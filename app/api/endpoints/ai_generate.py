"""
AI Activity Generation Endpoint
Uses LLM function calling to generate structured activity data
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional
import json
import os
from app.services.ai_orchestrator.llm_client_groq import LLMClientGroq

router = APIRouter()

# Initialize modular LLM client
# Uses llama-3.3-70b-versatile for balanced performance in activity generation
client = LLMClientGroq(model="llama-3.3-70b-versatile")


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

        # Call LLM with function calling using modular client
        function_call_result = await client.complete_with_function_calling(
            system_prompt=system_prompt,
            user_prompt=request.prompt,
            tools=[ACTIVITY_GENERATION_TOOL],
            temperature=0.7
        )

        # Parse the function call arguments
        generated_data = json.loads(function_call_result["arguments"])

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


# Note: To use a different model (e.g., for different capabilities or costs),
# you can create another client instance:
# client_fast = LLMClientGroq(model="llama-3.1-8b-instant")  # Faster, simpler tasks
# client_large = LLMClientGroq(model="mixtral-8x7b-32768")   # Larger context window
