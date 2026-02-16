# Certify Intel v7.0 - AI Agent System

## Overview

Certify Intel v7.0 introduces a LangGraph-orchestrated AI agent system for intelligent competitive intelligence. The system routes natural language queries to specialized agents that provide cited, verified responses.

## Architecture

```
User Query
    ↓
┌─────────────────────────────────────────────────────────┐
│                     ORCHESTRATOR                         │
│  (LangGraph StateGraph with intelligent routing)         │
└─────────────────────────────────────────────────────────┘
    ↓                                                   ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Dashboard  │  │  Discovery  │  │  Battlecard │  │    News     │
│    Agent    │  │    Agent    │  │    Agent    │  │   Agent     │
└─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘
    ↓                                                   ↓
┌─────────────┐  ┌─────────────┐  ┌─────────────┐
│  Analytics  │  │  Validation │  │   Records   │
│    Agent    │  │    Agent    │  │   Agent     │
└─────────────┘  └─────────────┘  └─────────────┘
    ↓
┌─────────────────────────────────────────────────────────┐
│                  SHARED COMPONENTS                       │
│  • Knowledge Base (RAG)    • Vector Store (pgvector)    │
│  • AI Router (cost-aware)  • Citation Validator         │
│  • Cost Tracker            • Langfuse Observability     │
└─────────────────────────────────────────────────────────┘
```

## Agents

### 1. Dashboard Agent
**Purpose:** Executive summaries and threat analysis

**Queries:**
- "What are the top threats?"
- "Give me a status overview"
- "Summarize the competitive landscape"

**Output:** Threat levels, key metrics, actionable insights with citations

---

### 2. Discovery Agent
**Purpose:** Find and qualify new competitors

**Queries:**
- "Find telehealth competitors"
- "Discover emerging AI healthcare companies"
- "Scout for new market entrants"

**Output:** Qualified competitors with scores, SWOT analysis, recommendations

---

### 3. Battlecard Agent
**Purpose:** Generate sales battlecards

**Queries:**
- "Generate battlecard for Epic Systems"
- "Create competitive comparison"
- "Give me talking points vs Athenahealth"

**Output:** Structured battlecard with strengths, weaknesses, objection handlers

---

### 4. News Agent
**Purpose:** Real-time news monitoring and sentiment

**Queries:**
- "Latest news about competitors"
- "Show funding announcements this week"
- "What's the sentiment for Cerner?"

**Output:** News digest with sentiment breakdown, major event highlights

---

### 5. Analytics Agent
**Purpose:** Market analysis and reporting

**Queries:**
- "Generate executive summary"
- "Show market positioning"
- "Win/loss trends this quarter"

**Output:** Data-driven reports with visualizations and recommendations

---

### 6. Validation Agent
**Purpose:** Data confidence scoring (Admiralty Code)

**Queries:**
- "Validate data for Epic Systems"
- "Show low confidence data"
- "Data quality report"

**Output:** Confidence scores per field, verification recommendations

**Admiralty Code Ratings:**
- **A** (50): Completely reliable
- **B** (40): Usually reliable
- **C** (30): Fairly reliable
- **D** (20): Not usually reliable
- **E** (10): Unreliable
- **F** (5): Cannot be judged

---

### 7. Records Agent
**Purpose:** Change tracking and audit logs

**Queries:**
- "Show change history for competitor"
- "What changed this week?"
- "Activity log for today"

**Output:** Change timeline with before/after, severity indicators

---

## API Endpoints

### Query Orchestrator
```
POST /api/agents/query
{
    "query": "What are the top threats?",
    "user_id": "user123",
    "session_id": "optional-session"
}

Response:
{
    "response": "Based on our analysis...",
    "agent": "dashboard",
    "citations": [...],
    "cost_usd": 0.001,
    "tokens_used": 500,
    "latency_ms": 150
}
```

### Direct Agent Access
```
POST /api/agents/dashboard
POST /api/agents/discovery
POST /api/agents/battlecard
POST /api/agents/news
POST /api/agents/analytics
POST /api/agents/validation
POST /api/agents/records
```

### Status & Cost
```
GET /api/agents/status    # System health
GET /api/agents/cost      # Usage tracking
```

### Knowledge Base
```
POST /api/agents/knowledge-base/search
POST /api/agents/knowledge-base/context
```

---

