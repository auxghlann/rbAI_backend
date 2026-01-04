"""
AI Orchestrator Module - Pedagogical Firewall for Learning Support

Provides Socratic tutoring while filtering out-of-scope requests.
Integrates with behavioral engine for context-aware interventions.
"""

from .firewall import PedagogicalFirewall
from .llm_client import LLMClient
from .llm_client_groq import LLMClientGroq

__all__ = ["PedagogicalFirewall", "LLMClient", "LLMClientGroq"]
