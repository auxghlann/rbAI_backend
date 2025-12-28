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
    LARGE_INSERTION_THRESHOLD = 30  
    # Justification: For novice solutions (250-500 chars typical), 30 chars represents
    # 6-12% of solution inserted at once. Typical incremental edits by novices
    # are 5-15 characters (partial lines). Exceeding this suggests bulk transfer.
    
    BURST_TYPING_MIN = 50  # characters
    BURST_TYPING_MAX = 100  # characters
    # Justification: Detects rapid continuous input (50-100 chars in short bursts).
    # Atypical for novice reflective workflows; indicates potential metric inflation
    # or non-cognitive key-mashing activity.
    
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
    DISENGAGEMENT_THRESHOLD = 120  # seconds (revised from 30s)
    # Justification: Idle detection standardized to 120 seconds. Novices require 
    # 30-120s post-error to parse messages and plan corrections. <30s = normal flow.
    # 30-120s + error context = reflective pause (valid). >120s = disengagement.

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
        
        # IMPORTANT: This analysis is STATELESS and evaluates CURRENT behavior only.
        # Each telemetry update gets a fresh evaluation. Previous flags don't carry over.
        # Small legitimate edits after a large insertion will return to INCREMENTAL_EDIT.
        
        # Default State (assume legitimate until proven otherwise)
        provenance = ProvenanceState.INCREMENTAL_EDIT
        integrity_penalty = 0.0
        
        raw_kpm = metrics.total_keystrokes / metrics.duration_minutes if metrics.duration_minutes > 0 else 0
        
        # Logic Tree: Large Insertions
        # Context: For novices solving short problems (250-500 chars), 30-char insertions
        # represent 6-12% of solution added at once, atypical for incremental construction
        # NOTE: Small edits (<30 chars) will skip this check and remain INCREMENTAL_EDIT
        if metrics.last_edit_size_chars > self.LARGE_INSERTION_THRESHOLD:
            # Calculate keystroke density: how many keystrokes were used to create the current code
            # If last_edit_size is 100 chars but only 10 keystrokes in recent window, likely pasted
            keystroke_to_insertion_ratio = metrics.recent_burst_size_chars / metrics.last_edit_size_chars if metrics.last_edit_size_chars > 0 else 0
            
            # STRICTER: Suspect paste ONLY if multiple strong indicators present
            # Must have: (1) Very low keystroke ratio (<20%) AND (2) Focus violations AND (3) Large edit (>50 chars)
            if (keystroke_to_insertion_ratio < 0.2 and 
                metrics.focus_violation_count > 0 and 
                metrics.last_edit_size_chars > 50):
                # Pattern: Very large insertion + tab-switch + extremely low keystroke density
                # Interpretation: Strong evidence of copy-paste from external source
                provenance = ProvenanceState.SUSPECTED_PASTE
                integrity_penalty = 0.5
            # Alternative: Large insertion with high keystroke efficiency
            elif keystroke_to_insertion_ratio > 0.8:
                # Pattern: Large insertion + high keystroke density (typed it)
                # Interpretation: Authentic refactoring/rewrite
                provenance = ProvenanceState.AUTHENTIC_REFACTORING
            else:
                # Pattern: Large insertion + moderate activity
                # Interpretation: Uncertain—could be internal block move/paste or fast typing
                provenance = ProvenanceState.AMBIGUOUS_EDIT

        # Logic Tree: Spam Check & Additional Paste Detection
        # Context: Novices typically achieve efficiency ratios of 0.20-0.40
        # due to trial-and-error. Ratios <0.05 suggest random key-mashing.
        efficiency_ratio = metrics.net_code_change / metrics.total_keystrokes if metrics.total_keystrokes > 50 else 1.0
        
        # Check for burst typing/spamming
        is_burst_typing = (self.BURST_TYPING_MIN <= metrics.recent_burst_size_chars <= self.BURST_TYPING_MAX)
        
        # Additional paste detection: VERY strict to avoid false positives
        # Only flag if there's EXTREME evidence: lots of code, very few keystrokes, multiple focus violations
        if (metrics.net_code_change > 200 and 
            metrics.total_keystrokes < metrics.net_code_change * 0.3 and 
            metrics.focus_violation_count > 2 and
            provenance not in [ProvenanceState.SUSPECTED_PASTE, ProvenanceState.SPAMMING]):
            # Pattern: Lots of code exists but extremely few keystrokes + multiple tab switches
            # Interpretation: Code was likely pasted in multiple chunks
            provenance = ProvenanceState.SUSPECTED_PASTE
            integrity_penalty = 0.5
        
        if metrics.total_keystrokes > self.SPAM_KEYSTROKE_MINIMUM and efficiency_ratio < self.SPAM_EFFICIENCY_THRESHOLD:
            # Detected: High keystroke volume with negligible code retention
            # Action: Nullify KPM contribution to prevent score inflation
            effective_kpm = 0.0
            provenance = ProvenanceState.SPAMMING
        elif is_burst_typing and efficiency_ratio < 0.15:
            # Detected: Burst typing pattern with low efficiency
            # Action: Flag as potential spamming/gaming behavior
            effective_kpm = raw_kpm * 0.5  # Apply 50% penalty
            if provenance == ProvenanceState.INCREMENTAL_EDIT:
                provenance = ProvenanceState.SPAMMING
        else:
            effective_kpm = raw_kpm


        # --- 2. ITERATION QUALITY (Figure 6) ---
        
        iteration = IterationState.NORMAL
        effective_runs = metrics.total_run_attempts
        
        # Logic Tree: Run Intervals
        # Context: Novices need ~10s minimum to process feedback and respond
        if metrics.last_run_interval_seconds < self.RAPID_ITERATION_THRESHOLD:
            # STRICTER: If last run had error AND rapid re-run, likely guessing regardless of changes
            # Exception: Only count as MICRO_ITERATION if semantic change AND no error (successful fix)
            if not metrics.is_semantic_change:
                # Pattern: Quick re-run + no logical change (whitespace only)
                # Interpretation: Reflexive guessing, not deliberate debugging
                iteration = IterationState.RAPID_GUESSING
                # Penalty: Discount 20% of run attempts (partial productivity credit)
                effective_runs = metrics.total_run_attempts * self.RAPID_GUESSING_PENALTY
            elif metrics.last_run_was_error:
                # Pattern: Quick re-run + has changes BUT previous run had error
                # Interpretation: Likely random trial-and-error without understanding
                # If truly debugging thoughtfully, would take >10s to read error and fix
                iteration = IterationState.RAPID_GUESSING
                effective_runs = metrics.total_run_attempts * self.RAPID_GUESSING_PENALTY
            else:
                # Pattern: Quick re-run + meaningful code change + no previous error
                # Interpretation: Valid fast-paced iteration (testing variations)
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