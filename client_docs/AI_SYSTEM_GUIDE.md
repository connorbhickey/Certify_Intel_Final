# AI System Guide

Certify Intel uses a multi-provider AI system with 7 specialized LangGraph agents.

---

## AI Provider Architecture

### Provider Hierarchy
```
                   AIRouter (ai_router.py)
                         |
        +----------------+----------------+
        |                |                |
   Claude Opus 4.5   GPT-4o          Gemini 3
   (Anthropic)       (OpenAI)        (Google)
   Quality tasks     Fallback        Flash: speed/bulk
                                     Pro: grounded search
```

### Task Routing
The `TASK_ROUTING` dictionary in `ai_router.py` maps task types to providers:

| Task Type | Default Provider | Why |
|-----------|-----------------|-----|
| Complex analysis | Anthropic (Claude) | Best reasoning quality |
| Battlecard generation | Anthropic (Claude) | Nuanced competitive writing |
| Chat/conversation | Gemini Flash | Fast, cheap, good enough |
| Summarization | Gemini Flash | Speed over quality |
| Classification | Gemini Flash | Simple categorization |
| Bulk extraction | Gemini Flash | Cost-effective at scale |
| Grounded search | Gemini Pro | Has web grounding capability |
| Deep research | Gemini Pro | Quality + grounding |
| Executive summaries | Gemini Pro | Quality output |
| Fallback | GPT-4o | When primary provider fails |

### How Routing Works

```python
# ai_router.py - simplified flow
class AIRouter:
    async def route_request(self, prompt, task_type, **kwargs):
        provider = TASK_ROUTING.get(task_type, "anthropic")
        try:
            return await self._call_provider(provider, prompt, **kwargs)
        except Exception:
            if AI_FALLBACK_ENABLED:
                return await self._call_fallback(prompt, **kwargs)
            raise
```

**Important**: Always use `get_ai_router()` singleton. Never instantiate `AIRouter()` per request (causes memory leaks).

---

## Agent System (LangGraph)

### The 7 Agents

| Agent | File | Purpose |
|-------|------|---------|
| **Dashboard** | `agents/dashboard_agent.py` | Competitive landscape summaries, threat analysis |
| **Discovery** | `agents/discovery_agent.py` | Find new competitors via 4-stage AI pipeline |
| **Battlecard** | `agents/battlecard_agent.py` | Generate sales-ready competitor one-pagers |
| **News** | `agents/news_agent.py` | News analysis, sentiment, event classification |
| **Analytics** | `agents/analytics_agent.py` | Market positioning, trend analysis |
| **Validation** | `agents/validation_agent.py` | Data verification against web sources |
| **Records** | `agents/records_agent.py` | Data management queries |

### Orchestrator
`agents/orchestrator.py` routes user queries to the appropriate agent using keyword scoring:

```
User query -> Orchestrator -> Score keywords -> Select agent -> Execute -> Return
```

### Agent Base Class
All agents inherit from `BaseAgent` (`agents/base_agent.py`):

```python
class BaseAgent:
    def __init__(self, name, db_session=None):
        self.name = name
        self.db_session = db_session
        self.ai_router = get_ai_router()

    async def process(self, query, context=None):
        # Override in subclass
        raise NotImplementedError
```

### Citation Validator
`agents/citation_validator.py` validates AI outputs against source data to prevent hallucinations.

---

## Adding a New Agent

### Step 1: Create the Agent File

```python
# agents/my_agent.py
import logging
from agents.base_agent import BaseAgent
from constants import NO_HALLUCINATION_INSTRUCTION

logger = logging.getLogger(__name__)

class MyAgent(BaseAgent):
    def __init__(self, db_session=None):
        super().__init__(name="my_agent", db_session=db_session)

    async def process(self, query: str, context: dict = None) -> dict:
        system_prompt = f"""{NO_HALLUCINATION_INSTRUCTION}
        You are a specialized agent for [purpose].
        Respond in JSON format only.
        """

        result = await self.ai_router.route_request(
            prompt=query,
            system_prompt=system_prompt,
            task_type="complex_analysis"  # Maps to provider via TASK_ROUTING
        )

        return {
            "agent": self.name,
            "response": result.get("content", ""),
            "metadata": {"model": result.get("model", "unknown")}
        }
```

### Step 2: Register in Orchestrator

In `agents/orchestrator.py`, add routing keywords:

```python
AGENT_KEYWORDS = {
    "my_agent": ["my-keyword", "another-keyword", "topic-words"],
    # ... existing agents
}
```

### Step 3: Add API Endpoint

In `routers/agents.py`:

```python
@router.post("/my-agent")
async def run_my_agent(
    request: AgentRequest,
    db=Depends(get_db),
    user=Depends(get_current_user)
):
    from agents.my_agent import MyAgent
    agent = MyAgent(db_session=db)
    result = await agent.process(request.query, request.context)
    return result
```

### Step 4: Add Tests

```python
# tests/test_my_agent.py
from unittest.mock import patch, AsyncMock

class TestMyAgent:
    @patch("agents.my_agent.get_ai_router")
    async def test_process_returns_result(self, mock_router):
        mock_router.return_value.route_request = AsyncMock(
            return_value={"content": "AI response", "model": "claude"}
        )
        from agents.my_agent import MyAgent
        agent = MyAgent()
        result = await agent.process("test query")
        assert result["agent"] == "my_agent"
        assert "response" in result
```

---

## Key Patterns

### Hallucination Prevention
Every AI system prompt MUST include `NO_HALLUCINATION_INSTRUCTION`:

```python
from constants import NO_HALLUCINATION_INSTRUCTION

system_prompt = f"""{NO_HALLUCINATION_INSTRUCTION}
Your specific instructions here...
"""
```

### Gemini JSON Output
Gemini models wrap responses in markdown code blocks. Always request JSON-only:

```python
system_prompt = """
Respond with ONLY valid JSON. No markdown, no code blocks, no explanation.
"""
```

### Rate Limiting for Gemini
When making batch Gemini calls, add a 1-second delay between requests:

```python
import asyncio

for item in items:
    result = await ai_router.route_request(prompt, task_type="classification")
    await asyncio.sleep(1)  # Prevent rate limiting
```

### Background AI Tasks
Long-running AI operations use the task service:

```python
from services.task_service import create_task, update_task

task_id = create_task("my_operation")
try:
    result = await long_ai_operation()
    update_task(task_id, status="completed", result=result)
except Exception as e:
    update_task(task_id, status="failed", error=str(e))
```

Frontend polls `GET /api/ai/tasks/{task_id}` for status updates.

---

## Cost Management

### AI Cost Tracking
The app tracks AI costs via `GET /api/ai/cost/summary`:
- Cost breakdown by provider and model
- Daily cost time series
- Cost by feature (discovery, battlecards, etc.)

### Cost Optimization Tips
1. Use Gemini Flash for simple tasks (10x cheaper than Claude)
2. Enable caching (`REDIS_ENABLED=true`) to avoid duplicate AI calls
3. Use `OLLAMA_ENABLED=true` for development/testing ($0 cost)
4. Monitor costs via the Settings > AI Cost panel
