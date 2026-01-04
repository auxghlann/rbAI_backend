"""
FastAPI endpoints for code execution with behavioral telemetry integration.
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging

from ...services.execution import DockerExecutor, ExecutionResult

logger = logging.getLogger(__name__)

# Initialize executor (singleton)
executor = DockerExecutor()

router = APIRouter(prefix="/api/execution", tags=["execution"])


# --- REQUEST/RESPONSE MODELS ---

class TestCase(BaseModel):
    """Individual test case for code validation"""
    input: str = Field(default="", description="Standard input for the test")
    expected_output: str = Field(..., description="Expected program output")
    description: Optional[str] = Field(None, description="Test case description")


class ExecutionRequest(BaseModel):
    """Request body for code execution"""
    session_id: str = Field(..., description="Unique session identifier")
    code: str = Field(..., description="Python code to execute")
    problem_id: str = Field(..., description="Problem/activity identifier")
    stdin: Optional[str] = Field(default="", description="Standard input")
    test_cases: Optional[List[TestCase]] = Field(None, description="Test cases for validation")
    
    # Telemetry data for behavioral monitoring
    telemetry: Optional[Dict[str, Any]] = Field(
        None,
        description="Telemetry data: keystroke_count, time_since_last_run, etc."
    )


class ExecutionResponse(BaseModel):
    """Response body for code execution"""
    status: str
    output: str
    error: Optional[str] = None
    execution_time: float
    exit_code: int
    test_results: Optional[List[Dict]] = None
    timestamp: datetime
    
    # Behavioral monitoring flags
    behavioral_flags: Optional[Dict[str, Any]] = None


# --- ENDPOINTS ---

@router.post("/run", response_model=ExecutionResponse)
async def run_code(
    request: ExecutionRequest,
    background_tasks: BackgroundTasks
):
    """
    Execute Python code in a sandboxed Docker container.
    
    This endpoint:
    1. Executes user code securely in isolation
    2. Captures output and errors
    3. Stores code in session for chat context retrieval
    4. Logs execution event for behavioral analysis
    5. Returns results immediately to frontend
    
    Security Features:
    - 128MB memory limit
    - 5-second timeout
    - No network access
    - Read-only filesystem
    """
    
    logger.info(f"Execution request for session {request.session_id}, problem {request.problem_id}")
    
    try:
        # Store code in session for chat context (import here to avoid circular dependency)
        from .chat import _store_session_code
        background_tasks.add_task(
            _store_session_code,
            request.session_id,
            request.problem_id,
            request.code
        )
        
        # Execute code
        if request.test_cases:
            # Run with test validation
            result = await executor.execute_with_tests(
                code=request.code,
                test_cases=[tc.dict() for tc in request.test_cases]
            )
        else:
            # Simple execution
            result = await executor.execute_code(
                code=request.code,
                stdin=request.stdin or ""
            )
        
        # Prepare behavioral flags (to be analyzed by Data Fusion Engine)
        behavioral_flags = _analyze_execution_behavior(
            result=result,
            telemetry=request.telemetry
        )
        
        # Store execution event asynchronously (doesn't block response)
        background_tasks.add_task(
            _store_execution_event,
            session_id=request.session_id,
            problem_id=request.problem_id,
            code=request.code,
            result=result,
            telemetry=request.telemetry,
            behavioral_flags=behavioral_flags
        )
        
        # Return response immediately
        return ExecutionResponse(
            status=result.status,
            output=result.output,
            error=result.error if result.error else None,
            execution_time=result.execution_time,
            exit_code=result.exit_code,
            test_results=result.test_results,
            timestamp=datetime.now(),
            behavioral_flags=behavioral_flags
        )
        
    except Exception as e:
        logger.error(f"Execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Execution service error: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Check if the execution service is healthy.
    
    Returns Docker status and configuration.
    """
    health = executor.health_check()
    
    if health["status"] != "healthy":
        raise HTTPException(
            status_code=503,
            detail="Execution service unavailable"
        )
    
    return health


# --- HELPER FUNCTIONS ---

def _analyze_execution_behavior(
    result: ExecutionResult,
    telemetry: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze execution in context of behavioral monitoring.
    
    This feeds into:
    - Cognitive State Differentiation (Figure 8): last_run_was_error
    - Iteration Quality Assessment (Figure 7): run intervals
    
    Returns flags for the Data Fusion Engine.
    """
    if not telemetry:
        return {}
    
    flags = {
        "last_run_was_error": result.status == "error",
        "execution_time": result.execution_time,
        "timestamp": datetime.now().isoformat()
    }
    
    # Calculate run interval if available
    if "last_run_timestamp" in telemetry:
        try:
            last_run = datetime.fromisoformat(telemetry["last_run_timestamp"])
            interval = (datetime.now() - last_run).total_seconds()
            flags["last_run_interval_seconds"] = interval
            
            # Flag rapid-fire attempts (< 10 seconds, as per thesis)
            if interval < 10:
                flags["rapid_iteration"] = True
        except:
            pass
    
    return flags


async def _store_execution_event(
    session_id: str,
    problem_id: str,
    code: str,
    result: ExecutionResult,
    telemetry: Optional[Dict[str, Any]],
    behavioral_flags: Dict[str, Any]
):
    """
    Store execution event in database for retrospective analysis.
    
    This data feeds into:
    - Run-Attempt Timeline Analysis (Section 1.2.5)
    - Data Fusion Engine for integrity verification
    
    TODO: Implement database persistence
    """
    event_data = {
        "session_id": session_id,
        "problem_id": problem_id,
        "timestamp": datetime.now(),
        "event_type": "run_attempt",
        "code_snapshot": code,
        "output": result.output,
        "error": result.error,
        "status": result.status,
        "execution_time": result.execution_time,
        "telemetry": telemetry,
        "behavioral_flags": behavioral_flags
    }
    
    # TODO: Insert into database (Sessions table, Telemetry Events table)
    logger.info(f"Storing execution event for session {session_id}")
    # await db.telemetry_events.insert(event_data)
    pass


# --- TESTING/DEBUG ENDPOINTS (Remove in production) ---

@router.post("/test/simple")
async def test_simple_execution():
    """Quick test endpoint to verify Docker execution works"""
    result = await executor.execute_code("print('Hello from Docker!')")
    return result.to_dict()


@router.post("/test/timeout")
async def test_timeout():
    """Test timeout handling"""
    result = await executor.execute_code("import time; time.sleep(10)")
    return result.to_dict()


@router.post("/test/memory")
async def test_memory_limit():
    """Test memory limit enforcement"""
    result = await executor.execute_code("data = 'x' * (200 * 1024 * 1024)")  # Try to allocate 200MB
    return result.to_dict()