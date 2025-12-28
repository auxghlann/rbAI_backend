"""
Async OpenAI client wrapper with token management and error handling.
Lightweight implementation without LangChain overhead.
"""

import os
import logging
from typing import Optional
from openai import AsyncOpenAI
from openai import APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)


class LLMClient:
    """
    Async wrapper for OpenAI API with token budget management.
    
    Design principles:
    - Token-efficient: Uses gpt-4o-mini for cost optimization
    - Fast: Async for non-blocking operations
    - Resilient: Basic retry logic for transient failures
    - Observable: Comprehensive logging
    """
    
    # Token limits (conservative for cost management)
    MAX_INPUT_TOKENS = 1000   # Limit context size
    MAX_OUTPUT_TOKENS = 150   # Keep responses concise (Socratic hints)
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini"):
        """
        Initialize OpenAI client.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (default: gpt-4o-mini for cost efficiency)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError(
                "OpenAI API key required. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        self.model = model
        
        logger.info(f"LLMClient initialized with model: {model}")
    
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> str:
        """
        Generate completion with token management and retry logic.
        
        Args:
            system_prompt: System instructions
            user_prompt: User query
            temperature: Sampling temperature (0.7 for balanced creativity)
            max_retries: Number of retry attempts on failure
            
        Returns:
            Generated response text
            
        Raises:
            RuntimeError: If all retries fail
        """
        # Validate token budget (rough estimation: ~4 chars per token)
        estimated_input_tokens = (len(system_prompt) + len(user_prompt)) // 4
        if estimated_input_tokens > self.MAX_INPUT_TOKENS:
            logger.warning(
                f"Input may exceed token budget: ~{estimated_input_tokens} tokens "
                f"(limit: {self.MAX_INPUT_TOKENS})"
            )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Requesting completion (attempt {attempt + 1}/{max_retries + 1})")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=self.MAX_OUTPUT_TOKENS,
                    timeout=10.0,  # 10 second timeout
                )
                
                # Extract response
                content = response.choices[0].message.content
                
                # Log token usage for monitoring
                usage = response.usage
                logger.info(
                    f"Completion successful - Tokens: {usage.prompt_tokens} in, "
                    f"{usage.completion_tokens} out, {usage.total_tokens} total"
                )
                
                return content
                
            except RateLimitError as e:
                logger.warning(f"Rate limit hit (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise RuntimeError("OpenAI rate limit exceeded. Try again later.")
                # Exponential backoff would go here in production
                
            except APITimeoutError as e:
                logger.warning(f"Timeout (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise RuntimeError("OpenAI request timed out. Try again later.")
                    
            except APIError as e:
                logger.error(f"OpenAI API error: {e}")
                raise RuntimeError(f"AI service error: {str(e)}")
                
            except Exception as e:
                logger.error(f"Unexpected error in LLM completion: {e}")
                raise RuntimeError(f"Failed to generate response: {str(e)}")
        
        raise RuntimeError("Failed to get completion after all retries")
    
    async def validate_scope(self, user_query: str, validator_prompt: tuple[str, str]) -> bool:
        """
        Quick scope validation (optimized for low token usage).
        
        Args:
            user_query: User's question/request
            validator_prompt: (system, user) prompt tuple
            
        Returns:
            True if in scope, False otherwise
        """
        system_prompt, user_template = validator_prompt
        
        try:
            response = await self.complete(
                system_prompt=system_prompt,
                user_prompt=user_template.format(user_query=user_query),
                temperature=0.0,  # Deterministic for validation
            )
            
            result = response.strip().upper()
            logger.debug(f"Scope validation result: {result}")
            
            return "IN_SCOPE" in result
            
        except Exception as e:
            logger.error(f"Scope validation failed: {e}")
            # Fail open: allow request through if validation fails
            return True
