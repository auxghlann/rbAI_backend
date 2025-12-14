"""
FastAPI endpoints for behavioral telemetry processing.
Implements the backend side of Figure 11 architecture.

Frontend sends raw telemetry → Backend applies Data Fusion → Returns CES + States
"""

from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
import logging

from ...services.behavior_engine.metrics import SessionMetrics
from ...services.behavior_engine.data_fusion import DataFusionEngine
from ...services.behavior_engine.ces_calculator import CESCalculator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])

# Initialize behavioral analysis engines
fusion_engine = DataFusionEngine()
ces_calculator = CESCalculator()


# --- REQUEST/RESPONSE MODELS ---

class TelemetryRequest(BaseModel):
    """
    Raw telemetry data from frontend (Figure 11: Stage 1 - Telemetry Capture)
    Frontend only collects and buffers raw behavioral signals.
    """
    session_id: str = Field(..., description="Unique session identifier")
    problem_id: str = Field(..., description="Problem/activity identifier")
    
    # Raw metrics collected by frontend
    session_duration_minutes: float = Field(..., description="Total session time in minutes")
    total_keystrokes: int = Field(..., description="Raw keystroke count")
    total_run_attempts: int = Field(..., description="Number of code executions")
    total_idle_minutes: float = Field(..., description="Total idle time in minutes")
    focus_violation_count: int = Field(..., description="Tab switches / blur events")
    net_code_change: int = Field(..., description="Current code length")
    
    # Context signals for Data Fusion
    last_edit_size_chars: int = Field(..., description="Size of most recent edit")
    last_run_interval_seconds: float = Field(..., description="Time since last run")
    is_semantic_change: bool = Field(..., description="Code changed since last run")
    current_idle_duration: float = Field(..., description="Current idle period in seconds")
    is_window_focused: bool = Field(..., description="Window currently focused")
    last_run_was_error: bool = Field(..., description="Last execution had errors")


class TelemetryResponse(BaseModel):
    """
    Computed behavioral insights from backend (Figure 11: Stage 2-4)
    Backend performs Data Fusion, CES calculation, and classification.
    """
    # Computed metrics (after Data Fusion)
    kpm: float = Field(..., description="Keystrokes Per Minute")
    ad: float = Field(..., description="Attempt Density")
    ir: float = Field(..., description="Idle Ratio")
    fvc: int = Field(..., description="Focus Violation Count")
    
    # CES Score
    ces: float = Field(..., description="Cognitive Engagement Score (-1.0 to 1.0)")
    ces_classification: str = Field(..., description="Engagement level classification")
    
    # Data Fusion States
    provenance_state: str = Field(..., description="Code authenticity classification")
    iteration_state: str = Field(..., description="Iteration quality classification")
    cognitive_state: str = Field(..., description="Cognitive engagement state")
    
    # Effective metrics (post-fusion adjustments)
    effective_kpm: float = Field(..., description="Adjusted KPM after spam filtering")
    effective_ad: float = Field(..., description="Adjusted AD after guessing penalty")
    effective_ir: float = Field(..., description="Adjusted IR after reflective pause exclusion")
    integrity_penalty: float = Field(..., description="Overall integrity penalty applied")
    
    timestamp: datetime = Field(default_factory=datetime.now)


# --- ENDPOINTS ---

@router.post("/analyze", response_model=TelemetryResponse)
async def analyze_telemetry(request: TelemetryRequest):
    """
    Analyzes raw telemetry and returns computed behavioral insights.
    
    This endpoint implements the backend pipeline from Figure 11:
    1. Receives raw telemetry from frontend
    2. Applies Data Fusion Engine (integrity checks)
    3. Computes CES score
    4. Returns classification and insights
    
    Frontend → Backend Flow:
    - Frontend: Collects keystrokes, focus events, run attempts (raw data only)
    - Backend: Processes with DataFusionEngine → CESCalculator
    - Returns: Computed CES, states, and effective metrics
    """
    
    logger.info(f"Processing telemetry for session {request.session_id}, problem {request.problem_id}")
    
    try:
        # Step 1: Convert request to SessionMetrics DTO
        metrics = SessionMetrics(
            duration_minutes=request.session_duration_minutes,
            total_keystrokes=request.total_keystrokes,
            total_run_attempts=request.total_run_attempts,
            total_idle_minutes=request.total_idle_minutes,
            focus_violation_count=request.focus_violation_count,
            net_code_change=request.net_code_change,
            last_edit_size_chars=request.last_edit_size_chars,
            last_run_interval_seconds=request.last_run_interval_seconds,
            is_semantic_change=request.is_semantic_change,
            current_idle_duration=request.current_idle_duration,
            is_window_focused=request.is_window_focused,
            last_run_was_error=request.last_run_was_error
        )
        
        # Step 2: Apply Data Fusion (Figure 11: Stage 2)
        # This performs the 3 classification pipelines:
        # - Provenance & Authenticity (Figure 5)
        # - Iteration Quality (Figure 6)
        # - Cognitive State (Figure 7)
        fusion_insights = fusion_engine.analyze(metrics)
        
        # Step 3: Calculate CES (Figure 11: Stage 3)
        ces_result = ces_calculator.calculate(metrics, fusion_insights)
        
        # Step 4: Prepare response with all computed data
        response = TelemetryResponse(
            # Basic metrics
            kpm=ces_result["kpm"],
            ad=ces_result["ad"],
            ir=ces_result["ir"],
            fvc=metrics.focus_violation_count,
            
            # CES Score
            ces=ces_result["ces"],
            ces_classification=ces_result["classification"],
            
            # Data Fusion States
            provenance_state=fusion_insights.provenance_state.value,
            iteration_state=fusion_insights.iteration_state.value,
            cognitive_state=fusion_insights.cognitive_state.value,
            
            # Effective metrics (post-fusion)
            effective_kpm=fusion_insights.effective_kpm,
            effective_ad=fusion_insights.effective_ad,
            effective_ir=fusion_insights.effective_ir,
            integrity_penalty=fusion_insights.integrity_penalty
        )
        
        logger.info(f"CES computed: {ces_result['ces']:.3f} ({ces_result['classification']})")
        
        return response
        
    except Exception as e:
        logger.error(f"Telemetry analysis failed: {e}", exc_info=True)
        raise


@router.get("/health")
async def health_check():
    """Check if telemetry processing services are available"""
    return {
        "status": "healthy",
        "services": {
            "data_fusion_engine": "available",
            "ces_calculator": "available"
        }
    }
