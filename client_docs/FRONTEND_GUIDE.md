# Frontend Development Guide

The frontend is a vanilla JavaScript Single Page Application (SPA) with no framework dependencies.

---

## Architecture

### File Structure
```
frontend/
  index.html              # Main SPA shell (sidebar + content area)
  login.html              # Login page (separate, pre-auth)
  app_v2.js               # Main application (~24,000 lines, all page logic)
  styles.css              # All styles (~6,000 lines)
  service-worker.js       # Offline caching + cache versioning
  app.js                  # ES6 module entry point
  core/
    api.js                # fetchAPI() - authenticated HTTP client
    utils.js              # escapeHtml(), formatters, debounce
    state.js              # Global polling state flags
    navigation.js         # showPage(), hash routing
    keyboard.js           # Shortcuts (Ctrl+K, Ctrl+1-9, Escape)
    export.js             # PDFExporter + ExcelExporter classes
  components/
    toast.js              # Toast notification system
    modals.js             # Modal create/show/hide with focus trap
    chat.js               # AI chat widget
    command_palette.js    # Ctrl+K global search
    notification_center.js # Bell icon + notification panel
  __tests__/              # Jest unit tests
```

### How the SPA Works

1. `index.html` loads `app_v2.js` which renders the sidebar and `<div id="content">`
2. Navigation uses URL hash: `#dashboard`, `#competitors`, etc.
3. `showPage(pageName)` clears `#content` and renders the selected page
4. Each page has its own `load*()` function that fetches data and builds the DOM
5. The chat widget is persistent across pages (global state, not DOM-dependent)

### ES6 Module System

The `core/` and `components/` directories use ES6 `import/export`. However, because `app_v2.js` uses inline `onclick` handlers in HTML strings, all exported functions must also be attached to `window.*`:

```javascript
// core/utils.js
export function escapeHtml(str) { ... }
window.escapeHtml = escapeHtml;  // Required for onclick handlers
```

Both `app_v2.js` (traditional) and `app.js` (ES6 modules) can coexist.

---

## Key Patterns

### API Calls
Always use `fetchAPI()` which handles auth tokens, error toasts, and base URL:

```javascript
// GET request
const data = await fetchAPI('/api/competitors');

// POST request
const result = await fetchAPI('/api/agents/battlecard', {
    method: 'POST',
    body: JSON.stringify({ competitor_id: 5, prompt_key: 'battlecard_generation' })
});

// Silent request (no error toast on failure)
const data = await fetchAPI('/api/news-feed', { silent: true });
```

**Important**: `fetchAPI()` already prepends the API base URL. Never include `http://localhost:8000` in the path.

### XSS Prevention
```javascript
// SAFE - use for user/AI content
element.textContent = userInput;

// SAFE - escaped HTML
element.innerHTML = `<span>${escapeHtml(userInput)}</span>`;

// DANGEROUS - never do this with user content
element.innerHTML = userInput;  // XSS vulnerability!
```

### Background Operations
Long-running operations (discovery, news fetch, verification) must survive SPA page navigation:

```javascript
// Use global polling flags
window._discoveryPolling = true;

async function pollDiscoveryProgress(taskId) {
    while (window._discoveryPolling) {
        const result = await fetchAPI(`/api/discovery/progress/${taskId}`, { silent: true });
        if (result.status === 'completed') {
            window._discoveryPolling = false;
            // Guard DOM access - user might be on a different page
            const el = document.getElementById('discoveryResults');
            if (el) renderDiscoveryResults(result.data);
            break;
        }
        await new Promise(r => setTimeout(r, 2000));
    }
}
```

**Key rules:**
- Use global flags, not `setInterval` inside Promises (they die on navigation)
- Guard ALL `getElementById` calls - DOM may not exist if user navigated away
- Store results globally so they persist when user returns to the page

### Chart.js Usage
```javascript
// Canvas 2D context cannot resolve CSS variables
// BAD:  color: 'var(--text-primary)'
// GOOD: color: '#e2e8f0'

const chart = new Chart(ctx, {
    type: 'bar',
    data: { ... },
    options: {
        plugins: {
            legend: { labels: { color: '#e2e8f0' } }  // Hardcoded hex
        },
        scales: {
            x: { ticks: { color: '#94a3b8' } }
        }
    }
});

// Always destroy charts before recreating (prevents memory leaks)
if (window._myChart) window._myChart.destroy();
window._myChart = new Chart(ctx, config);
```