## Response Structure

All agents return consistent response structure:

```python
@dataclass
class AgentResponse:
    text: str              # Natural language response
    citations: List[Citation]  # Source references
    agent_type: str        # Which agent handled
    data: Dict[str, Any]   # Structured data
    cost_usd: float        # API cost
    latency_ms: float      # Response time
    tokens_used: int       # Token count
```

### Citations
Every factual claim includes citations:

```python
@dataclass
class Citation:
    source_id: str         # Unique ID
    source_type: str       # "document", "competitor_database", "news"
    content: str           # Cited content
    confidence: float      # 0-1 confidence score
    url: Optional[str]     # Source URL if available
```

---

## Cost-Optimized AI Routing

The system uses intelligent model selection:

| Task Type | Model | Cost/1M tokens |
|-----------|-------|----------------|
| Bulk extraction | DeepSeek V3.2 | $0.14 |
| Fast responses | Gemini 2.0 Flash | $0.075 |
| Complex analysis | Claude Sonnet 4 | $3.00 |
| Strategic decisions | Claude Opus 4 | $15.00 |

**Result:** ~98% cost savings vs using Opus for everything

---

## Integration Example

```python
from agents import run_agent_query

# Query the orchestrator
response = await run_agent_query(
    query="What are the top threats this week?",
    user_id="analyst_1"
)

print(f"Agent: {response.agent_type}")
print(f"Response: {response.text}")
print(f"Citations: {len(response.citations)}")
print(f"Cost: ${response.cost_usd:.4f}")
```

---

## Test Coverage

| Test Suite | Tests | Status |
|------------|-------|--------|
| Agent Integration | 51 | ✅ Pass |
| Orchestrator | 21 | ✅ Pass |
| Hallucination Prevention | 12 | ✅ Pass |
| E2E Workflows | 14 | ✅ Pass |
| Full Integration | 27 | ✅ Pass |
| Performance Benchmarks | 17 | ✅ Pass |
| Agent KB Integration | 31 | ✅ Pass |
| **Total** | **171+** | **✅ All Pass** |

*Last verified: February 2, 2026 (Session 47)*

---

## Performance Targets

| Metric | Target | Actual |
|--------|--------|--------|
| Agent response | <2000ms | ✅ ~500ms avg |
| Vector search | <500ms | ✅ <200ms |
| RAG context | <1000ms | ✅ ~300ms |
| DB queries | <100ms | ✅ <50ms |

---

## Files

```
backend/
├── agents/
│   ├── __init__.py          # Exports all agents
│   ├── orchestrator.py      # LangGraph routing
│   ├── base_agent.py        # Base class & dataclasses
│   ├── dashboard_agent.py   # Executive summaries
│   ├── discovery_agent.py   # Competitor discovery
│   ├── battlecard_agent.py  # Sales battlecards
│   ├── news_agent.py        # News monitoring
│   ├── analytics_agent.py   # Market analysis
│   ├── validation_agent.py  # Data confidence
│   ├── records_agent.py     # Change tracking
│   └── citation_validator.py # Hallucination prevention
├── ai_router.py             # Cost-aware model selection
├── knowledge_base.py        # RAG pipeline
├── vector_store.py          # pgvector integration
├── observability.py         # Langfuse tracing
└── routers/
    └── agents.py            # API endpoints
```

---

## Quick Start

1. **Install dependencies:**
   ```bash
   pip install langchain langgraph asyncpg pgvector
   ```

2. **Configure environment:**
   ```bash
   export OPENAI_API_KEY=...
   export GOOGLE_AI_API_KEY=...
   export DATABASE_URL=postgresql://...
   ```

3. **Run server:**
   ```bash
   cd backend
   python main.py
   ```

4. **Test agents:**
   ```bash
   pytest tests/test_full_integration.py -v
   ```

---

## Version History

- **v7.0.0** (Feb 2026): LangGraph agents, RAG, citations
- **v6.3.x**: UI improvements, discovery scout
- **v5.x**: Sales & Marketing module, hybrid AI
- **v4.x**: News monitoring, data quality

---

*Documentation generated for Certify Intel v7.0*
*Last updated: February 2, 2026*

---

**v7.0.0 Released:** February 2, 2026
**All Planned Features:** Implemented
**GitHub Release:** https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v6.1.1/releases/tag/v7.0.0
