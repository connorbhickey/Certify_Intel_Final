# Desktop App - Certify Intel

Electron desktop app bundling the FastAPI backend (via PyInstaller) and the frontend SPA.

## Structure

| Directory | Purpose |
|-----------|---------|
| `electron/main.js` | Electron main process, auto-update, Sentry |
| `frontend/` | **Synced copy** from `../frontend/` — do NOT edit directly |
| `backend-bundle/` | PyInstaller output (exe, db, .env) |
| `dist/` | Build output (installer, blockmap, latest.yml) |
| `package.json` | Version, build config, electron-builder settings |

## Key Rules

- **Never edit `desktop-app/frontend/` directly** — edit `frontend/` and sync
- Version in `package.json` must match all 5 other version locations
- Full 11-step build protocol in root `CLAUDE.md` is MANDATORY
- Always clear electron-builder AND PyInstaller caches before building
- All 3 release artifacts required: `.exe`, `.blockmap`, `latest.yml`

## Build Protocol Summary

1. Bump version in 6 files → 2. Sync frontend → 3. Cleanup processes → 4. Clear caches → 5. Verify source → 6. PyInstaller → 7. Copy to bundle → 8. Electron build → 9. Verify output → 10. Report location → 11. Commit/push/release

## For Agent Team Teammates

If you are a teammate working on the desktop app:
- Configuration changes go in `electron/main.js` or `package.json`
- Frontend changes must be made in `../frontend/` first, then synced
- Coordinate with the backend teammate if backend startup behavior changes
- Building requires a Windows machine with the user's local environment

## Current Version

v7.1.6 (Windows only — macOS requires macOS machine)
