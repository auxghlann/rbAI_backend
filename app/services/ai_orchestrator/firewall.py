"""
Pedagogical Firewall - Main orchestration logic.

Coordinates scope validation, behavioral context integration, and Socratic tutoring.
Stateless design for single-shot interactions focused on learning support.
"""

import logging
from typing import Optional
from dataclasses import dataclass

from .llm_client import LLMClient
from .policies import ScopePolicy, InterventionPolicy
from .prompts import (
    SCOPE_VALIDATOR,
    build_socratic_prompt,
    OUT_OF_SCOPE_RESPONSE,
)

logger = logging.getLogger(__name__)


@dataclass
class ChatContext:
    """
    Context bundle for a single chat interaction.
    Stateless - no conversation history maintained.
    """
    user_query: str
    problem_description: str
    
    # Optional behavioral context from telemetry
    cognitive_state: Optional[str] = None
    iteration_state: Optional[str] = None
    provenance_state: Optional[str] = None
    
    # Metadata
    problem_id: Optional[str] = None


@dataclass
class ChatResponse:
    """Structured response from the pedagogical firewall"""
    message: str
    is_allowed: bool
    reasoning: Optional[str] = None
    intervention_triggered: bool = False


class PedagogicalFirewall:
    """
    Main orchestrator for AI-powered learning support.
    
    Architecture:
    1. Quick policy-based filtering (fast path)
    2. LLM-based scope validation (if needed)
    3. Behavioral context integration
    4. Socratic response generation
    
    Design Principles:
    - Stateless: Each request is independent
    - Token-efficient: Minimal context, concise responses
    - Behaviorally-aware: Adapts to learner state
    - Safe: Filters out-of-scope and harmful requests
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize firewall with LLM client.
        
        Args:
            llm_client: Optional pre-configured LLMClient (creates default if None)
        """
        self.llm = llm_client or LLMClient()
        logger.info("PedagogicalFirewall initialized")
    
    async def process_request(self, context: ChatContext) -> ChatResponse:
        """
        Main entry point - process a chat request with full pipeline.
        
        Pipeline:
        1. Quick policy filter
        2. LLM scope validation (if needed)
        3. Behavioral analysis
        4. Generate Socratic response
        
        Args:
            context: ChatContext with query and optional behavioral data
            
        Returns:
            ChatResponse with message and metadata
        """
        logger.info(
            f"Processing request - Problem: {context.problem_id}"
        )
        
        # STEP 1: Quick policy-based filter
        is_allowed, filter_reason = ScopePolicy.quick_filter(context.user_query)
        
        if not is_allowed:
            logger.warning(f"Request blocked by policy: {filter_reason}")
            return ChatResponse(
                message=OUT_OF_SCOPE_RESPONSE,
                is_allowed=False,
                reasoning=filter_reason,
            )
        
        # STEP 2: LLM scope validation (for borderline or unclear cases)
        if filter_reason == "NEEDS_LLM_VALIDATION":
            try:
                is_in_scope = await self.llm.validate_scope(
                    context.user_query,
                    (SCOPE_VALIDATOR.system, SCOPE_VALIDATOR.user)
                )
                
                if not is_in_scope:
                    logger.info("Request rejected by LLM scope validator")
                    return ChatResponse(
                        message=OUT_OF_SCOPE_RESPONSE,
                        is_allowed=False,
                        reasoning="LLM_VALIDATION_FAILED",
                    )
                    
            except Exception as e:
                logger.error(f"Scope validation error: {e}")
                # Fail open - allow request if validation fails
                pass
        
        # STEP 3: Check if behavioral intervention is needed
        intervention_mode = False
        if context.cognitive_state and context.iteration_state:
            intervention_mode = InterventionPolicy.should_intervene(
                context.cognitive_state,
                context.iteration_state,
            )
            
            if intervention_mode:
                logger.info(
                    f"Intervention triggered - Cognitive: {context.cognitive_state}, "
                    f"Iteration: {context.iteration_state}"
                )
        
        # STEP 4: Generate Socratic response with behavioral context
        try:
            system_prompt, user_prompt = build_socratic_prompt(
                user_query=context.user_query,
                problem_description=context.problem_description,
                cognitive_state=context.cognitive_state,
                iteration_state=context.iteration_state,
                provenance_state=context.provenance_state,
            )
            
            response_text = await self.llm.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.7,  # Balanced creativity for Socratic questions
            )
            
            logger.info("Socratic response generated successfully")
            
            return ChatResponse(
                message=response_text,
                is_allowed=True,
                reasoning=filter_reason,
                intervention_triggered=intervention_mode,
            )
            
        except Exception as e:
            logger.error(f"Failed to generate Socratic response: {e}")
            
            # Fallback response
            return ChatResponse(
                message=(
                    "I'm having trouble processing your request right now. "
                    "Please try rephrasing your question or try again in a moment."
                ),
                is_allowed=True,
                reasoning="LLM_ERROR",
            )
    
    async def generate_hint(
        self,
        problem_description: str,
        current_code: Optional[str] = None,
        cognitive_state: Optional[str] = None,
    ) -> str:
        """
        Generate a proactive hint when student is struggling.
        
        Use case: Called when behavioral engine detects DISENGAGEMENT
        or extended PASSIVE_IDLE state.
        
        Args:
            problem_description: The problem statement
            current_code: Student's current attempt (optional)
            cognitive_state: Current cognitive state
            
        Returns:
            Hint message
        """
        hint_query = "I'm stuck and need a hint to get started."
        
        if current_code:
            hint_query = f"I'm stuck. Here's my current code:\n```\n{current_code[:200]}...\n```\nWhat should I focus on?"
        
        context = ChatContext(
            user_query=hint_query,
            problem_description=problem_description,
            cognitive_state=cognitive_state or "DISENGAGEMENT",
        )
        
        response = await self.process_request(context)
        return response.message
