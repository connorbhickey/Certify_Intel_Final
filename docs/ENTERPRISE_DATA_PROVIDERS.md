# Enterprise Data Provider Integration Guide

Certify Intel v8.3.0 supports 10 enterprise data providers for automated competitor intelligence enrichment. Each provider is a plug-and-play adapter -- paste your API key into `.env` and it activates automatically.

---

## Quick Setup

1. Open `backend/.env`
2. Paste your API key(s) for any provider below
3. Restart the backend server
4. Check Settings page -> "Enterprise Data Providers" to confirm activation

---

## Provider Reference

### Tier 1 (Healthcare CI Priority)

#### PitchBook
- **Env Vars**: `PITCHBOOK_API_KEY`, `PITCHBOOK_API_SECRET`
- **Enriches**: Revenue, funding rounds, valuations, investors, deal history
- **Rate Limit**: 100 requests/minute
- **Get API Key**: Contact PitchBook sales (https://pitchbook.com/data/api)
- **Notes**: Gold standard for financial data. Requires enterprise subscription.

#### Crunchbase
- **Env Vars**: `CRUNCHBASE_API_KEY`
- **Enriches**: Funding total, employee count, founded year, headquarters, investors, categories
- **Rate Limit**: 200 requests/minute
- **Get API Key**: https://data.crunchbase.com/docs/using-the-api (free tier available, 200 calls/min)
- **Notes**: Best for startup/growth company data. Free tier sufficient for most use cases.

#### S&P Capital IQ
- **Env Vars**: `SP_CAPITAL_IQ_API_KEY`, `SP_CAPITAL_IQ_API_SECRET`
- **Enriches**: Revenue, market cap, credit ratings, financial ratios, industry classifications
- **Rate Limit**: 50 requests/minute
- **Get API Key**: Contact S&P Global Market Intelligence (https://www.spglobal.com/marketintelligence/en/solutions/sp-capital-iq-pro)
- **Notes**: Enterprise-only. Best for public company financials and credit data.

#### Bloomberg
- **Env Vars**: `BLOOMBERG_API_KEY`
- **Enriches**: Market data, financial statements, analyst estimates, ESG scores
- **Rate Limit**: 60 requests/minute
- **Get API Key**: Bloomberg Terminal subscription required (https://www.bloomberg.com/professional/solution/bloomberg-terminal/)
- **Notes**: Most expensive provider. Adapter code only -- requires Bloomberg Terminal or B-PIPE.

### Tier 2 (Supplemental)

#### LSEG (Refinitiv)
- **Env Vars**: `LSEG_API_KEY`, `LSEG_APP_KEY`
- **Enriches**: Financial data, ESG scores, M&A activity, ownership
- **Rate Limit**: 60 requests/minute
- **Get API Key**: https://developers.lseg.com/

#### CB Insights
- **Env Vars**: `CB_INSIGHTS_API_KEY`
- **Enriches**: Market maps, competitive positioning, funding, technology signals
- **Rate Limit**: 60 requests/minute
- **Get API Key**: Contact CB Insights sales (https://www.cbinsights.com/)

#### Dealroom
- **Env Vars**: `DEALROOM_API_KEY`
- **Enriches**: Funding, team size, tech stack, growth signals
- **Rate Limit**: 60 requests/minute
- **Get API Key**: https://dealroom.co/

#### Preqin
- **Env Vars**: `PREQIN_API_KEY`
- **Enriches**: PE/VC fund data, investments, AUM
- **Rate Limit**: 30 requests/minute
- **Get API Key**: https://www.preqin.com/

#### Orbis (Bureau van Dijk / Moody's)
- **Env Vars**: `ORBIS_API_KEY`, `ORBIS_API_SECRET`
- **Enriches**: Corporate structure, beneficial owners, financials, compliance
- **Rate Limit**: 60 requests/minute
- **Get API Key**: https://www.bvdinfo.com/en-us/our-products/data/international/orbis

#### FactSet
- **Env Vars**: `FACTSET_API_KEY`, `FACTSET_API_SECRET`
- **Enriches**: Estimates, fundamentals, ownership, supply chain
- **Rate Limit**: 120 requests/minute
- **Get API Key**: https://developer.factset.com/

---

## Field Mapping Reference

| Competitor Field | PB | CB | S&P | BB | LSEG | CBI | DR | PQ | Orbis | FS |
|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| employee_count | x | x | | | | | x | | x | |
| funding_total | x | x | | | | x | x | | | |
| headquarters | x | x | | | | | x | | x | |
| year_founded | x | x | | | | | | | x | |
| revenue / estimated_revenue | x | x | x | x | x | | | | x | x |
| pe_vc_backers | x | x | | | | | | x | | |
| latest_round | x | x | | | | | x | | | |
| product_categories | | x | x | | | x | x | | | |
| g2_rating | | | | | | | | | | |

**Legend**: PB=PitchBook, CB=Crunchbase, S&P=Capital IQ, BB=Bloomberg, CBI=CB Insights, DR=Dealroom, PQ=Preqin, FS=FactSet

---

## Data Confidence

Enterprise providers are assigned the highest confidence in the data triangulation pipeline:

| Source Type | Confidence Range |
|:---|:---|
| Enterprise API (PitchBook, S&P, Bloomberg) | 90-98% |
| Official Website | 80-85% |
| News Article | 70-75% |
| AI-Extracted (Gemini search) | 65-75% |
| Unknown / Unverified | 50% |

---

## API Endpoints

### Check Provider Status
```
GET /api/admin/data-providers/status
```
Returns all 10 providers with configured/unconfigured status.

### Test Provider Connection
```
POST /api/admin/data-providers/test/{provider_name}
```
Makes minimal API call to verify connectivity.

### Enrich from Providers
```
POST /api/admin/enrich-from-providers
```
Background task: enriches all competitors using active enterprise providers.

---

## Troubleshooting

### Provider shows "unconfigured"
- Verify the env var name matches exactly (case-sensitive)
- Restart the backend after changing `.env`
- Check `Settings -> Enterprise Data Providers` for status

### "Connection failed" on test
- Verify API key is valid and not expired
- Check network/firewall allows outbound HTTPS to provider domain
- Some providers require IP whitelisting

### Rate limit errors
- Each provider has built-in rate limiting
- If you see rate limit warnings in logs, reduce concurrent operations
- PitchBook and S&P have strict limits; Crunchbase is more generous

---

*Last Updated: February 13, 2026*
