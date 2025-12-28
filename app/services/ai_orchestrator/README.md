# Pedagogical Firewall - AI Orchestrator

## 🎯 Overview
The pedagogical firewall provides **Socratic tutoring** for novice programmers learning algorithmic problem-solving. It filters out-of-scope requests and adapts responses based on behavioral telemetry.

## 🏗️ Architecture

```
ai_orchestrator/
├── __init__.py           # Module exports
├── firewall.py           # Main orchestration logic
├── llm_client.py         # Async OpenAI wrapper
├── prompts.py            # Prompt templates
└── policies.py           # Scope validation & intervention rules
```

### Design Principles
- **Stateless**: Each request is independent (no conversation history)
- **Token-efficient**: Optimized for cost (<150 tokens per response)
- **Behaviorally-aware**: Integrates with FusionInsights from behavior_engine
- **Safe**: Filters harmful and out-of-scope requests

## 🔥 Key Components

### 1. **PedagogicalFirewall** (`firewall.py`)
Main orchestrator that:
- Validates request scope (quick policy filter + LLM validation)
- Integrates behavioral context (CognitiveState, IterationState, ProvenanceState)
- Generates Socratic responses (hints, not solutions)
- Triggers interventions for struggling students

### 2. **LLMClient** (`llm_client.py`)
Async OpenAI wrapper with:
- Token budget management (max 1000 input, 150 output)
- Retry logic for transient failures
- Comprehensive logging
- Uses `gpt-4o-mini` for cost efficiency

### 3. **Prompt Templates** (`prompts.py`)
Lightweight string-based templates with:
- Scope validator (IN_SCOPE vs OUT_OF_SCOPE)
- Socratic tutor base prompt
- State-specific augmentations (intervention modes)

### 4. **Policies** (`policies.py`)
- **ScopePolicy**: Pattern-based filtering (learning-oriented vs solution-seeking)
- **InterventionPolicy**: Behavioral state → teaching adjustments

## 📡 API Endpoints

### `POST /api/chat/ask`
Get Socratic tutoring help.

**Request:**
```json
{
  "session_id": "abc123",
  "problem_id": "two-sum",
  "problem_description": "Find two numbers that add up to target...",
  "user_query": "I'm confused about how to approach this problem",
  "behavioral_context": {
    "cognitive_state": "ACTIVE",
    "iteration_state": "NORMAL",
    "provenance_state": "INCREMENTAL_EDIT"
  },
  "current_code": "def two_sum(nums, target):\n    ..."
}
```

**Response:**
```json
{
  "message": "Great question! Let's think about this step-by-step. What data structure could help you quickly check if a number exists?",
  "is_allowed": true,
  "intervention_triggered": false,
  "timestamp": "2025-12-15T10:30:00Z"
}
```

### `POST /api/chat/hint`
Get proactive hint when stuck.

**Query Parameters:**
- `session_id`: Session identifier
- `problem_id`: Problem identifier
- `problem_description`: Problem statement
- `current_code`: (Optional) Current code attempt
- `cognitive_state`: (Optional) Current cognitive state

**Response:**
```json
{
  "message": "You're on the right track! Try thinking about what happens if you store numbers you've already seen...",
  "is_allowed": true,
  "intervention_triggered": true,
  "timestamp": "2025-12-15T10:31:00Z"
}
```

### `GET /api/chat/health`
Check service status.

## 🧠 Behavioral Integration

The firewall adapts responses based on **FusionInsights** states:

| Cognitive State | Intervention | Response Style |
|----------------|--------------|----------------|
| `ACTIVE` | None | Subtle hints, maintain flow |
| `REFLECTIVE_PAUSE` | Low | Gentle nudge |
| `PASSIVE_IDLE` | Medium | Proactive encouragement |
| `DISENGAGEMENT` | **HIGH** | Concrete starting point, encouraging |

| Iteration State | Adaptation |
|-----------------|------------|
| `RAPID_GUESSING` | Slow down with reflective questions |
| `DELIBERATE_DEBUGGING` | Support debugging process |
| `MICRO_ITERATION` | Encourage bigger-picture thinking |

| Provenance State | Concern |
|------------------|---------|
| `SUSPECTED_PASTE` | Ask student to explain code |
| `SPAMMING` | Encourage thoughtful edits |

## 🚀 Setup

1. **Install dependencies:**
```bash
pip install openai
```

2. **Set OpenAI API key:**
```bash
export OPENAI_API_KEY="sk-..."
```

3. **Run the backend:**
```bash
uvicorn app.main:app --reload
```

4. **Test the endpoint:**
```bash
curl -X POST http://localhost:8000/api/chat/ask \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "test123",
    "problem_id": "reverse-string",
    "problem_description": "Write a function to reverse a string",
    "user_query": "How do I start?"
  }'
```

## 🛡️ Safety Features

### Scope Filtering
**In Scope:**
- Understanding problems
- Debugging help
- Concept explanations
- Approach guidance

**Out of Scope:**
- Complete solutions
- Non-programming topics
- Harmful/unethical requests

### Token Management
- Input limit: 1000 tokens (~4000 chars)
- Output limit: 150 tokens (~600 chars)
- Model: gpt-4o-mini (cost-optimized)

## 📊 Example Interactions

### Example 1: Normal Request
**Query:** "I don't understand how recursion works"
**Response:** "Let's break it down! Can you think of a problem that's easier to solve if you first solve a smaller version of it?"

### Example 2: Intervention (DISENGAGEMENT)
**Context:** CognitiveState = DISENGAGEMENT, 5 minutes idle
**Response:** "I notice you might be stuck. Let's start simple: what's the first thing you need to do with the input data?"

### Example 3: Filtered Request
**Query:** "Write the complete solution for me"
**Response:** (OUT_OF_SCOPE_RESPONSE)

## 🔧 Customization

### Adjust Token Budgets
Edit `llm_client.py`:
```python
MAX_INPUT_TOKENS = 1000   # Increase for longer problems
MAX_OUTPUT_TOKENS = 150   # Increase for more detailed hints
```

### Modify Intervention Thresholds
Edit `policies.py`:
```python
INTERVENTION_URGENCY = {
    "DISENGAGEMENT": 3,  # Adjust urgency level
}
```

### Change AI Model
Edit `llm_client.py`:
```python
def __init__(self, model: str = "gpt-4o"):  # Use more powerful model
```

## 📝 Notes

- **Stateless Design**: No conversation history maintained (single-shot interactions)
- **Cost Optimization**: Uses gpt-4o-mini with strict token limits
- **Fail-Open**: If scope validation fails, request is allowed (prioritizes availability)
- **Logging**: All interactions logged for monitoring and debugging
