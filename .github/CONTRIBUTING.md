# Contributing to Certify Intel

## For AI Agents (Claude, GPT, Copilot, Cursor, etc.)

**READ `CLAUDE.md` FIRST** - It contains mandatory instructions for all AI agents.

---

## ⚡ SYNC PROTOCOL - REQUIRED AFTER EVERY TASK

**MANDATORY: After completing ANY task (no matter how minor), sync local ↔ GitHub:**

```bash
cd /path/to/Project_Intel_v6.1.1
git status
git add -A
git commit -m "[Category] Brief description"
git push origin master
```

**Every single change must be committed and pushed immediately.**

| Category | Use For |
|----------|---------|
| `[Fix]` | Bug fixes |
| `[Feature]` | New functionality |
| `[Docs]` | Documentation |
| `[Build]` | Desktop app releases |
| `[Refactor]` | Code restructuring |
| `[Chore]` | Maintenance |

---

## 🔒 CI/CD PIPELINE - AUTO-PR & AUTO-MERGE

### Local Testing (Before Push)

**MANDATORY**: Run tests locally before pushing:

```powershell
.\scripts\pre-push-tests.ps1
```

Or install git hooks for automatic testing:
```powershell
.\scripts\setup-git-hooks.ps1
```

### Automated Pipeline

1. **On Push to ANY Branch**:
   - Tests run automatically (pytest)
   - Code quality checks (flake8, black, isort)

2. **Feature Branches**:
   - When tests pass → PR is auto-created to master
   - PR is labeled `auto-pr`

3. **Auto-Merge**:
   - PRs with `auto-pr` label merge automatically when all checks pass
   - Uses squash merge for clean history

### Workflow

```bash
# Feature branch workflow
git checkout -b feature/my-feature
# ... make changes ...
.\scripts\pre-push-tests.ps1
git add -A && git commit -m "[Feature] Description"
git push origin feature/my-feature
# CI/CD creates PR and auto-merges when checks pass

# Direct to master (quick fixes)
git checkout master
# ... make changes ...
.\scripts\pre-push-tests.ps1
git add -A && git commit -m "[Fix] Description"
git push origin master
```

---

## Quick Reference

### File Save Locations
- **Documentation**: Save to `docs/` folder (NOT hidden folders)
- **Code**: Save to respective folders (`backend/`, `frontend/`, `desktop-app/`)
- **Desktop builds**: Output to `desktop-app/dist/`

### Desktop App Build Protocol

**MANDATORY**: Before building ANY new desktop app version:

1. Run cleanup script first:
```powershell
powershell -ExecutionPolicy Bypass -File "docs/CLEANUP_OLD_INSTALL.ps1"
```

2. Build new version:
```powershell
cd desktop-app
npm run build:win
```

3. Installer will be at: `desktop-app/dist/Certify_Intel_vX.X.X_Setup.exe`

4. **SYNC TO GITHUB** (don't forget!)

### Why Cleanup First?
- Kills orphaned backend processes (port 8000)
- Uninstalls old version silently
- Deletes leftover files that cause conflicts
- Ensures clean installation

---

## Project Structure

```
Project_Intel_v6.1.1/
├── backend/           # FastAPI Python backend
├── frontend/          # Web UI (HTML/JS/CSS)
├── desktop-app/       # Electron wrapper
│   ├── dist/          # Built installers go here
│   └── backend-bundle/# PyInstaller executable
├── docs/              # Documentation and scripts
├── .github/           # GitHub config (this file)
└── CLAUDE.md          # AI agent instructions (READ THIS)
```

---

## Key Files for AI Agents

| File | Purpose |
|------|---------|
| `CLAUDE.md` | **READ FIRST** - Mandatory instructions, current state, remaining work |
| `PLAN_COMPETITOR_INTEL_OPTIMIZED.md` | Master rebuild plan with all tasks |
| `docs/V7_AGENT_SYSTEM.md` | Agent architecture, API endpoints |
| `docs/CLEANUP_OLD_INSTALL.ps1` | Run before desktop builds |

---

## For Human Developers

1. Read `CLAUDE.md` for project context and current state
2. Check `PLAN_COMPETITOR_INTEL_OPTIMIZED.md` for master plan
3. Follow the desktop app build protocol above
4. **Always commit and push after every change**
5. Test locally before pushing

---

## Code Style

- **Python**: Type hints, async/await, Pydantic models
- **JavaScript**: ES6+, no frameworks (vanilla JS)
- **CSS**: CSS variables, flexbox/grid, dark theme

---

## GitHub Repository

- **Repo**: `https://github.com/[YOUR-GITHUB-ORG]/Project_Intel_v6.1.1`
- **Branch**: `master`
- **Local Path**: `[USER_HOME]\Documents\Project_Intel_v6.1.1\`

**Local and GitHub MUST be 100% identical at all times.**

