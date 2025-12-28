"""
Chat API endpoint for pedagogical AI interactions.

Provides Socratic tutoring integrated with behavioral telemetry.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging

from ...services.ai_orchestrator import PedagogicalFirewall
from ...services.ai_orchestrator.firewall import ChatContext

logger = logging.getLogger(__name__)

# Initialize firewall (singleton)
try:
    firewall = PedagogicalFirewall()
except Exception as e:
    logger.error(f"Failed to initialize PedagogicalFirewall: {e}")
    firewall = None

router = APIRouter(prefix="/api/chat", tags=["chat"])


# --- REQUEST/RESPONSE MODELS ---

class BehavioralContext(BaseModel):
    """Optional behavioral telemetry from the learning environment"""
    cognitive_state: Optional[str] = Field(
        None,
        description="ACTIVE, REFLECTIVE_PAUSE, PASSIVE_IDLE, or DISENGAGEMENT"
    )
    iteration_state: Optional[str] = Field(
        None,
        description="NORMAL, DELIBERATE_DEBUGGING, RAPID_GUESSING, etc."
    )
    provenance_state: Optional[str] = Field(
        None,
        description="INCREMENTAL_EDIT, SUSPECTED_PASTE, etc."
    )


class ChatRequest(BaseModel):
    """Request for AI tutoring assistance"""
    problem_id: str = Field(..., description="Problem identifier")
    problem_description: str = Field(
        ...,
        description="The coding problem statement or description",
        max_length=2000,  # Token management
    )
    user_query: str = Field(
        ...,
        description="Student's question or help request",
        min_length=5,
        max_length=500,  # Keep queries concise
    )
    
    # Optional behavioral context
    behavioral_context: Optional[BehavioralContext] = Field(
        None,
        description="Behavioral telemetry for context-aware responses"
    )
    
    # Optional student code context (for debugging help)
    current_code: Optional[str] = Field(
        None,
        description="Student's current code (optional, for debugging support)",
        max_length=1000,  # Keep token usage low
    )


class ChatResponse(BaseModel):
    """AI tutor response"""
    message: str = Field(..., description="AI-generated tutoring message")
    is_allowed: bool = Field(
        ...,
        description="Whether the request was in scope"
    )
    intervention_triggered: bool = Field(
        False,
        description="Whether behavioral intervention was triggered"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# --- ENDPOINTS ---

@router.post("/ask", response_model=ChatResponse)
async def ask_tutor(request: ChatRequest):
    """
    Get Socratic tutoring help on a coding problem.
    
    The AI will:
    - Validate the request is learning-oriented (not solution-seeking)
    - Adapt response based on behavioral state (if provided)
    - Provide hints and guiding questions (never direct solutions)
    - Filter out-of-scope requests
    
    Returns:
        Pedagogically appropriate response or out-of-scope message
    """
    if not firewall:
        raise HTTPException(
            status_code=503,
            detail="AI tutoring service is unavailable. Check OpenAI API configuration."
        )
    
    logger.info(
        f"Chat request - Problem: {request.problem_id}, "
        f"Query length: {len(request.user_query)}"
    )
    
    # Build context
    context = ChatContext(
        user_query=request.user_query,
        problem_description=request.problem_description,
        problem_id=request.problem_id,
    )
    
    # Add behavioral context if provided
    if request.behavioral_context:
        context.cognitive_state = request.behavioral_context.cognitive_state
        context.iteration_state = request.behavioral_context.iteration_state
        context.provenance_state = request.behavioral_context.provenance_state
    
    try:
        # Process through firewall
        response = await firewall.process_request(context)
        
        return ChatResponse(
            message=response.message,
            is_allowed=response.is_allowed,
            intervention_triggered=response.intervention_triggered,
        )
        
    except Exception as e:
        logger.error(f"Error processing chat request: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to process your request. Please try again."
        )


class HintRequest(BaseModel):
    """Request for a proactive hint"""
    problem_id: str = Field(..., description="Problem identifier")
    problem_description: str = Field(..., description="Problem statement")
    current_code: Optional[str] = Field(None, description="Current code attempt")
    cognitive_state: Optional[str] = Field(None, description="Current cognitive state")


@router.post("/hint", response_model=ChatResponse)
async def get_hint(request: HintRequest):
    """
    Get a proactive hint when stuck.
    
    Use case: Student clicks "I need help" button or system detects
    DISENGAGEMENT state and proactively offers assistance.
    
    Returns:
        Hint to help student get unstuck
    """
    if not firewall:
        raise HTTPException(
            status_code=503,
            detail="AI tutoring service is unavailable"
        )
    
    logger.info(f"Hint requested - Problem: {request.problem_id}")
    
    try:
        hint = await firewall.generate_hint(
            problem_description=request.problem_description,
            current_code=request.current_code,
            cognitive_state=request.cognitive_state,
        )
        
        return ChatResponse(
            message=hint,
            is_allowed=True,
            intervention_triggered=True,
        )
        
    except Exception as e:
        logger.error(f"Error generating hint: {e}")
        raise HTTPException(
            status_code=500,
            detail="Failed to generate hint"
        )


@router.get("/health")
async def health_check():
    """Check if AI tutoring service is operational"""
    if not firewall:
        return {
            "status": "unavailable",
            "reason": "PedagogicalFirewall not initialized"
        }
    
    return {
        "status": "operational",
        "model": firewall.llm.model,
    }
