"""
Async Groq client wrapper using OpenAI compatibility layer.
Uses Groq's OpenAI-compatible API for fast inference with LPU architecture.
"""

import os
import logging
from dotenv import load_dotenv
from typing import Optional, AsyncGenerator, List, Dict
from openai import AsyncOpenAI
from openai import APIError, RateLimitError, APITimeoutError

logger = logging.getLogger(__name__)

load_dotenv()

class LLMClientGroq:
    """
    Async wrapper for Groq API using OpenAI compatibility.
    
    Design principles:
    - Token-efficient: Uses Groq's llama models optimized for LPU
    - Fast: Async for non-blocking operations + Groq's ultra-low latency
    - Resilient: Basic retry logic for transient failures
    - Observable: Comprehensive logging
    
    Popular Groq models:
    - llama-3.3-70b-versatile: Best for complex reasoning
    - llama-3.1-8b-instant: Fastest, good for simple tasks
    - mixtral-8x7b-32768: Large context window
    - gemma2-9b-it: Google's Gemma model
    """
    
    # Token limits (conservative for cost management)
    MAX_INPUT_TOKENS = 1000   # Limit context size
    MAX_OUTPUT_TOKENS = 500   # Sufficient for detailed explanations with code examples
    
    def __init__(self, api_key: Optional[str] = None, model: str = "openai/gpt-oss-120b"):
        """
        Initialize Groq client using OpenAI compatibility.
        
        Args:
            api_key: Groq API key (defaults to GROQ_API_KEY env var)
            model: Model to use (default: llama-3.3-70b-versatile for balanced performance)
        """
        self.api_key = api_key or os.getenv("GROQ_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Groq API key required. Set GROQ_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        # Use OpenAI client with Groq's base URL
        self.client = AsyncOpenAI(
            base_url="https://api.groq.com/openai/v1",
            api_key=self.api_key
        )
        self.model = model
        
        logger.info(f"LLMClientGroq initialized with model: {model}")
    
    async def complete(
        self,
        system_prompt: str,
        user_prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> str:
        """
        Generate completion with token management, chat history, and retry logic.
        
        Args:
            system_prompt: System instructions
            user_prompt: User query
            chat_history: Previous conversation messages for context
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
        
        # Build messages with chat history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history if provided (for context)
        if chat_history:
            messages.extend(chat_history)
        
        # Add current user query
        messages.append({"role": "user", "content": user_prompt})
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Requesting Groq completion (attempt {attempt + 1}/{max_retries + 1})")
                
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
                    f"Groq completion successful - Tokens: {usage.prompt_tokens} in, "
                    f"{usage.completion_tokens} out, {usage.total_tokens} total"
                )
                
                return content
                
            except RateLimitError as e:
                logger.warning(f"Groq rate limit hit (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise RuntimeError("Groq rate limit exceeded. Try again later.")
                # Exponential backoff would go here in production
                
            except APITimeoutError as e:
                logger.warning(f"Groq timeout (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise RuntimeError("Groq request timed out. Try again later.")
                    
            except APIError as e:
                logger.error(f"Groq API error: {e}")
                raise RuntimeError(f"AI service error: {str(e)}")
                
            except Exception as e:
                logger.error(f"Unexpected error in Groq LLM completion: {e}")
                raise RuntimeError(f"Failed to generate response: {str(e)}")
        
        raise RuntimeError("Failed to get Groq completion after all retries")
    
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
            logger.debug(f"Groq scope validation result: {result}")
            
            return "IN_SCOPE" in result
            
        except Exception as e:
            logger.error(f"Groq scope validation failed: {e}")
            # Fail open: allow request through if validation fails
            return True
    
    async def stream_complete(
        self,
        system_prompt: str,
        user_prompt: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Generate streaming completion for real-time UX with chat history.
        
        Yields response chunks as they're generated, similar to ChatGPT's
        streaming interface. Provides better user experience for longer responses.
        
        Args:
            system_prompt: System instructions
            user_prompt: User query
            chat_history: Previous conversation messages for context
            temperature: Sampling temperature (0.7 for balanced creativity)
            
        Yields:
            String chunks as they're generated
            
        Raises:
            RuntimeError: If streaming fails
        """
        # Validate token budget
        estimated_input_tokens = (len(system_prompt) + len(user_prompt)) // 4
        if estimated_input_tokens > self.MAX_INPUT_TOKENS:
            logger.warning(
                f"Input may exceed token budget: ~{estimated_input_tokens} tokens "
                f"(limit: {self.MAX_INPUT_TOKENS})"
            )
        
        # Build messages with chat history
        messages = [{"role": "system", "content": system_prompt}]
        
        # Add chat history if provided (for context)
        if chat_history:
            messages.extend(chat_history)
        
        # Add current user query
        messages.append({"role": "user", "content": user_prompt})
        
        try:
            logger.debug("Requesting streaming Groq completion")
            
            # Create streaming response
            stream = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=self.MAX_OUTPUT_TOKENS,
                stream=True,  # Enable streaming
                timeout=30.0,  # Longer timeout for streaming
            )
            
            # Yield chunks as they arrive
            async for chunk in stream:
                if chunk.choices and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    if delta.content:
                        yield delta.content
            
            logger.info("Groq streaming completion successful")
            
        except RateLimitError as e:
            logger.warning(f"Groq rate limit hit during streaming: {e}")
            raise RuntimeError("Rate limit exceeded. Please try again later.")
            
        except APITimeoutError as e:
            logger.warning(f"Groq timeout during streaming: {e}")
            raise RuntimeError("Request timed out. Please try again.")
            
        except APIError as e:
            logger.error(f"Groq API error during streaming: {e}")
            raise RuntimeError(f"AI service error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Unexpected error in Groq streaming: {e}")
            raise RuntimeError(f"Failed to stream response: {str(e)}")
    
    async def complete_with_function_calling(
        self,
        system_prompt: str,
        user_prompt: str,
        tools: List[Dict],
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> Dict:
        """
        Generate completion with function/tool calling for structured outputs.
        
        Used for scenarios where you need the LLM to generate structured data
        conforming to a schema (e.g., activity generation, data extraction).
        
        Args:
            system_prompt: System instructions
            user_prompt: User query
            tools: List of tool/function definitions (OpenAI format)
            temperature: Sampling temperature (0.7 for balanced creativity)
            max_retries: Number of retry attempts on failure
            
        Returns:
            Dictionary containing the function call name and parsed arguments
            
        Raises:
            RuntimeError: If all retries fail or no function call generated
        """
        # Validate token budget
        estimated_input_tokens = (len(system_prompt) + len(user_prompt)) // 4
        if estimated_input_tokens > self.MAX_INPUT_TOKENS:
            logger.warning(
                f"Input may exceed token budget: ~{estimated_input_tokens} tokens "
                f"(limit: {self.MAX_INPUT_TOKENS})"
            )
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        for attempt in range(max_retries + 1):
            try:
                logger.debug(f"Requesting Groq function calling (attempt {attempt + 1}/{max_retries + 1})")
                
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    tools=tools,
                    tool_choice="required",  # Force function calling
                    temperature=temperature,
                    max_tokens=4000,  # Higher limit for structured generation
                    timeout=15.0,
                )
                
                message = response.choices[0].message
                
                if not message.tool_calls:
                    raise RuntimeError("LLM did not generate function call")
                
                # Extract function call
                function_call = message.tool_calls[0]
                
                # Log token usage
                usage = response.usage
                logger.info(
                    f"Groq function calling successful - Tokens: {usage.prompt_tokens} in, "
                    f"{usage.completion_tokens} out, {usage.total_tokens} total"
                )
                
                return {
                    "name": function_call.function.name,
                    "arguments": function_call.function.arguments
                }
                
            except RateLimitError as e:
                logger.warning(f"Groq rate limit hit (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise RuntimeError("Groq rate limit exceeded. Try again later.")
                    
            except APITimeoutError as e:
                logger.warning(f"Groq timeout (attempt {attempt + 1}): {e}")
                if attempt == max_retries:
                    raise RuntimeError("Groq request timed out. Try again later.")
                    
            except APIError as e:
                logger.error(f"Groq API error: {e}")
                raise RuntimeError(f"AI service error: {str(e)}")
                
            except Exception as e:
                logger.error(f"Unexpected error in Groq function calling: {e}")
                raise RuntimeError(f"Failed to generate structured response: {str(e)}")
        
        raise RuntimeError("Failed to get Groq function call after all retries")
