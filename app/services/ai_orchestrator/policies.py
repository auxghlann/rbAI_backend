"""
Policy definitions for scope validation and content filtering.
Defines what's in-scope vs out-of-scope for the pedagogical firewall.
"""

from typing import List, Pattern
import re


class ScopePolicy:
    """
    Defines what the AI tutor can and cannot help with.
    
    Philosophy: Guide learning, never give solutions.
    """
    
    # Keywords that indicate learning-oriented queries (IN SCOPE)
    LEARNING_KEYWORDS = [
        # Understanding
        "how", "why", "what", "explain", "understand", "confused",
        "difference", "between", "mean", "means",
        
        # Problem-solving
        "hint", "stuck", "help", "approach", "strategy", "think",
        "start", "beginning", "idea",
        
        # Debugging
        "error", "bug", "wrong", "not working", "issue", "problem",
        "debug", "fix", "fail",
        
        # Concepts
        "algorithm", "complexity", "time", "space", "data structure",
        "loop", "recursion", "variable", "function",
    ]
    
    # Patterns that indicate solution-seeking (BORDERLINE - needs LLM judgment)
    SOLUTION_SEEKING_PATTERNS: List[Pattern] = [
        re.compile(r"\b(write|code|implement|complete)\s+(the\s+)?(code|solution|function|program)", re.IGNORECASE),
        re.compile(r"\bgive\s+me\s+(the\s+)?(answer|solution|code)", re.IGNORECASE),
        re.compile(r"\bsolve\s+(this|the)\s+problem", re.IGNORECASE),
        re.compile(r"\bshow\s+me\s+(the\s+)?(solution|code|answer)", re.IGNORECASE),
    ]
    
    # Patterns clearly OUT OF SCOPE
    OUT_OF_SCOPE_PATTERNS: List[Pattern] = [
        # Non-programming
        re.compile(r"\b(weather|news|sports|recipe|movie|music)\b", re.IGNORECASE),
        
        # Unethical requests
        re.compile(r"\b(hack|cheat|steal|plagiarize|copy)\b", re.IGNORECASE),
        
        # Personal info
        re.compile(r"\b(personal|address|phone|email|password)\b", re.IGNORECASE),
        
        # Other domains
        re.compile(r"\b(medical|legal|financial)\s+advice\b", re.IGNORECASE),
    ]
    
    @classmethod
    def quick_filter(cls, user_query: str) -> tuple[bool, str]:
        """
        Fast pattern-based filtering before LLM validation.
        
        Returns:
            (is_allowed, reason)
        """
        query_lower = user_query.lower()
        
        # Check for clearly out-of-scope patterns
        for pattern in cls.OUT_OF_SCOPE_PATTERNS:
            if pattern.search(user_query):
                return False, "OUT_OF_SCOPE_DOMAIN"
        
        # Check for solution-seeking (flag for LLM review, don't auto-reject)
        for pattern in cls.SOLUTION_SEEKING_PATTERNS:
            if pattern.search(user_query):
                return True, "BORDERLINE_SOLUTION_SEEKING"  # Let LLM handle
        
        # Check for learning keywords (likely in scope)
        has_learning_keyword = any(
            keyword in query_lower for keyword in cls.LEARNING_KEYWORDS
        )
        
        if has_learning_keyword:
            return True, "LEARNING_ORIENTED"
        
        # Default: let LLM validate
        return True, "NEEDS_LLM_VALIDATION"


class InterventionPolicy:
    """
    Defines when and how the AI should intervene based on behavioral state.
    
    Integrates with FusionInsights from behavior_engine.
    """
    
    # Map cognitive states to intervention urgency
    INTERVENTION_URGENCY = {
        "ACTIVE": 0,                    # No intervention needed
        "REFLECTIVE_PAUSE": 1,          # Low urgency
        "PASSIVE_IDLE": 2,              # Medium urgency
        "DISENGAGEMENT": 3,             # HIGH urgency - active intervention
    }
    
    # Map provenance states to teaching adjustments
    PROVENANCE_CONCERNS = {
        "SUSPECTED_PASTE": "Ask student to explain the code",
        "SPAMMING": "Encourage thoughtful edits over random changes",
        "AMBIGUOUS_EDIT": "Help student understand their large changes",
    }
    
    @classmethod
    def should_intervene(cls, cognitive_state: str, iteration_state: str) -> bool:
        """
        Determine if proactive intervention is needed.
        
        Args:
            cognitive_state: From FusionInsights.cognitive_state
            iteration_state: From FusionInsights.iteration_state
            
        Returns:
            True if AI should proactively help (high urgency states)
        """
        urgency = cls.INTERVENTION_URGENCY.get(cognitive_state, 0)
        
        # Also intervene on problematic iteration patterns
        if iteration_state in ["RAPID_GUESSING", "MICRO_ITERATION"]:
            urgency = max(urgency, 2)
        
        return urgency >= 2  # Intervene on medium-high urgency
    
    @classmethod
    def get_intervention_tone(cls, cognitive_state: str) -> str:
        """Get appropriate tone for intervention"""
        if cognitive_state == "DISENGAGEMENT":
            return "encouraging_and_concrete"
        elif cognitive_state == "PASSIVE_IDLE":
            return "gentle_nudge"
        else:
            return "supportive"
