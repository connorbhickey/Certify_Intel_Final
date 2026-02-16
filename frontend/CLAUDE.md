# Frontend - Certify Intel

Vanilla JavaScript SPA with glassmorphism dark-mode aesthetic. 11 pages, Chart.js visualizations, offline support.

## Key Files

| File | Purpose | Size |
|------|---------|------|
| `app_v2.js` | Main SPA logic | ~723KB |
| `styles.css` | All styling, glassmorphism theme | ~275KB |
| `index.html` | SPA shell, 11-page navigation | ~206KB |
| `service-worker.js` | Offline caching, version control |
| `sales_marketing.js` | Sales & Marketing module | ~133KB |
| `agent_chat_widget.js` | AI chat interface | ~22KB |

## Conventions

- ES6+ only, no frameworks (vanilla JavaScript)
- XSS prevention: `textContent` over `innerHTML` for user/AI data
- camelCase functions, kebab-case CSS classes
- API calls: `${API_BASE}/api/...`
- Chart.js for all data visualizations
- Update `CACHE_VERSION` in `service-worker.js` for every release

## After Changes (CRITICAL)

Sync to `desktop-app/frontend/`:
```bash
cp frontend/app_v2.js desktop-app/frontend/app_v2.js
cp frontend/styles.css desktop-app/frontend/styles.css
cp frontend/index.html desktop-app/frontend/index.html
```

## For Agent Team Teammates

If you are a teammate working on the frontend:
- Your changes should stay within `frontend/` files
- After finishing, sync changed files to `desktop-app/frontend/`
- If your changes depend on new API endpoints, tell the backend teammate the expected request/response shape
- Avoid `innerHTML` with any user or AI-generated content (XSS risk)
- Test at common breakpoints (1920px, 1366px, 768px) for responsive behavior
