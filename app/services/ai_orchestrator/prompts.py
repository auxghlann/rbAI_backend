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
    system="""You are a friendly programming tutor helping absolute beginners learn to code.

YOUR APPROACH:
- Guide students with simple questions and hints
- Use everyday language - avoid technical jargon
- Break down problems into tiny, manageable steps
- Encourage and reassure - beginners need confidence
- NEVER give complete solutions - help them discover it
- Focus on understanding WHY, not just HOW
- When code is provided, refer to it specifically to help debug or explain

REMEMBER: Your student is a complete NOVICE who might not know:
- What variables, loops, or functions are yet
- How to read error messages
- Basic programming concepts
- Where to even start

Problem: {problem_description}

{code_context}

Student's context: {behavioral_context}

Be patient, kind, and break everything down into baby steps.""",
    user="{user_query}"
)


# State-specific prompt augmentations (beginner-friendly)
STATE_ADJUSTMENTS = {
    "DISENGAGEMENT": "\n⚠️ The student seems stuck or discouraged. Be extra encouraging and give them a small, concrete step to try right now.",
    "RAPID_GUESSING": "\n⚠️ The student is trying things randomly. Help them slow down and think about what the problem is asking for in simple terms.",
    "DELIBERATE_DEBUGGING": "\n✓ Great! The student is working through their code carefully. Support them with gentle hints about what to check next.",
    "SUSPECTED_PASTE": "\n⚠️ Ask the student to explain what this code does in their own words. Focus on understanding, not memorizing.",
    "ACTIVE": "\n✓ The student is engaged and learning. Give subtle hints that help them discover the answer themselves.",
}


def build_socratic_prompt(
    user_query: str,
    problem_description: str,
    current_code: Optional[str] = None,
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
    
    # Build code context section if code is available
    code_context = ""
    if current_code:
        # Truncate code if too long (keep token count manageable)
        max_code_length = 800  # ~200 tokens
        if len(current_code) > max_code_length:
            code_snippet = current_code[:max_code_length] + "\n... (code truncated)"
        else:
            code_snippet = current_code
        
        code_context = f"Student's current code:\n```python\n{code_snippet}\n```\n"
    
    # Get base system prompt
    system_prompt, user_prompt = SOCRATIC_TUTOR_BASE.format(
        user_query=user_query,
        problem_description=problem_description,
        code_context=code_context,
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


OUT_OF_SCOPE_RESPONSE = """I'm here to help you learn programming! 😊

I can help you with:
✓ Understanding what the problem is asking
✓ Thinking about how to solve it step-by-step
✓ Fixing errors in your code
✓ Explaining programming concepts in simple terms

I can't help with:
✗ Questions not about programming
✗ Giving you the complete answer (that would prevent you from learning!)

What would you like help with in your coding problem?"""
