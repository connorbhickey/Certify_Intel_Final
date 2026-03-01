# Meeting Prep: Competitor Management in Certify Intel

**Prepared**: March 1, 2026
**Context**: Client's IT team has deployed Certify Intel on internal servers and fixed the login issue. Client wants a walkthrough on editing/updating the competitor list.

---

## Quick Summary of What They Can Do

The platform fully supports all three requests out of the box:
1. **Change threat levels** (move competitors up/down the threat list)
2. **Remove competitors** (soft-delete, recoverable)
3. **Add new competitors** (manual entry or AI-powered discovery)

---

## 1. Changing Threat Levels (Moving Competitors Up/Down)

### Via the UI (Easiest)
- Navigate to **Competitors** page
- Click on any competitor card to open the detail/edit view
- Change the **Threat Level** dropdown: `High`, `Medium`, or `Low`
- Save — the change is logged automatically with a full audit trail

### What Happens Behind the Scenes
- The `PUT /api/competitors/{id}` endpoint updates the competitor
- Every field change is recorded in `DataChangeHistory` (who changed it, old value, new value, timestamp)
- The **Dashboard** automatically recalculates:
  - Threat distribution chart (High/Medium/Low breakdown)
  - Top 5 threats panel (sorted High → Medium → Low)
  - 90-day threat trend graph

### Bulk Threat Level Changes
- Select multiple competitors → use **Bulk Update** to set them all to the same threat level at once
- Endpoint: `PUT /api/competitors/bulk-update` accepts a list of IDs + field updates

---

## 2. Removing Competitors

### Via the UI
- On the **Competitors** page, each competitor card has a delete button
- Deletion is a **soft delete** (`is_deleted = true`) — the record stays in the database but is hidden from all views
- This means it's recoverable if they change their mind

### Bulk Delete
- Select multiple competitors → **Bulk Delete** removes them all at once
- Endpoint: `DELETE /api/competitors/bulk-delete` accepts a list of IDs
- All deletions are logged in the activity audit trail

---

## 3. Adding New Competitors

### Option A: Manual Entry (UI Form)
- **Competitors** page → **Add Competitor** button
- Required field: **Name** only
- Optional fields (30+ data points):
  - Website, Threat Level (defaults to Medium), Status
  - Pricing model, base price, product categories
  - Key features, certifications, integration partners
  - Target segments, customer size focus, geographic focus
  - Customer count, acquisition rate, key customers
  - Employee count, growth rate, G2 rating
  - Year founded, headquarters, funding total
  - Latest round, PE/VC backers, website traffic
  - Social following, recent launches, news mentions
- On save, the system **automatically**:
  - Detects if it's a public company (auto-populates ticker symbol & exchange)
  - Triggers AI source discovery (finds relevant data sources)
  - Runs data quality verification
  - Performs URL refinement for source citations

### Option B: AI Discovery Scout (Recommended for Finding New Competitors)
- Navigate to the **Discovery** feature
- Set criteria:
  - Target market segments
  - Required capabilities
  - Geography
  - Funding stages
  - Employee range
  - Companies to exclude
- The AI runs a 4-stage pipeline:
  1. **Search** — finds candidates via web search
  2. **Scrape** — extracts detailed company data
  3. **Qualify** — evaluates against the user's criteria
  4. **Analyze** — assigns threat assessment and scoring
- Results come back with sources and citations (no hallucinated data)
- User can then add qualified candidates to the competitor list

### Option C: Bulk Import
- `POST /api/competitors/bulk-update` accepts JSON payloads for importing multiple competitors at once
- Can be used for CSV/spreadsheet imports with a simple data transformation

---

## 4. Data Export (Complementary Feature to Mention)

If they want to review the current competitor list before making changes:
- **Export formats**: Excel, CSV, JSON, PDF
- **What's exported**: All 20+ fields per competitor (name, website, threat level, pricing, customers, funding, etc.)
- **Other exports available**: Changelog (CSV), Battlecards (Excel/CSV/JSON), Dashboard (PDF with charts), Executive Summary (PDF/PPTX)

---

## 5. Audit Trail & Change Approval

### Every Change is Tracked
- Who made the change, when, what the old and new values were
- Viewable in the **Records** page and **Admin > Audit Logs**
- Exportable as CSV

### Optional Approval Workflow
- Non-admin users can submit changes as **Pending Changes**
- Admin users see pending changes and can approve or reject them
- This is useful if they want a review gate before data modifications

---

## 6. Role Permissions for Competitor Management

| Action | Viewer | Analyst | Admin |
|--------|--------|---------|-------|
| View competitors | Yes | Yes | Yes |
| Add competitors | No | Yes | Yes |
| Edit/update competitors | No | Yes | Yes |
| Delete competitors | No | Yes | Yes |
| Bulk operations | No | Yes | Yes |
| Approve pending changes | No | No | Yes |
| System settings & prompts | No | No | Yes |

---

## Talking Points for the Meeting

1. **"How do I move competitors up the threat list?"**
   → Click into the competitor, change Threat Level to High/Medium/Low, save. Dashboard updates automatically. Can also do it in bulk.

2. **"How do I remove competitors?"**
   → Delete from the competitor card. It's a soft delete — recoverable if needed. Bulk delete available for multiple at once.

3. **"How do I add new competitors?"**
   → Two approaches: Manual entry (just a name to start) or the AI Discovery Scout which finds and qualifies competitors automatically based on your criteria. Both auto-enrich with public company data and source discovery.

4. **Proactive suggestion**: Offer to run a Discovery Scout session during the meeting to demonstrate the AI finding new competitors based on their specific criteria. This is usually the "wow" moment.

5. **Proactive suggestion**: Offer to export their current competitor list to Excel first, so they can review it offline and come back with specific adds/removes/re-rankings.

---

## Potential Questions & Answers

**Q: Can I undo a deletion?**
A: Yes, deletions are soft deletes. The data is preserved and can be restored.

**Q: What if I add a competitor that already exists?**
A: The system allows it (no unique constraint on name), but the Discovery Scout has deduplication built in.

**Q: Can I import from a spreadsheet?**
A: The bulk update API accepts JSON. A CSV/Excel can be converted to JSON for import. The Knowledge Base also supports document uploads (PDF, DOCX) for enriching competitor intelligence.

**Q: How many competitors can the system handle?**
A: Currently tracking 74 competitors, 789 products, 920 news articles. SQLite handles this scale well for a single-org deployment.

**Q: Who can see the changes I make?**
A: All changes are logged with your email and timestamp. Admins can view the full audit trail in Records/Admin pages.
