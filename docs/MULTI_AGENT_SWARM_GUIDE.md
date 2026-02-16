# Multi-Agent Setup Guide — Certify Intel v7.1.1

> Two complementary patterns configured: **Agent Teams** (multi-session swarm) and **Subagents** (single-session delegation).

---

## Table of Contents

1. [Agent Teams vs Subagents — When to Use Which](#agent-teams-vs-subagents)
2. [Agent Teams (The Swarm)](#agent-teams-the-swarm)
3. [Subagents (Single-Session Specialists)](#subagents-single-session-specialists)
4. [Configuration Reference](#configuration-reference)
5. [Practical Prompts for This Codebase](#practical-prompts-for-this-codebase)
6. [Best Practices](#best-practices)

---

## Agent Teams vs Subagents

This project is configured with **both** patterns. Choose based on whether your workers need to communicate with each other.

| | Subagents | Agent Teams |
|---|---|---|
| **Context** | Own context window; results return to caller | Own context window; fully independent |
| **Communication** | Report results back to main agent only | Teammates message each other directly |
| **Coordination** | Main agent manages all work | Shared task list with self-coordination |
| **Best for** | Focused tasks where only the result matters | Complex work requiring discussion and collaboration |
| **Token cost** | Lower: results summarized back to main context | Higher: each teammate is a separate Claude instance |
| **File conflicts** | N/A (sequential, main agent manages) | Must assign different files to different teammates |

**Use Agent Teams when:**
- The task spans frontend, backend, AND tests (cross-layer coordination)
- You want teammates to challenge each other's findings (competing hypotheses)
- Multiple people need to investigate different aspects in parallel and discuss
- You're doing a comprehensive review or audit across the whole codebase

**Use Subagents when:**
- You need a quick, focused worker that reports back (run tests, lint check)
- The task is self-contained (review one file, investigate one module)
- You want to keep verbose output out of your main conversation
- Latency matters — subagents are faster to spin up

---

## Agent Teams (The Swarm)

### How It Works

Agent Teams coordinate **multiple independent Claude Code sessions** working together:

```
You (prompt) → Team Lead (your main session)
                   ├── Spawns Teammate A (backend work)
                   ├── Spawns Teammate B (frontend work)
                   └── Spawns Teammate C (test validation)
                         ↕ ↕ ↕
                   Shared Task List + Direct Messaging (Mailbox)
                         ↕ ↕ ↕
                   Lead synthesizes results
```

**Key architecture:**

| Component | Role |
|---|---|
| **Team Lead** | Your main session — creates the team, spawns teammates, coordinates |
| **Teammates** | Separate Claude Code instances, each with own context window |
| **Task List** | Shared list of work items that teammates claim and complete |
| **Mailbox** | Direct messaging between any agents (not just lead ↔ teammate) |

### Enablement

Already configured in `.claude/settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process"
}
```

**Display modes:**
- `"in-process"` (configured) — All teammates in your main terminal. Use **Shift+Up/Down** to select a teammate, type to message them.
- `"tmux"` — Each teammate gets its own split pane. Requires tmux or iTerm2.
- `"auto"` — Uses split panes if inside tmux, otherwise in-process.

To switch to split panes, change `teammateMode` to `"tmux"` in `.claude/settings.json` or pass `--teammate-mode tmux` at launch.

### Starting a Team

Tell Claude to create a team and describe the structure you want in natural language:

```
Create an agent team to investigate the slow dashboard load time.
Spawn three teammates:
- One investigating backend SQL queries and N+1 issues in main.py
- One checking frontend rendering bottlenecks in app_v2.js
- One reviewing the AI agent response latency in agents/dashboard_agent.py
Have them share findings and challenge each other's conclusions.
```

Claude creates the team, spawns teammates, assigns tasks, and synthesizes results.

### Controlling the Team

#### Navigate teammates (in-process mode)
- **Shift+Up/Down** — Select a teammate
- **Type + Enter** — Send message to selected teammate
- **Enter** — View a teammate's session
- **Escape** — Interrupt a teammate's current turn
- **Ctrl+T** — Toggle the shared task list

#### Delegate mode
Press **Shift+Tab** to switch the lead into delegate mode. This restricts the lead to coordination-only (spawn, message, manage tasks) and prevents it from implementing code itself. Useful when you want the lead to purely orchestrate.

#### Require plan approval
For risky changes, require teammates to plan before implementing:

```
Spawn a backend teammate to refactor the authentication module.
Require plan approval before they make any changes.
Only approve plans that include test coverage.
```

The teammate works in read-only plan mode, submits a plan to the lead, and only proceeds after approval.

#### Assign tasks explicitly or let teammates self-claim

```
Assign the database migration task to the backend teammate
```

Or let teammates self-claim: after finishing a task, a teammate picks up the next unassigned, unblocked task automatically.

#### Shut down teammates and clean up

```
Ask the frontend teammate to shut down
```

When done with all work:
```
Clean up the team
```

Always shut down all teammates before cleaning up. Only the lead should run cleanup.

### Agent Teams Prompts for This Codebase

Below are ready-to-use prompts tailored to Certify Intel's architecture.

#### Cross-Layer Feature Implementation

```
Create an agent team to implement [feature description]. Spawn teammates:
- Backend teammate: implement the API endpoint in backend/main.py and any
  database model changes in backend/database.py
- Frontend teammate: implement the UI in frontend/app_v2.js and
  frontend/styles.css, then sync to desktop-app/frontend/
- Test teammate: write tests in backend/tests/ and run the CI-safe test suite

Important context:
- Backend uses FastAPI + SQLAlchemy 2.0 (async, select() pattern)
- Frontend is vanilla JS SPA (no frameworks), XSS prevention required
- Frontend changes MUST be synced to desktop-app/frontend/
- SQLite won't auto-create columns — need ALTER TABLE migrations
```

#### Parallel Code Review / Security Audit

```
Create an agent team to review the codebase before release. Spawn teammates:
- Security reviewer: scan backend/main.py and frontend/app_v2.js for
  XSS, SQL injection, hardcoded secrets, and auth bypasses
- Performance reviewer: check for N+1 queries, memory leaks, blocking
  async calls, and unnecessary re-renders
- Test coverage reviewer: identify untested endpoints and edge cases,
  run the CI-safe test suite

Have them share findings with each other. The security reviewer should
challenge any "safe" claims from the others.
```

#### Debugging with Competing Hypotheses

```
Users report [bug description]. Create an agent team to investigate.
Spawn 3 teammates to test different hypotheses:
- Hypothesis 1: backend database query returning wrong data (check main.py)
- Hypothesis 2: frontend rendering logic error (check app_v2.js)
- Hypothesis 3: AI agent returning hallucinated content (check agents/)

Have them talk to each other to try to disprove each other's theories.
Update findings as consensus emerges.
```

#### AI Agent System Changes

```
Create an agent team to add [new capability] to the agent system. Spawn:
- Architect teammate: design the changes to the LangGraph orchestrator
  (backend/agents/orchestrator.py) and base agent (backend/agents/base_agent.py).
  Require plan approval before implementation.
- Implementer teammate: implement changes after architect's plan is approved.
  Follow existing BaseAgent patterns, include citation validation.
- Validator teammate: run test_agent_integration.py, test_orchestrator.py,
  and test_hallucination_prevention.py. Report any failures.

Context: 7 LangGraph agents route via keyword scoring in orchestrator.py.
All agents inherit from BaseAgent. AI routing uses Claude Opus 4.5 primary,
GPT-4o fallback, Gemini for bulk tasks.
```

---

## Subagents (Single-Session Specialists)

### How They Work

Subagents run **within your current session**. Claude auto-delegates to the right subagent based on its `description` field, or you can request one explicitly.

```
You (prompt) → Claude → delegates to subagent (own context)
                                    ↓
                            subagent works
                                    ↓
                            result returns to Claude
```

### Configured Subagents (7)

| Agent | File | Model | Purpose |
|-------|------|-------|---------|
| `backend-specialist` | `.claude/agents/backend-specialist.md` | Sonnet | Python/FastAPI endpoints, business logic |
| `frontend-specialist` | `.claude/agents/frontend-specialist.md` | Sonnet | Vanilla JS SPA, CSS, Chart.js |
| `agent-architect` | `.claude/agents/agent-architect.md` | **Opus** | LangGraph agents, AI Router, RAG pipeline |
| `test-runner` | `.claude/agents/test-runner.md` | **Haiku** | pytest, flake8, CI validation |
| `security-reviewer` | `.claude/agents/security-reviewer.md` | Sonnet | OWASP audit, XSS, auth review |
| `desktop-app-builder` | `.claude/agents/desktop-app-builder.md` | Sonnet | Electron/PyInstaller builds |
| `database-specialist` | `.claude/agents/database-specialist.md` | Sonnet | SQLAlchemy ORM, migrations |

**Model selection rationale:**
- **Opus** for `agent-architect` — Complex AI system reasoning requires strongest model
- **Haiku** for `test-runner` — Just runs commands and reports, fast and cheap
- **Sonnet** for everything else — Balanced speed/quality for code work

### Using Subagents

Claude auto-delegates based on task description. You can also request explicitly:

```
Use the test-runner subagent to run the CI-safe test suite
```

```
Use the security-reviewer subagent to audit the authentication endpoints
```

```
Use the backend-specialist subagent to add a new API endpoint for competitor notes
```

### Subagent Persistent Memory

Key subagents have persistent memory enabled. They build knowledge across conversations:

- `backend-specialist` — Remembers codebase patterns, common pitfalls
- `agent-architect` — Remembers architectural decisions, agent design patterns
- `security-reviewer` — Remembers past findings, known vulnerability patterns

Memory is stored in `.claude/agent-memory/<agent-name>/MEMORY.md` and accumulates over time.

---

## Configuration Reference

### Files Created

```
.claude/
├── agents/                          # 7 subagent definitions
│   ├── backend-specialist.md
│   ├── frontend-specialist.md
│   ├── agent-architect.md
│   ├── test-runner.md
│   ├── security-reviewer.md
│   ├── desktop-app-builder.md
│   └── database-specialist.md
├── rules/                           # Path-specific coding rules
│   ├── backend.md                   # Auto-applied when editing backend/
│   ├── frontend.md                  # Auto-applied when editing frontend/
│   └── desktop-app.md              # Auto-applied when editing desktop-app/
└── settings.json                    # Agent Teams enablement + permissions

backend/CLAUDE.md                    # Backend context (loaded by teammates too)
frontend/CLAUDE.md                   # Frontend context (loaded by teammates too)
desktop-app/CLAUDE.md               # Desktop app context (loaded by teammates too)
```

### How Teammates Get Context

Agent Team teammates automatically load:
1. **Root `CLAUDE.md`** — Full project instructions, architecture, build protocol
2. **Component `CLAUDE.md`** — When working in `backend/`, `frontend/`, or `desktop-app/`
3. **Path rules** (`.claude/rules/`) — Auto-injected when editing files in matching paths
4. **Spawn prompt** — Task-specific context you provide when creating the team

Teammates do NOT inherit the lead's conversation history. Include task-specific details in the spawn prompt.

### settings.json

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  },
  "teammateMode": "in-process",
  "permissions": {
    "allow": [ "...common safe commands..." ],
    "ask": [ "Bash(git push *)" ],
    "deny": [ "...destructive commands, .env files..." ]
  }
}
```

Teammates inherit the lead's permission settings. Pre-approve common operations to reduce permission prompt friction during team work.

---

## Best Practices

### For Agent Teams

1. **Give teammates enough context in the spawn prompt.** They load CLAUDE.md automatically but don't inherit your conversation history. Include file paths, function names, and relevant constraints.

2. **Size tasks appropriately.** Too small = coordination overhead exceeds benefit. Too large = teammates work too long without check-ins. Aim for self-contained units that produce a clear deliverable. Having 5-6 tasks per teammate keeps everyone productive.

3. **Avoid file conflicts.** Two teammates editing the same file leads to overwrites. Assign each teammate a different set of files (e.g., one owns `main.py`, another owns `app_v2.js`).

4. **Use delegate mode for complex orchestration.** Press Shift+Tab so the lead focuses on coordination instead of implementing code itself.

5. **Require plan approval for risky changes.** Database schema changes, auth modifications, and build protocol changes should be planned before implemented.

6. **Monitor and steer.** Check teammate progress, redirect approaches that aren't working, and synthesize findings as they come in. Don't let a team run unattended too long.

7. **Tell the lead to wait.** If the lead starts implementing instead of waiting for teammates:
   ```
   Wait for your teammates to complete their tasks before proceeding
   ```

8. **Start with research/review tasks** if you're new to Agent Teams. PR reviews, bug investigations, and audits have clear boundaries and show the value of parallel exploration without coordination complexity.

### For Subagents

1. **Use for focused, isolated tasks.** Running tests, quick audits, single-file investigations.

2. **Request the right subagent explicitly** when auto-delegation doesn't match:
   ```
   Use the agent-architect subagent to review the LangGraph routing logic
   ```

3. **Chain subagents** for multi-step workflows:
   ```
   Use backend-specialist to implement the endpoint, then test-runner to verify
   ```

### For Both

1. **Use `/clear` between unrelated tasks.** Context accumulates and degrades performance.

2. **Pre-approve permissions.** The more operations pre-approved in settings.json, the fewer interruptions during team/subagent work.

3. **Keep CLAUDE.md files concise.** They're loaded into every teammate's and subagent's context. Focus on what Claude can't infer from code.

---

## Customization

### Adding a New Subagent

Create a file in `.claude/agents/`:

```markdown
---
name: my-new-agent
description: When Claude should delegate to this agent
model: sonnet
memory: project
---

System prompt for the agent...
```

Run `/agents` in Claude Code to manage subagents interactively.

### Switching Display Modes

For split-pane mode (requires tmux or iTerm2):
```json
{ "teammateMode": "tmux" }
```

Or per-session:
```bash
claude --teammate-mode tmux
```

### Disabling a Subagent

Add to `.claude/settings.json`:
```json
{
  "permissions": {
    "deny": ["Task(agent-name)"]
  }
}
```
