"""
Lightweight prompt template system for token-efficient AI interactions.
No external dependencies - simple string formatting with validation.
"""

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class PromptTemplate:
    """Simple template with variable injection"""
    system: str
    user: str
    
    def format(self, **kwargs) -> tuple[str, str]:
        """Format both system and user prompts with provided variables"""
        try:
            system_msg = self.system.format(**kwargs)
            user_msg = self.user.format(**kwargs)
            return system_msg, user_msg
        except KeyError as e:
            raise ValueError(f"Missing required template variable: {e}")


# --- CORE PROMPT TEMPLATES ---

SCOPE_VALIDATOR = PromptTemplate(
    system="""You are a scope validator. Determine if the user's request is about:
1. Getting help with algorithmic/coding problems
2. Understanding code concepts, debugging, or learning
3. Asking for hints or explanations

Respond with ONLY 'IN_SCOPE' or 'OUT_OF_SCOPE'. No explanations.""",
    user="{user_query}"
)


SOCRATIC_TUTOR_BASE = PromptTemplate(
    system="""You are a Socratic programming tutor for novice learners solving algorithmic puzzles.

STRICT RULES:
- NEVER give direct solutions or complete code
- Ask guiding questions that prompt thinking
- Give hints about approach, not implementation
- Keep responses under 100 tokens
- Use simple language for beginners

Context:
- Problem: {problem_description}
- Behavioral State: {behavioral_context}

Adapt your tone based on the learner's state.""",
    user="{user_query}"
)


# State-specific prompt augmentations (token-efficient)
STATE_ADJUSTMENTS = {
    "DISENGAGEMENT": "\n⚠️ INTERVENTION MODE: Student appears disengaged. Be more encouraging and provide a concrete starting point.",
    "RAPID_GUESSING": "\n⚠️ Student is guessing rapidly. Slow them down with a reflective question about their approach.",
    "DELIBERATE_DEBUGGING": "\n✓ Student is debugging methodically. Support their process with targeted debugging hints.",
    "SUSPECTED_PASTE": "\n⚠️ CRITICAL: Suspected code paste. Ask them to explain the code in their own words.",
    "ACTIVE": "\n✓ Student is actively engaged. Provide subtle hints to maintain flow.",
}


def build_socratic_prompt(
    user_query: str,
    problem_description: str,
    cognitive_state: Optional[str] = None,
    iteration_state: Optional[str] = None,
    provenance_state: Optional[str] = None,
) -> tuple[str, str]:
    """
    Build context-aware Socratic prompt with behavioral integration.
    
    Keeps token count low by only including relevant state information.
    """
    # Start with base behavioral context
    behavioral_parts = []
    
    if cognitive_state:
        behavioral_parts.append(f"Cognitive: {cognitive_state}")
        
    if iteration_state and iteration_state != "NORMAL":
        behavioral_parts.append(f"Iteration: {iteration_state}")
        
    if provenance_state and provenance_state != "INCREMENTAL_EDIT":
        behavioral_parts.append(f"Code Pattern: {provenance_state}")
    
    behavioral_context = ", ".join(behavioral_parts) if behavioral_parts else "Normal engagement"
    
    # Get base system prompt
    system_prompt, user_prompt = SOCRATIC_TUTOR_BASE.format(
        user_query=user_query,
        problem_description=problem_description,
        behavioral_context=behavioral_context
    )
    
    # Augment with state-specific guidance (token-efficient)
    primary_state = (
        provenance_state if provenance_state in ["SUSPECTED_PASTE", "SPAMMING"]
        else iteration_state if iteration_state == "RAPID_GUESSING"
        else cognitive_state
    )
    
    if primary_state and primary_state in STATE_ADJUSTMENTS:
        system_prompt += STATE_ADJUSTMENTS[primary_state]
    
    return system_prompt, user_prompt


OUT_OF_SCOPE_RESPONSE = """I'm specifically designed to help you learn algorithmic problem-solving. 

I can help you with:
✓ Understanding the problem
✓ Thinking through your approach
✓ Debugging your code
✓ Learning concepts

I cannot help with:
✗ Non-programming questions
✗ Complete solutions
✗ Unrelated tasks

Please ask about your coding problem, and I'll guide you!"""
