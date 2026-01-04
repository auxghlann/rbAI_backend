"""
Pedagogical Firewall - Main orchestration logic.

Coordinates scope validation, behavioral context integration, and Socratic tutoring.
Stateless design for single-shot interactions focused on learning support.
"""

import logging
from typing import Optional, AsyncGenerator, List, Dict
from dataclasses import dataclass, field

from .llm_client_groq import LLMClientGroq
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
    Now includes conversation history for continuity within a chat thread.
    """
    user_query: str
    problem_description: str
    
    # Conversation history for memory
    chat_history: List[Dict[str, str]] = field(default_factory=list)
    # Format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    
    # Optional current code context (retrieved from session)
    current_code: Optional[str] = None
    
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
    
    def __init__(self, llm_client: Optional[LLMClientGroq] = None):
        """
        Initialize firewall with Groq LLM client.
        
        Args:
            llm_client: Optional pre-configured LLMClientGroq (creates default if None)
        """
        self.llm = llm_client or LLMClientGroq()
        logger.info("PedagogicalFirewall initialized with Groq")
    
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
        
        # STEP 4: Generate Socratic response with behavioral context and history
        try:
            system_prompt, user_prompt = build_socratic_prompt(
                user_query=context.user_query,
                problem_description=context.problem_description,
                current_code=context.current_code,
                cognitive_state=context.cognitive_state,
                iteration_state=context.iteration_state,
                provenance_state=context.provenance_state,
            )
            
            response_text = await self.llm.complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                chat_history=context.chat_history,
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
    
    async def stream_response(self, context: ChatContext) -> AsyncGenerator[str, None]:
        """
        Stream a response chunk by chunk for real-time UX.
        
        Similar to process_request but yields chunks as they're generated.
        Used by the /stream endpoint for ChatGPT-like streaming responses.
        
        Args:
            context: ChatContext with query and optional behavioral data
            
        Yields:
            String chunks as they're generated from the LLM
        """
        logger.info(f"Streaming request - Problem: {context.problem_id}")
        
        # STEP 1: Quick policy-based filter
        is_allowed, filter_reason = ScopePolicy.quick_filter(context.user_query)
        
        if not is_allowed:
            logger.warning(f"Request blocked by policy: {filter_reason}")
            yield OUT_OF_SCOPE_RESPONSE
            return
        
        # STEP 2: LLM scope validation (for borderline cases)
        if filter_reason == "NEEDS_LLM_VALIDATION":
            try:
                is_in_scope = await self.llm.validate_scope(
                    context.user_query,
                    (SCOPE_VALIDATOR.system, SCOPE_VALIDATOR.user)
                )
                
                if not is_in_scope:
                    logger.info("Request rejected by LLM scope validator")
                    yield OUT_OF_SCOPE_RESPONSE
                    return
                    
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
        
        # STEP 4: Stream Socratic response with behavioral context
        try:
            system_prompt, user_prompt = build_socratic_prompt(
                user_query=context.user_query,
                problem_description=context.problem_description,
                current_code=context.current_code,
                cognitive_state=context.cognitive_state,
                iteration_state=context.iteration_state,
                provenance_state=context.provenance_state,
            )
            
            # Stream chunks from LLM with chat history
            async for chunk in self.llm.stream_complete(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                chat_history=context.chat_history,
                temperature=0.7,
            ):
                yield chunk
            
            logger.info("Streaming response completed successfully")
            
        except Exception as e:
            logger.error(f"Failed to stream Socratic response: {e}")
            yield (
                "\n\nI'm having trouble processing your request right now. "
                "Please try rephrasing your question or try again in a moment."
            )