### Modals
Modals are created dynamically in JavaScript, not in HTML:

```javascript
// Create modal
const modal = createModal('myModal', 'Modal Title', `
    <p>Modal content here</p>
    <button onclick="closeModal('myModal')">Close</button>
`);

// Show/hide
showModal('myModal');
closeModal('myModal');
```

---

## Adding a New Page

### Step 1: Add Sidebar Navigation
In `app_v2.js`, find the sidebar HTML and add your nav item:

```javascript
<a href="#my-page" onclick="showPage('my-page')" class="nav-link" data-page="my-page">
    <span class="nav-icon">...</span>
    <span class="nav-text">My Page</span>
</a>
```

### Step 2: Add the Page Case
In the `showPage()` function:

```javascript
case 'my-page':
    try {
        document.getElementById('content').innerHTML = `
            <div class="page-header">
                <div class="page-header-content">
                    <h1><span class="page-icon">...</span> My Page</h1>
                </div>
            </div>
            <div class="content-body">
                <div id="myPageContent">
                    <div class="loading-spinner">Loading...</div>
                </div>
            </div>
        `;
        await loadMyPage();
    } catch (err) {
        console.error('Error loading my page:', err);
        document.getElementById('content').innerHTML = `
            <div class="error-state">
                <h2>Error loading page</h2>
                <p>${escapeHtml(err.message)}</p>
            </div>
        `;
    }
    break;
```

### Step 3: Add Data Loading
```javascript
async function loadMyPage() {
    const data = await fetchAPI('/api/my-endpoint');
    const container = document.getElementById('myPageContent');
    if (!container) return;  // Guard against navigation

    container.innerHTML = `
        <div class="card">
            <h3>${escapeHtml(data.title)}</h3>
            <p>${escapeHtml(data.description)}</p>
        </div>
    `;
}
```

### Step 4: Add Keyboard Shortcut (Optional)
In the keyboard handler, add `Ctrl+N` (where N is the page number):

```javascript
case 'my-page-number':
    showPage('my-page');
    break;
```

---

## CSS Conventions

### Theme Colors (Dark Mode)
```css
--bg-primary: #0f172a;      /* Main background */
--bg-secondary: #1e293b;    /* Card backgrounds */
--bg-tertiary: #334155;     /* Hover states */
--text-primary: #e2e8f0;    /* Primary text */
--text-secondary: #94a3b8;  /* Secondary text */
--accent: #3b82f6;          /* Blue accent */
--accent-hover: #2563eb;    /* Blue hover */
--success: #10b981;         /* Green */
--warning: #f59e0b;         /* Amber */
--danger: #ef4444;          /* Red */
```

### Common Classes
- `.card` - Glassmorphism card container
- `.page-header` - Page title bar
- `.content-body` - Main content area
- `.loading-spinner` - Centered loading indicator
- `.error-state` - Error display
- `.btn-primary`, `.btn-secondary`, `.btn-danger` - Button styles
- `.data-grid` - Table/grid layouts
- `.sr-only` - Screen reader only text (accessibility)

### Glassmorphism Pattern
```css
.card {
    background: rgba(30, 41, 59, 0.8);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(148, 163, 184, 0.1);
    border-radius: 12px;
    padding: 1.5rem;
}
```

---

## Syncing to Desktop App

After ANY frontend change, sync to `desktop-app/frontend/`:

```bash
# Core files
copy frontend\app_v2.js desktop-app\frontend\app_v2.js
copy frontend\styles.css desktop-app\frontend\styles.css
copy frontend\index.html desktop-app\frontend\index.html

# ES6 modules
copy frontend\app.js desktop-app\frontend\app.js
xcopy frontend\core desktop-app\frontend\core /E /Y
xcopy frontend\components desktop-app\frontend\components /E /Y
```

Update `CACHE_VERSION` in both `service-worker.js` files for every release.

---

## Accessibility (WCAG 2.1 AA)

The app implements WCAG 2.1 AA compliance:
- **Skip-to-content** link on every page
- **ARIA landmarks**: `role="main"`, `role="navigation"`, `aria-label`
- **Focus-visible** indicators on all interactive elements
- **Keyboard navigation**: Ctrl+1-9 pages, Ctrl+K search, Escape close
- **Screen reader** text via `.sr-only` class
- **Color contrast**: 4.5:1 minimum ratio
