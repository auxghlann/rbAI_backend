from dataclasses import dataclass
from app.services.behavior_engine.data_fusion import FusionInsights

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
    last_edit_size_chars: int        # Needed for Provenance (Figure 5)
    last_run_interval_seconds: float # Needed for Iteration (Figure 6)
    is_semantic_change: bool         # Needed for Iteration (Figure 6)
    current_idle_duration: float     # Needed for Cognitive State (Figure 7)
    is_window_focused: bool          # Needed for Cognitive State (Figure 7)
    last_run_was_error: bool         # Needed for Cognitive State (Figure 7)

class CESCalculator:
    """
    Implements the Cognitive Engagement Score (CES) algorithm.
    Reference: Thesis Section 1.3.1
    """

    # ---------------------------------------------------------
    # 1. HEURISTIC THRESHOLDS (TUNED FOR PHASE 2)
    # ---------------------------------------------------------
    MIN_KPM = 5.0; MAX_KPM = 40.0
    MIN_AD = 0.05; MAX_AD = 0.5
    MIN_IR = 0.0; MAX_IR = 0.60
    MIN_FVC = 0; MAX_FVC = 10
    
    # ---------------------------------------------------------
    # 2. WEIGHTS (Thesis Section 1.3.1)
    # ---------------------------------------------------------
    W_KPM = 0.40
    W_AD  = 0.30
    W_IR  = 0.20
    W_FVC = 0.10

    def calculate(self, metrics: SessionMetrics, insights: FusionInsights) -> dict:
        """
        Computes CES using FUSED insights (Effective Metrics).
        """
        
        # --- USE FUSED "EFFECTIVE" DATA ---
        # The logic gates (Figures 5, 6, 7) have already filtered the data in 'insights'
        # We trust 'insights' to give us the CLEAN numbers.
        
        # 1. Normalize Effective KPM (Spam removed)
        kpm_norm = self._normalize(insights.effective_kpm, self.MIN_KPM, self.MAX_KPM)
        
        # 2. Normalize Effective AD (Rapid-guessing removed)
        ad_norm  = self._normalize(insights.effective_ad, self.MIN_AD, self.MAX_AD)
        
        # 3. Normalize Effective IR (Reflective pauses removed)
        ir_norm  = self._normalize(insights.effective_ir, self.MIN_IR, self.MAX_IR)
        
        # 4. Normalize FVC (Raw count)
        fvc_norm = self._normalize(metrics.focus_violation_count, self.MIN_FVC, self.MAX_FVC)

        # --- CALCULATE FINAL SCORE ---
        productive_score = (self.W_KPM * kpm_norm) + (self.W_AD * ad_norm)
        penalty_score    = (self.W_IR * ir_norm) + (self.W_FVC * fvc_norm)
        
        final_ces = productive_score - penalty_score

        # Apply Integrity Penalty (from Provenance Logic)
        final_ces -= insights.integrity_penalty

        # Clamp result (-1.0 to 1.0)
        final_ces = max(-1.0, min(1.0, final_ces))

        return {
            "ces_score": round(final_ces, 4),
            "grade_label": self._get_label(final_ces),
            
            # Since our Enums inherit from str, they serialize to JSON automatically!
            "pedagogical_states": {
                "provenance": insights.provenance_state, 
                "iteration": insights.iteration_state,
                "cognitive": insights.cognitive_state
            },
            "metrics_debug": {
                "kpm_effective": round(insights.effective_kpm, 2),
                "ad_effective": round(insights.effective_ad, 2),
                "ir_effective": round(insights.effective_ir, 2)
            }
        }

    def _normalize(self, value, min_val, max_val):
        if max_val - min_val == 0: return 0.0
        norm = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, norm))

    def _get_label(self, score):
        if score > 0.5: return "High Engagement"
        if score > 0.2: return "Moderate Engagement"
        if score > 0.0: return "Low Engagement"
        return "Disengaged/Suspicious"