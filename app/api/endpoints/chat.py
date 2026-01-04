"""
Chat API endpoint for pedagogical AI interactions.

Provides Socratic tutoring integrated with behavioral telemetry.
"""

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, AsyncGenerator, List, Dict
from datetime import datetime
import logging
import json

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


# --- SESSION CODE STORAGE ---
# In-memory storage for session code (replace with Redis/DB in production)
_session_code_store: Dict[str, Dict[str, str]] = {}


async def _store_session_code(session_id: str, problem_id: str, code: str) -> None:
    """
    Store the current code for a session-problem pair.
    
    Args:
        session_id: Unique session identifier
        problem_id: Problem/activity identifier
        code: Current code content
    """
    key = f"{session_id}:{problem_id}"
    _session_code_store[key] = {
        "code": code,
        "timestamp": datetime.utcnow().isoformat(),
    }
    logger.debug(f"Stored code for {key} ({len(code)} chars)")


async def _get_session_code(session_id: str, problem_id: str) -> Optional[str]:
    """
    Retrieve the current code for a session-problem pair.
    
    Args:
        session_id: Unique session identifier
        problem_id: Problem/activity identifier
        
    Returns:
        Current code or None if not found
    """
    key = f"{session_id}:{problem_id}"
    stored = _session_code_store.get(key)
    if stored:
        return stored["code"]
    return None


# --- SIMPLE CHAT MODELS FOR FRONTEND ---

class SimpleChatRequest(BaseModel):
    """Simple chat request from frontend"""
    message: str = Field(..., description="User message", min_length=1, max_length=500)
    chat_history: Optional[List[Dict[str, str]]] = Field(
        default=None,
        description="Previous conversation messages for context (optional)"
    )
    session_id: Optional[str] = Field(
        default=None,
        description="Session ID to retrieve current code context"
    )
    problem_id: Optional[str] = Field(
        default=None,
        description="Problem ID to retrieve current code context"
    )


class SimpleChatResponse(BaseModel):
    """Simple chat response to frontend"""
    response: str = Field(..., description="AI response")


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
    
    # Optional conversation history for context
    chat_history: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Previous conversation messages within this thread"
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

@router.post("", response_model=SimpleChatResponse)
async def simple_chat(request: SimpleChatRequest):
    """
    Simple chat endpoint for frontend - minimal interface.
    
    Provides helpful guidance and hints for coding problems.
    """
    if not firewall:
        raise HTTPException(
            status_code=503,
            detail="AI tutoring service is unavailable. Check GROQ_API_KEY configuration."
        )
    
    logger.info(f"Simple chat request - Message length: {len(request.message)}, History: {len(request.chat_history or [])} messages")
    
    # Fetch current code from session if available
    current_code = None
    if request.session_id and request.problem_id:
        current_code = await _get_session_code(request.session_id, request.problem_id)
        if current_code:
            logger.info(f"Retrieved code context for session {request.session_id} ({len(current_code)} chars)")
    
    # Build basic context (assume general coding help)
    context = ChatContext(
        user_query=request.message,
        problem_description="General coding problem",
        problem_id=request.problem_id or "simple-chat",
        chat_history=request.chat_history or [],
        current_code=current_code,
    )
    
    try:
        # Process through firewall
        response = await firewall.process_request(context)
        
        return SimpleChatResponse(
            response=response.message
        )
        
    except Exception as e:
        logger.error(f"Error processing simple chat request: {e}")
        return SimpleChatResponse(
            response="Sorry, I encountered an error. Please try again."
        )


@router.post("/stream")
async def stream_chat(request: SimpleChatRequest):
    """
    Streaming chat endpoint with Server-Sent Events (SSE).
    
    Streams AI responses in real-time for better UX, similar to ChatGPT.
    Frontend receives chunks as they're generated.
    
    Response format:
        data: {"content": "chunk text"}
        data: {"content": "more text"}
        data: [DONE]
    """
    if not firewall:
        raise HTTPException(
            status_code=503,
            detail="AI tutoring service is unavailable. Check GROQ_API_KEY configuration."
        )
    
    logger.info(f"Streaming chat request - Message length: {len(request.message)}, History: {len(request.chat_history or [])} messages")
    
    async def generate_response() -> AsyncGenerator[str, None]:
        """Generate SSE-formatted response chunks"""
        try:
            # Fetch current code from session if available
            current_code = None
            if request.session_id and request.problem_id:
                current_code = await _get_session_code(request.session_id, request.problem_id)
                if current_code:
                    logger.info(f"Retrieved code context for session {request.session_id} ({len(current_code)} chars)")
            
            # Build context with history
            context = ChatContext(
                user_query=request.message,
                problem_description="General coding problem",
                problem_id=request.problem_id or "simple-chat",
                chat_history=request.chat_history or [],
                current_code=current_code,
            )
            
            # Stream through firewall
            async for chunk in firewall.stream_response(context):
                # Format as SSE
                data = json.dumps({"content": chunk})
                yield f"data: {data}\n\n"
            
            # Send completion signal
            yield "data: [DONE]\n\n"
            
        except Exception as e:
            logger.error(f"Error in streaming chat: {e}")
            # Send error as final message
            error_data = json.dumps({
                "content": "\n\nSorry, I encountered an error. Please try again."
            })
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"
    
    return StreamingResponse(
        generate_response(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering
        }
    )


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
        f"Query length: {len(request.user_query)}, "
        f"History: {len(request.chat_history or [])} messages"
    )
    
    # Build context
    context = ChatContext(
        user_query=request.user_query,
        problem_description=request.problem_description,
        problem_id=request.problem_id,
        chat_history=request.chat_history or [],
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
