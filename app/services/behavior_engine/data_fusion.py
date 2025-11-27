from dataclasses import dataclass
from enum import Enum
from app.services.behavior_engine.ces_calculator import SessionMetrics

# --- DEFINING THE ENUMS (The Standardized Flags) ---

class ProvenanceState(str, Enum):
    INCREMENTAL_EDIT = "Incremental Edit"
    AUTHENTIC_REFACTORING = "Authentic Refactoring"
    AMBIGUOUS_EDIT = "Ambiguous Large Edit"
    SUSPECTED_PASTE = "Suspected External Paste"
    SPAMMING = "Spamming/Gaming"

class IterationState(str, Enum):
    NORMAL = "Normal"
    DELIBERATE_DEBUGGING = "Deliberate Debugging"
    VERIFICATION_RUN = "Verification Run"
    MICRO_ITERATION = "Micro-Iteration"
    RAPID_GUESSING = "Rapid-Fire Guessing"

class CognitiveState(str, Enum):
    ACTIVE = "Active"
    REFLECTIVE_PAUSE = "Reflective Pause"
    PASSIVE_IDLE = "Passive Idle"
    DISENGAGEMENT = "Disengagement"

@dataclass
class FusionInsights:
    """
    Carries the Qualitative Pedagogical Insights derived from Data Fusion.
    Now uses strict ENUMS instead of raw strings.
    """
    provenance_state: ProvenanceState
    iteration_state: IterationState
    cognitive_state: CognitiveState
    
    # Effective Metrics
    effective_kpm: float
    effective_ad: float
    effective_ir: float
    integrity_penalty: float

class DataFusionEngine:
    """
    Implements the Algorithmic Synergy using strict State Enums.
    """

    def analyze(self, metrics: SessionMetrics) -> FusionInsights:
        
        # --- 1. PROVENANCE & AUTHENTICITY ---
        
        # Default State
        provenance = ProvenanceState.INCREMENTAL_EDIT
        integrity_penalty = 0.0
        
        raw_kpm = metrics.total_keystrokes / metrics.duration_minutes if metrics.duration_minutes > 0 else 0
        LARGE_INSERTION_THRESHOLD = 100 
        
        # Logic Tree: Large Insertions
        if metrics.last_edit_size_chars > LARGE_INSERTION_THRESHOLD:
            if metrics.focus_violation_count > 0 and raw_kpm < 5.0:
                provenance = ProvenanceState.SUSPECTED_PASTE
                integrity_penalty = 0.5
            elif raw_kpm > 20.0:
                provenance = ProvenanceState.AUTHENTIC_REFACTORING
            else:
                provenance = ProvenanceState.AMBIGUOUS_EDIT

        # Logic Tree: Spam/Gaming Check
        efficiency_ratio = metrics.net_code_change / metrics.total_keystrokes if metrics.total_keystrokes > 50 else 1.0
        
        if metrics.total_keystrokes > 200 and efficiency_ratio < 0.05:
            effective_kpm = 0.0
            provenance = ProvenanceState.SPAMMING
        else:
            effective_kpm = raw_kpm


        # --- 2. ITERATION QUALITY ---
        
        iteration = IterationState.NORMAL
        effective_runs = metrics.total_run_attempts
        
        # Logic Tree: Run Intervals
        if metrics.last_run_interval_seconds < 10:
            if not metrics.is_semantic_change:
                iteration = IterationState.RAPID_GUESSING
                # Penalty: Remove 20% of runs from effective count
                effective_runs = metrics.total_run_attempts * 0.8 
            else:
                iteration = IterationState.MICRO_ITERATION
        else:
            if metrics.is_semantic_change:
                iteration = IterationState.DELIBERATE_DEBUGGING
            else:
                iteration = IterationState.VERIFICATION_RUN

        effective_ad = effective_runs / metrics.duration_minutes if metrics.duration_minutes > 0 else 0


        # --- 3. COGNITIVE STATE ---
        
        cognitive = CognitiveState.ACTIVE
        adjusted_idle_minutes = metrics.total_idle_minutes
        
        # Logic Tree: Idle Context
        if metrics.current_idle_duration > 30: 
            if not metrics.is_window_focused:
                cognitive = CognitiveState.DISENGAGEMENT
            else:
                if metrics.last_run_was_error:
                    cognitive = CognitiveState.REFLECTIVE_PAUSE
                    # Reward: Remove this pause from penalty
                    current_pause_min = metrics.current_idle_duration / 60
                    adjusted_idle_minutes = max(0, metrics.total_idle_minutes - current_pause_min)
                else:
                    cognitive = CognitiveState.PASSIVE_IDLE

        effective_ir = adjusted_idle_minutes / metrics.duration_minutes if metrics.duration_minutes > 0 else 0


        return FusionInsights(
            provenance_state=provenance,
            iteration_state=iteration,
            cognitive_state=cognitive,
            effective_kpm=effective_kpm,
            effective_ad=effective_ad,
            effective_ir=effective_ir,
            integrity_penalty=integrity_penalty
        )