from app.services.behavior_engine.metrics import SessionMetrics
from app.services.behavior_engine.data_fusion import FusionInsights

class CESCalculator:
    """
    Implements the Cognitive Engagement Score (CES) algorithm.
    Reference: Thesis Section 1.3.1
    
    Domain Context (Thesis Section 1.1.1):
    - Target Population: Novice programmers (Programming 1-2 level)
    - Problem Type: LeetCode-style algorithmic exercises (20-80 LOC)
    - Session Duration: 15-60 minutes per problem
    
    Thresholds calibrated specifically for this domain and validated
    through evolutionary prototyping (Phase 2-3, Section 2).
    """

    # ---------------------------------------------------------
    # 1. HEURISTIC THRESHOLDS (BEING TUNED FOR PHASE 2)
    # ---------------------------------------------------------
    
    # KPM: Keystrokes Per Minute
    MIN_KPM = 5.0 
    # Rationale: Lower bound for demonstrable engagement. Below this threshold
    # indicates disengagement vs. deliberation. Values below 5.0 indicate 
    # insufficient activity for novices in short-form algorithmic tasks.
    
    MAX_KPM = 24.0
    # Rationale: Upper bound for authentic manual typing (session average).
    # Values above 24.0 exceed realistic sustained manual entry for novices
    # in algorithmic problem-solving contexts.
    
    # AD: Attempt Density (Runs per Minute)
    MIN_AD = 0.05
    # Rationale: Minimum threshold = 1 run per 20 minutes. Below this indicates
    # lack of iterative testing or extremely slow problem-solving pace.
    
    MAX_AD = 0.50
    # Rationale: Maximum threshold = 1 run per 2 minutes. Higher rates suggest
    # excessive trial-and-error or rapid-fire guessing (already filtered by
    # DataFusionEngine, but capped here for normalization stability).
    
    # Idle Ratio (IR)
    MIN_IR = 0.0
    MAX_IR = 0.60
    # Rationale: Penalizes sessions where >60% of time is idle. For focused
    # problem-solving, idle time should not dominate active work. Reflective
    # pauses (post-error deliberation) are already excluded by DataFusionEngine.
    
    # FVC: Focus Violation Count
    MIN_FVC = 0
    MAX_FVC = 10
    # Rationale: Caps penalty at 10 violations per session to prevent outlier
    # skewing. For 30-60 minute sessions, >10 tab switches suggests severe
    # multitasking or integrity concerns, but additional violations beyond
    # this point provide diminishing diagnostic value.
    
    # ---------------------------------------------------------
    # 2. WEIGHTS (Thesis Section 1.3.1)
    # ---------------------------------------------------------
    W_KPM = 0.40
    # Justification: Keystroke activity is the primary indicator of active
    # code composition. Weighted highest as it is prerequisite for all work.
    
    W_AD  = 0.30
    # Justification: Run attempts reflect iterative problem-solving effort.
    # Secondary to keystrokes as testing follows creation, but critical for
    # measuring debugging persistence.
    
    W_IR  = 0.20
    # Justification: Idle time is ambiguous (could be thinking vs. distraction).
    # Conservative weight avoids over-penalizing thoughtful pauses while still
    # capturing disengagement patterns.
    
    W_FVC = 0.10
    # Justification: Focus violations have high signal noise (legitimate
    # documentation lookup vs. cheating). Lowest weight minimizes false
    # positive impact while retaining integrity monitoring capability.

    def calculate(self, metrics: SessionMetrics, insights: FusionInsights) -> dict:
        """
        Computes CES using FUSED insights (Effective Metrics).
        
        Process Flow:
        1. DataFusionEngine (Figure 4) has already filtered raw telemetry:
           - Spam keystrokes removed from KPM
           - Rapid-guessing runs discounted from AD
           - Reflective pauses excluded from IR
        2. This function normalizes the CLEANED metrics and applies weights
        3. Final CES represents net productive engagement (-1.0 to 1.0)
        
        Args:
            metrics: Raw session telemetry (for FVC, which is not adjusted)
            insights: Fused behavioral insights with effective metrics
        
        Returns:
            dict containing:
            - ces_score: Final engagement score (-1.0 to 1.0)
            - grade_label: Human-readable classification
            - pedagogical_states: Qualitative behavior flags
            - metrics_debug: Effective metric values for transparency
        """
        
        # --- USE FUSED "EFFECTIVE" DATA ---
        # The logic gates (Figures 5, 6, 7) have already filtered the data in 'insights'
        # We trust 'insights' to give us the CLEAN numbers.
        
        # 1. Normalize Effective KPM (Spam removed by DataFusionEngine)
        kpm_norm = self._normalize(insights.effective_kpm, self.MIN_KPM, self.MAX_KPM)
        
        # 2. Normalize Effective AD (Rapid-guessing discounted by DataFusionEngine)
        ad_norm  = self._normalize(insights.effective_ad, self.MIN_AD, self.MAX_AD)
        
        # 3. Normalize Effective IR (Reflective pauses excluded by DataFusionEngine)
        ir_norm  = self._normalize(insights.effective_ir, self.MIN_IR, self.MAX_IR)
        
        # 4. Normalize FVC (Raw count - not adjusted by fusion logic)
        fvc_norm = self._normalize(metrics.focus_violation_count, self.MIN_FVC, self.MAX_FVC)

        # --- CALCULATE FINAL SCORE ---
        # Productive Vector: Keystrokes + Run Attempts (positive contribution)
        productive_score = (self.W_KPM * kpm_norm) + (self.W_AD * ad_norm)
        
        # Disengagement Vector: Idle Time + Focus Violations (negative contribution)
        penalty_score    = (self.W_IR * ir_norm) + (self.W_FVC * fvc_norm)
        
        # Net Engagement = Productivity - Penalties
        final_ces = productive_score - penalty_score

        # Apply Integrity Penalty (from Provenance Logic, Figure 5)
        # e.g., SUSPECTED_PASTE adds 0.5 penalty, further reducing CES
        final_ces -= insights.integrity_penalty

        # Clamp result to valid range (-1.0 to 1.0)
        final_ces = max(-1.0, min(1.0, final_ces))

        return {
            # Basic metrics (needed by telemetry endpoint)
            "kpm": round(insights.effective_kpm, 2),
            "ad": round(insights.effective_ad, 4),
            "ir": round(insights.effective_ir, 2),
            
            # CES Score (needed by telemetry endpoint)
            "ces": round(final_ces, 4),
            "classification": self._get_label(final_ces),
            
            # Legacy keys for backward compatibility
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
                "ad_effective": round(insights.effective_ad, 4),
                "ir_effective": round(insights.effective_ir, 2)
            }
        }

    def _normalize(self, value, min_val, max_val):
        """
        Min-Max normalization to [0, 1] scale.
        
        Ensures all metrics (KPM, AD, IR, FVC) are dimensionless and comparable
        despite having vastly different raw scales (e.g., keystrokes vs. counts).
        
        Args:
            value: Raw metric value
            min_val: Minimum expected value (maps to 0.0)
            max_val: Maximum expected value (maps to 1.0)
        
        Returns:
            Normalized value clamped to [0.0, 1.0]
        """
        if max_val - min_val == 0: 
            return 0.0
        norm = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, norm))

    def _get_label(self, score):
        """
        Maps continuous CES score to qualitative engagement classification.
        
        Thresholds based on Table 3 (Thesis Section 1.3.1):
        - High Engagement (>0.50): Sustained productivity, fluid coding
        - Moderate Engagement (0.20-0.50): Steady progress with pauses
        - Low Engagement (0.00-0.20): Minimal activity, hesitation
        - Disengaged/Suspicious (≤0.00): Dominated by penalties/integrity flags
        """
        if score > 0.5: return "High Engagement"
        if score > 0.2: return "Moderate Engagement"
        if score > 0.0: return "Low Engagement"
        return "Disengaged/Suspicious"