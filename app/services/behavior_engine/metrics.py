from dataclasses import dataclass

@dataclass
class SessionMetrics:
    """
    DTO that holds the RAW telemetry data.
    Updated to include the specific fields needed for the 3 Decision Trees (Figs 5, 6, 7).
    """
    # Base Metrics
    duration_minutes: float
    total_keystrokes: int
    total_run_attempts: int
    total_idle_minutes: float
    focus_violation_count: int
    net_code_change: int
    
    # --- NEW FIELDS FOR DECISION TREES ---
    # These are required by the DataFusionEngine logic we just wrote
    last_edit_size_chars: int        # Needed for Provenance 
    last_run_interval_seconds: float # Needed for Iteration 
    is_semantic_change: bool         # Needed for Iteration 
    current_idle_duration: float     # Needed for Cognitive State 
    is_window_focused: bool          # Needed for Cognitive State 
    last_run_was_error: bool         # Needed for Cognitive State 
    
    # --- BURST TYPING DETECTION ---
    recent_burst_size_chars: int = 0 # Keystrokes in recent 5-second window (for spam detection)
