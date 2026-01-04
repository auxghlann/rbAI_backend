"""
AI Activity Generation Endpoint
Uses LLM function calling to generate structured activity data
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import json
from groq import Groq
import os

router = APIRouter()

# Initialize Groq client (you can also use OpenAI, Anthropic, etc.)
# Make sure to set GROQ_API_KEY in your environment
client = Groq(api_key=os.getenv("GROQ_API_KEY", ""))


# Request/Response Models
class GenerateActivityRequest(BaseModel):
    prompt: str = Field(..., description="Description of the activity to generate")


class TestCaseSchema(BaseModel):
    name: str
    input: str
    expectedOutput: str
    isHidden: bool = False


class GeneratedActivity(BaseModel):
    title: str
    description: str
    problemStatement: str
    starterCode: str
    testCases: List[TestCaseSchema]
    hints: Optional[List[str]] = None


# Function/Tool Definition for LLM
ACTIVITY_GENERATION_TOOL = {
    "type": "function",
    "function": {
        "name": "generate_coding_activity",
        "description": "Generate a structured coding activity with problem statement, starter code, test cases, and hints",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Concise activity title (e.g., 'Binary Search Algorithm')"
                },
                "description": {
                    "type": "string",
                    "description": "Brief one-sentence description of what students will learn"
                },
                "problemStatement": {
                    "type": "string",
                    "description": "Detailed problem statement in Markdown format. Include: problem description, examples with input/output, and requirements. Use proper markdown formatting with headers, code blocks, etc."
                },
                "starterCode": {
                    "type": "string",
                    "description": "Python starter code with function signature and basic structure. Should guide students but not solve the problem."
                },
                "testCases": {
                    "type": "array",
                    "description": "Array of test cases to validate the solution",
                    "items": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Descriptive name for the test case"
                            },
                            "input": {
                                "type": "string",
                                "description": "Input parameters as a string (e.g., '5, 3' or '[1,2,3]')"
                            },
                            "expectedOutput": {
                                "type": "string",
                                "description": "Expected output as a string"
                            },
                            "isHidden": {
                                "type": "boolean",
                                "description": "Whether this test case should be hidden from students",
                                "default": False
                            }
                        },
                        "required": ["name", "input", "expectedOutput"]
                    },
                    "minItems": 2
                },
                "hints": {
                    "type": "array",
                    "description": "Optional array of progressive hints to help students",
                    "items": {
                        "type": "string"
                    }
                }
            },
            "required": ["title", "description", "problemStatement", "starterCode", "testCases"]
        }
    }
}


@router.post("/generate-activity", response_model=GeneratedActivity)
async def generate_activity(request: GenerateActivityRequest):
    """
    Generate a coding activity using AI with function calling.
    
    The LLM will be instructed to generate structured data matching
    the Activity schema using function calling.
    """
    try:
        # Create the system prompt for activity generation
        system_prompt = """You are an expert computer science educator specializing in creating programming exercises.
Your task is to generate high-quality coding activities for students learning Python.

When creating activities:
- Make problem statements clear and educational
- Include realistic examples with input/output
- Write starter code that guides without solving
- Create comprehensive test cases (visible and hidden)
- Provide progressive hints that don't give away the solution
- Use proper Markdown formatting for problem statements
- Ensure test cases actually validate the solution

Generate activities appropriate for the requested difficulty level and topic."""

        # Call LLM with function calling
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",  # or "mixtral-8x7b-32768"
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            tools=[ACTIVITY_GENERATION_TOOL],
            tool_choice="required",  # Force the model to use the function
            temperature=0.7,
            max_tokens=4000
        )

        # Extract function call result
        message = response.choices[0].message
        
        if not message.tool_calls:
            raise HTTPException(
                status_code=500,
                detail="LLM did not generate activity using function calling"
            )

        # Parse the function call arguments
        function_call = message.tool_calls[0]
        generated_data = json.loads(function_call.function.arguments)

        # Validate and return
        activity = GeneratedActivity(**generated_data)
        return activity

    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse LLM response: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Activity generation failed: {str(e)}"
        )


@router.post("/generate-activity-openai", response_model=GeneratedActivity)
async def generate_activity_openai(request: GenerateActivityRequest):
    """
    Alternative implementation using OpenAI (if you prefer)
    """
    try:
        from openai import OpenAI
        
        openai_client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        system_prompt = """You are an expert computer science educator creating Python programming exercises."""
        
        response = openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.prompt}
            ],
            tools=[ACTIVITY_GENERATION_TOOL],
            tool_choice={"type": "function", "function": {"name": "generate_coding_activity"}},
            temperature=0.7
        )
        
        function_call = response.choices[0].message.tool_calls[0]
        generated_data = json.loads(function_call.function.arguments)
        
        return GeneratedActivity(**generated_data)
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"OpenAI generation failed: {str(e)}"
        )
