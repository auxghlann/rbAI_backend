from dataclasses import dataclass
from enum import Enum
from app.services.behavior_engine.metrics import SessionMetrics

# --- DEFINING THE ENUMS (The Standardized Flags) ---

class ProvenanceState(str, Enum):
    INCREMENTAL_EDIT = "Incremental Edit"
    AUTHENTIC_REFACTORING = "Authentic Refactoring"
    AMBIGUOUS_EDIT = "Ambiguous Large Edit"
    SUSPECTED_PASTE = "Suspected External Paste"
    SPAMMING = "Spamming"

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

# --- CORE ALGORITHM ---

@dataclass
class FusionInsights:
    """
    Carries the Qualitative Pedagogical Insights derived from Data Fusion.
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
    
    Domain Context (Thesis Section 1.1.1):
    - Target: Novice programmers solving LeetCode-style algorithmic problems
    - Problem Size: 20-80 lines of code (1,500-2,500 characters typical solution)
    - Session Duration: 15-60 minutes per problem
    - User Characteristics: Programming 1-2 level students with limited syntax fluency
    
    All thresholds below are calibrated for this specific domain and should NOT be
    assumed generalizable to professional development or large-scale projects.
    """

    # =====================================================================
    # DOMAIN-CALIBRATED THRESHOLDS (Thesis Section 1.1.1)
    # =====================================================================
    
    # Provenance Detection
    LARGE_INSERTION_THRESHOLD = 100  
    # Justification: For 40-line solutions (~1,500 chars), 100 chars represents
    # 6-7% of solution inserted at once. Typical incremental edits by novices
    # are 15-40 characters (1-2 lines). Exceeding this suggests bulk transfer.
    
    SPAM_KEYSTROKE_MINIMUM = 200
    SPAM_EFFICIENCY_THRESHOLD = 0.05
    # Justification: Efficiency ratio = net_code_change / total_keystrokes.
    # Novices exhibit trial-and-error with ratios ~0.20-0.40. Values <0.05
    # indicate meaningless key-mashing without productive intent.
    
    # Iteration Quality
    RAPID_ITERATION_THRESHOLD = 10  # seconds
    # Justification: Minimum time for novices to: (1) observe output (2-3s),
    # (2) comprehend error/result (3-5s), (3) formulate change (3-4s).
    # Intervals <10s suggest reflexive guessing vs. hypothesis-driven debugging.
    
    RAPID_GUESSING_PENALTY = 0.8
    # Justification: Rapid-fire attempts lack deliberation but may provide
    # learning through immediate feedback. Assigned 80% productivity weight
    # (20% penalty) as conservative estimate pending validation (Phase 3).
    
    # Cognitive State
    REFLECTIVE_PAUSE_MIN = 30  # seconds
    DISENGAGEMENT_THRESHOLD = 120  # seconds
    # Justification: Novices require 30-120s post-error to parse messages
    # and plan corrections. <30s = normal flow. 30-120s + error context = 
    # reflective pause (valid). >120s or unfocused = disengagement.

    def analyze(self, metrics: SessionMetrics) -> FusionInsights:
        """
        Performs multi-dimensional behavioral analysis on raw session telemetry.
        
        Implements Data Fusion Algorithm (Thesis Section 1.2.6, Figure 4):
        1. Provenance & Authenticity (Figure 5): Detects copy-paste vs authentic coding
        2. Iteration Quality (Figure 6): Distinguishes debugging from guessing
        3. Cognitive State (Figure 7): Contextualizes idle time
        
        Args:
            metrics: Raw telemetry data from novice programming session
        
        Returns:
            FusionInsights containing:
            - Pedagogical state classifications (Provenance, Iteration, Cognitive)
            - Adjusted "effective" metrics (cleaned of spam, guessing, etc.)
            - Integrity penalty (0.0 to 1.0) for suspected dishonesty
        
        Domain Assumptions (see Thesis Section 1.1.1):
        - Short-form problems (20-80 LOC solutions)
        - Novice programmers (Programming 1-2 level)
        - Session duration 15-60 minutes
        """
        
        # --- 1. PROVENANCE & AUTHENTICITY (Figure 5) ---
        
        # Default State
        provenance = ProvenanceState.INCREMENTAL_EDIT
        integrity_penalty = 0.0
        
        raw_kpm = metrics.total_keystrokes / metrics.duration_minutes if metrics.duration_minutes > 0 else 0
        
        # Logic Tree: Large Insertions
        # Context: For novices solving 40-line problems, 100-char insertions
        # represent ~3 lines added at once, atypical for incremental construction
        if metrics.last_edit_size_chars > self.LARGE_INSERTION_THRESHOLD:
            if metrics.focus_violation_count > 0 and raw_kpm < 5.0:
                # Pattern: Large insertion + recent tab-switch + low typing rate
                # Interpretation: Likely copied from external source
                provenance = ProvenanceState.SUSPECTED_PASTE
                integrity_penalty = 0.5
            elif raw_kpm > 20.0:
                # Pattern: Large insertion + high sustained typing
                # Interpretation: Authentic refactoring/rewrite by skilled novice
                provenance = ProvenanceState.AUTHENTIC_REFACTORING
            else:
                # Pattern: Large insertion + moderate activity
                # Interpretation: Uncertain—could be internal block move/paste
                provenance = ProvenanceState.AMBIGUOUS_EDIT

        # Logic Tree: Spam Check
        # Context: Novices typically achieve efficiency ratios of 0.20-0.40
        # due to trial-and-error. Ratios <0.05 suggest random key-mashing.
        efficiency_ratio = metrics.net_code_change / metrics.total_keystrokes if metrics.total_keystrokes > 50 else 1.0
        
        if metrics.total_keystrokes > self.SPAM_KEYSTROKE_MINIMUM and efficiency_ratio < self.SPAM_EFFICIENCY_THRESHOLD:
            # Detected: High keystroke volume with negligible code retention
            # Action: Nullify KPM contribution to prevent score inflation
            effective_kpm = 0.0
            provenance = ProvenanceState.SPAMMING
        else:
            effective_kpm = raw_kpm


        # --- 2. ITERATION QUALITY (Figure 6) ---
        
        iteration = IterationState.NORMAL
        effective_runs = metrics.total_run_attempts
        
        # Logic Tree: Run Intervals
        # Context: Novices need ~10s minimum to process feedback and respond
        if metrics.last_run_interval_seconds < self.RAPID_ITERATION_THRESHOLD:
            if not metrics.is_semantic_change:
                # Pattern: Quick re-run + no logical change (whitespace only)
                # Interpretation: Reflexive guessing, not deliberate debugging
                iteration = IterationState.RAPID_GUESSING
                # Penalty: Discount 20% of run attempts (partial productivity credit)
                effective_runs = metrics.total_run_attempts * self.RAPID_GUESSING_PENALTY
            else:
                # Pattern: Quick re-run + meaningful code change
                # Interpretation: Valid fast-paced debugging (micro-iteration)
                iteration = IterationState.MICRO_ITERATION
        else:
            if metrics.is_semantic_change:
                # Pattern: Sufficient interval + logical modification
                # Interpretation: Optimal hypothesis-driven debugging
                iteration = IterationState.DELIBERATE_DEBUGGING
            else:
                # Pattern: Sufficient interval + trivial change
                # Interpretation: Re-running same code (verification/sanity check)
                iteration = IterationState.VERIFICATION_RUN

        effective_ad = effective_runs / metrics.duration_minutes if metrics.duration_minutes > 0 else 0


        # --- 3. COGNITIVE STATE (Figure 7) ---
        
        cognitive = CognitiveState.ACTIVE
        adjusted_idle_minutes = metrics.total_idle_minutes
        
        # Logic Tree: Idle Context
        # Context: Novices need 30-120s to parse errors and plan corrections
        if metrics.current_idle_duration > self.REFLECTIVE_PAUSE_MIN: 
            if not metrics.is_window_focused:
                # Pattern: Idle + window unfocused (alt-tabbed away)
                # Interpretation: Off-task behavior, distraction
                cognitive = CognitiveState.DISENGAGEMENT
            else:
                if metrics.last_run_was_error:
                    # Pattern: Idle + window focused + recent error
                    # Interpretation: Reading error messages, planning fix (VALID)
                    cognitive = CognitiveState.REFLECTIVE_PAUSE
                    # Reward: Exclude this pause from idle penalty
                    current_pause_min = metrics.current_idle_duration / 60
                    adjusted_idle_minutes = max(0, metrics.total_idle_minutes - current_pause_min)
                else:
                    # Pattern: Idle + window focused + no error context
                    # Interpretation: Unproductive stalling (writer's block)
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