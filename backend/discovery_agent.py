"""
Certify Intel - Autonomous Competitor Discovery Agent (v5.0.2)
Uses DuckDuckGo search + Playwright scraping + AI qualification to discover new competitors.

v5.0.2: Added Gemini support for cost-effective AI qualification.
"""
import asyncio
import re
import time
import os
from typing import List, Dict, Any, Tuple
from datetime import datetime

# DuckDuckGo Search - Zero Cost
try:
    from duckduckgo_search import DDGS
    DDGS_AVAILABLE = True
except ImportError:
    DDGS_AVAILABLE = False
    print("Warning: duckduckgo-search not installed. Run: pip install duckduckgo-search")

# Playwright for scraping
try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("Warning: playwright not installed. Run: pip install playwright && playwright install chromium")

# OpenAI for advanced qualification (optional)
try:
    import openai
    OPENAI_AVAILABLE = bool(os.getenv("OPENAI_API_KEY"))
except ImportError:
    OPENAI_AVAILABLE = False

# Gemini for cost-effective qualification (v5.0.2)
try:
    from gemini_provider import GeminiProvider
    GEMINI_AVAILABLE = bool(os.getenv("GOOGLE_AI_API_KEY"))
except ImportError:
    GEMINI_AVAILABLE = False


class DiscoveryAgent:
    """
    Autonomous Competitor Discovery Agent using Zero-Cost tools (DuckDuckGo + Heuristics).

    v5.0.2: Supports both OpenAI GPT and Google Gemini for AI qualification.
    Gemini is ~90% cheaper for bulk qualification tasks.
    """

    def __init__(self, use_live_search: bool = True, use_ai: bool = False, use_openai: bool = None, prefer_provider: str = None):
        """
        Initialize the Discovery Agent.

        Args:
            use_live_search: If True, use real DuckDuckGo search. If False, use seed list.
            use_ai: If True, use AI for advanced qualification (Gemini or OpenAI).
            use_openai: Alias for use_ai (backwards compatibility).
            prefer_provider: "gemini", "openai", or None (auto-select based on config/availability).
        """
        self.use_live_search = use_live_search and DDGS_AVAILABLE

        # Support both use_ai and use_openai for backwards compatibility
        effective_use_ai = use_ai or (use_openai if use_openai is not None else False)

        # v5.0.2: Determine AI provider
        self.prefer_provider = prefer_provider or os.getenv("AI_PROVIDER", "hybrid")
        self.use_ai = effective_use_ai and (OPENAI_AVAILABLE or GEMINI_AVAILABLE)
        self.use_openai = self.use_ai  # Backwards compatibility

        # Initialize Gemini provider if available
        self.gemini_provider = None
        if GEMINI_AVAILABLE:
            try:
                self.gemini_provider = GeminiProvider()
            except Exception as e:
                print(f"Warning: Failed to initialize Gemini: {e}")

        # Load Certify Health DNA Profile from JSON
        self.profile = self._load_profile()

        # Rate limiting
        self.search_delay = 2.0  # seconds between searches
        self.last_search_time = 0

    def _get_ai_provider(self) -> str:
        """Determine which AI provider to use for qualification."""
        if not self.use_ai:
            return "none"

        # For discovery (bulk qualification), prefer cheaper provider
        bulk_pref = os.getenv("AI_BULK_TASKS", "gemini")

        if self.prefer_provider == "openai" and OPENAI_AVAILABLE:
            return "openai"
        elif self.prefer_provider == "gemini" and self.gemini_provider and self.gemini_provider.is_available:
            return "gemini"
        elif self.prefer_provider == "hybrid":
            # For bulk tasks, prefer Gemini (cheaper)
            if bulk_pref == "gemini" and self.gemini_provider and self.gemini_provider.is_available:
                return "gemini"
            elif OPENAI_AVAILABLE:
                return "openai"
            elif self.gemini_provider and self.gemini_provider.is_available:
                return "gemini"

        # Fallback to whatever is available
        if self.gemini_provider and self.gemini_provider.is_available:
            return "gemini"
        elif OPENAI_AVAILABLE:
            return "openai"

        return "none"
        
    def _load_profile(self) -> Dict[str, Any]:
        """Load context profile from JSON file."""
        import json
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            context_path = os.path.join(current_dir, "certify_context.json")
            
            if not os.path.exists(context_path):
                print(f"[WARNING] Context file not found at {context_path}. Using empty profile.")
                return {
                    "core_keywords": [], "market_keywords": [],
                    "required_context": [], "negative_keywords": [], "known_competitors": []
                }

            with open(context_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"[WARNING] Error loading context file: {e}")
            return {
                "core_keywords": [], "market_keywords": [], 
                "required_context": [], "negative_keywords": [], "known_competitors": []
            }
        
    async def run_discovery_loop(self, max_candidates: int = 10) -> List[Dict[str, Any]]:
        """
        Run the full discovery loop.
        
        Args:
            max_candidates: Maximum number of candidates to return.
            
        Returns:
            List of discovered competitor candidates with scores.
        """
        print("=" * 60)
        print("🔍 CERTIFY SCOUT - Autonomous Discovery Loop")
        print("=" * 60)
        print(f"Mode: {'LIVE SEARCH' if self.use_live_search else 'SEED LIST'}")
        print(f"OpenAI: {'ENABLED' if self.use_openai else 'DISABLED'}")
        print("-" * 60)
        
        candidates = []
        
        # 1. Generate Search Queries - Covering all 7 Products & 11 Markets
        queries = [
            # Product-focused queries
            "Phreesia competitors patient intake 2026",
            "patient experience platform healthcare software",
            "practice management system medical",
            "healthcare revenue cycle management companies",
            "patient payment collection software healthcare",
            "biometric patient identification healthcare",
            "ehr integration platform fhir hl7",
            "ai medical scribe clinical documentation",
            "digital front door healthcare solutions",
            "patient self-scheduling software medical",
            # Market-focused queries  
            "hospital patient intake software",
            "ambulatory care practice management",
            "urgent care check-in software",
            "behavioral health practice management software",
            "telehealth platform patient engagement",
            "dental DSO practice management software",
            "long-term care patient management",
            "laboratory patient scheduling software",
            "multi-specialty group practice software",
            # Competitor-focused queries
            "Phreesia alternatives 2026",
            "athenahealth competitors healthcare",
            "Epic alternatives patient engagement",
            "Clearwave competitors patient check-in"
        ]
        
        found_urls = set()
        raw_results = []
        
        # 2. Execute Search
        if self.use_live_search:
            print("📡 Executing LIVE DuckDuckGo searches...")
            raw_results = await self._execute_live_search(queries, found_urls)
        else:
            print("📦 Using SEED LIST (fallback mode)...")
            raw_results = self._get_seed_list(found_urls)
        
        print(f"\n📊 Found {len(raw_results)} unique candidate URLs\n")
        
        # 3. Qualify Candidates (Scrape & Score)
        print("🔬 Qualifying candidates...")
        qualified = 0
        for idx, res in enumerate(raw_results[:max_candidates * 2]):  # Process extra to ensure we get enough
            if qualified >= max_candidates:
                break
                
            print(f"  [{idx+1}/{len(raw_results)}] Analyzing {res['href'][:50]}...")
            
            score, data = await self._qualify_candidate(res['href'])
            
            if score >= 50:  # Qualification threshold
                candidates.append({
                    "name": self._extract_name_from_url(res['href']),
                    "url": res['href'],
                    "title": res.get('title', 'Unknown'),
                    "snippet": res.get('body', ''),
                    "relevance_score": score,
                    "reasoning": data.get("reasoning", "Matched keywords"),
                    "status": "Discovered",
                    "discovered_at": datetime.utcnow().isoformat()
                })
                print(f"    [OK] QUALIFIED ({score}%) - {data.get('reasoning', '')[:50]}")
                qualified += 1
            else:
                reason = data.get("reasoning") or data.get("error", "Low score")
                print(f"    [X] REJECTED ({score}%) - {reason[:50]}")
        
        print("\n" + "=" * 60)
        print(f"[DONE] Discovery Complete: {len(candidates)} qualified candidates")
        print("=" * 60)
        
        return candidates
    
    async def _execute_live_search(self, queries: List[str], found_urls: set) -> List[Dict]:
        """Execute real DuckDuckGo searches with rate limiting."""
        results = []
        
        for query in queries:
            # Rate limiting
            elapsed = time.time() - self.last_search_time
            if elapsed < self.search_delay:
                await asyncio.sleep(self.search_delay - elapsed)
            
            try:
                print(f"  [SEARCH] Searching: '{query}'")
                with DDGS() as ddgs:
                    search_results = list(ddgs.text(query, max_results=5))
                    
                    for r in search_results:
                        url = r.get('href', r.get('link', ''))
                        if url and url not in found_urls and not self._is_ignored(url):
                            found_urls.add(url)
                            results.append({
                                "href": url,
                                "title": r.get('title', ''),
                                "body": r.get('body', r.get('snippet', ''))
                            })
                    
                    print(f"     Found {len(search_results)} results, {len(results)} unique so far")
                    
                self.last_search_time = time.time()
                
            except Exception as e:
                print(f"     [WARNING] Search failed: {e}")
                continue
        
        return results
    
    def _get_seed_list(self, found_urls: set) -> List[Dict]:
        """Return seed list for MVP/fallback mode."""
        seed_candidates = [
            {"href": "https://www.klara.com", "title": "Klara", "body": "Patient communication platform"},
            {"href": "https://www.mend.com", "title": "Mend", "body": "Telehealth and patient engagement"},
            {"href": "https://www.notablehealth.com", "title": "Notable Health", "body": "AI-powered intake automation"},
            {"href": "https://www.qure4u.com", "title": "Qure4u", "body": "Virtual care and patient engagement"},
            {"href": "https://www.yosi.health", "title": "Yosi Health", "body": "Digital patient intake"},
            {"href": "https://www.healow.com", "title": "Healow", "body": "Patient portal and telehealth"},
            {"href": "https://www.solutionreach.com", "title": "Solutionreach", "body": "Patient communication"},
            {"href": "https://www.lumahealth.io", "title": "Luma Health", "body": "Patient access platform"},
        ]
        
        results = []
        for seed in seed_candidates:
            if seed['href'] not in found_urls and not self._is_ignored(seed['href']):
                found_urls.add(seed['href'])
                results.append(seed)
        
        return results

    def _is_ignored(self, url: str) -> bool:
        """Filter out non-company pages (reviews, news, social)."""
        ignored_domains = [
            "g2.com", "capterra.com", "linkedin.com", "facebook.com", 
            "twitter.com", "wikipedia.org", "youtube.com", "indeed.com",
            "glassdoor.com", "softwareadvice.com", "getapp.com", "reddit.com",
            "crunchbase.com", "bloomberg.com", "forbes.com", "techcrunch.com",
            "prnewswire.com", "businesswire.com", "globenewswire.com"
        ]
        url_lower = url.lower()
        for domain in ignored_domains:
            if domain in url_lower:
                return True
        return False

    async def _qualify_candidate(self, url: str) -> Tuple[int, Dict]:
        """
        Scrape URL and calculate relevance score (0-100).

        v5.0.2: Supports Gemini for cost-effective AI qualification.
        """
        # Determine which AI provider to use
        ai_provider = self._get_ai_provider()

        if ai_provider == "gemini":
            return await self._qualify_with_gemini(url)
        elif ai_provider == "openai":
            return await self._qualify_with_openai(url)

        # Otherwise use heuristic scoring (no AI)
        return await self._qualify_with_heuristics(url)
    
    async def _qualify_with_heuristics(self, url: str) -> Tuple[int, Dict]:
        """Use Playwright + keyword matching for qualification."""
        if not PLAYWRIGHT_AVAILABLE:
            # Basic URL-based scoring if Playwright not available
            return self._basic_url_score(url)

        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    text_content = await page.evaluate("document.body.innerText")
                    text_lower = text_content.lower()[:5000]  # Analyze first 5k chars
                    
                    score = 0
                    matches = []
                    
                    # 1. Context Check (Must have healthcare context)
                    if not any(k in text_lower for k in self.profile["required_context"]):
                        await browser.close()
                        return 0, {"reasoning": "Missing healthcare context"}
                    score += 20
                    
                    # 2. Core Keywords (15 points each, up to 60)
                    for kw in self.profile["core_keywords"]:
                        if kw in text_lower:
                            score += 15
                            matches.append(kw)
                            if score >= 80:  # Cap keyword score
                                break
                    
                    # 3. Known competitor mention (10 points)
                    for comp in self.profile["known_competitors"]:
                        if comp in text_lower:
                            score += 10
                            break
                    
                    # 4. Negative Check (punish review/list sites)
                    title = await page.title()
                    title_lower = title.lower()
                    for neg in self.profile["negative_keywords"]:
                        if neg in title_lower or neg in text_lower[:500]:
                            score -= 20
                            break
                    
                    reasoning = f"Matched: {', '.join(matches[:3])}" if matches else "Healthcare context only"
                    await browser.close()
                    return max(0, min(score, 100)), {"reasoning": reasoning}
                    
                except Exception as e:
                    await browser.close()
                    return 0, {"error": str(e)[:50]}
                    
        except Exception as e:
            return 0, {"error": str(e)[:50]}
    
    def _basic_url_score(self, url: str) -> Tuple[int, Dict]:
        """Basic scoring based on URL patterns only."""
        url_lower = url.lower()
        score = 40  # Base score
        
        # Healthcare-related TLD/keywords in URL
        if any(kw in url_lower for kw in ["health", "medical", "patient", "care", "clinic"]):
            score += 20
        
        # .com domains get slight boost
        if ".com" in url_lower:
            score += 10
        
        return score, {"reasoning": "URL pattern matching (no scraping)"}
    
    async def _qualify_with_openai(self, url: str) -> Tuple[int, Dict]:
        """Use GPT to analyze and qualify a competitor."""
        # First scrape the page
        text_content = ""
        if PLAYWRIGHT_AVAILABLE:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    text_content = await page.evaluate("document.body.innerText")
                    text_content = text_content[:3000]  # Limit tokens
                    await browser.close()
            except Exception:
                pass
        
        if not text_content:
            return 0, {"error": "Could not scrape page"}
        
        try:

            # Prepare Context for System Prompt
            core_keywords = ", ".join(self.profile.get("core_keywords", [])[:10])
            market_keywords = ", ".join(self.profile.get("market_keywords", [])[:10])
            exclusions = ", ".join(self.profile.get("exclusions", []))
            
            system_prompt = f"""You are a competitive intelligence analyst for Certify Health.
            
            About Certify Health:
            - Core Solutions: {core_keywords}
            - Target Market: {market_keywords}
            - Exclusions (NOT Competitors): {exclusions}
            
            Your job is to analyze website content and strictly determine if the company is a DIRECT COMPETITOR offering similar healthcare IT solutions.
            """

            client = openai.OpenAI()
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": f"""Analyze this website content.
                        
                        URL: {url}
                        Content Snippet: {text_content}
                        
                        Determine:
                        1. Is this a healthcare IT company?
                        2. Do they offer solutions competing with Certify Health (e.g., patient intake, RCM)?
                        3. Assign a Threat Score (0-100). 0 = Irrelevant, 100 = Direct Competitor.
                        4. Provide brief reasoning.

                        Respond in JSON format: {{"is_healthcare_it": bool, "is_competitor": bool, "score": int, "reasoning": string}}"""
                    }
                ],
                max_tokens=250,
                response_format={"type": "json_object"}
            )
            
            result = response.choices[0].message.content
            import json
            data = json.loads(result)
            
            score = data.get("score", 0)
            
            # Double check exclusions via rule-based override if LLM missed it
            if any(exc in text_content.lower() for exc in self.profile.get("exclusions", [])):
                 if score > 20: 
                     score = 20
                     data["reasoning"] = f"Low score due to exclusion keyword match. {data.get('reasoning','')}"

            return score, {"reasoning": data.get("reasoning", "GPT analysis"), "provider": "openai"}

        except Exception as e:
            # Fall back to heuristics
            return await self._qualify_with_heuristics(url)

    async def _qualify_with_gemini(self, url: str) -> Tuple[int, Dict]:
        """
        Use Gemini to analyze and qualify a competitor.

        v5.0.2: Cost-effective AI qualification (~90% cheaper than OpenAI).
        """
        # First scrape the page
        text_content = ""
        if PLAYWRIGHT_AVAILABLE:
            try:
                async with async_playwright() as p:
                    browser = await p.chromium.launch(headless=True)
                    page = await browser.new_page()
                    await page.goto(url, timeout=15000, wait_until="domcontentloaded")
                    text_content = await page.evaluate("document.body.innerText")
                    text_content = text_content[:4000]  # Gemini can handle more tokens
                    await browser.close()
            except Exception:
                pass

        if not text_content:
            return 0, {"error": "Could not scrape page"}

        try:
            # Prepare Context for System Prompt
            core_keywords = ", ".join(self.profile.get("core_keywords", [])[:10])
            market_keywords = ", ".join(self.profile.get("market_keywords", [])[:10])
            exclusions = ", ".join(self.profile.get("exclusions", []))

            system_prompt = f"""You are a competitive intelligence analyst for Certify Health.

About Certify Health:
- Core Solutions: {core_keywords}
- Target Market: {market_keywords}
- Exclusions (NOT Competitors): {exclusions}

Your job is to analyze website content and strictly determine if the company is a DIRECT COMPETITOR offering similar healthcare IT solutions."""

            user_prompt = f"""Analyze this website content.

URL: {url}
Content Snippet: {text_content}

Determine:
1. Is this a healthcare IT company?
2. Do they offer solutions competing with Certify Health (e.g., patient intake, RCM)?
3. Assign a Threat Score (0-100). 0 = Irrelevant, 100 = Direct Competitor.
4. Provide brief reasoning.

Respond in JSON format: {{"is_healthcare_it": true/false, "is_competitor": true/false, "score": 0-100, "reasoning": "brief explanation"}}"""

            result = self.gemini_provider.generate_json(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.1
            )

            score = result.get("score", 0)

            # Double check exclusions via rule-based override
            if any(exc in text_content.lower() for exc in self.profile.get("exclusions", [])):
                if score > 20:
                    score = 20
                    result["reasoning"] = f"Low score due to exclusion keyword match. {result.get('reasoning', '')}"

            return score, {
                "reasoning": result.get("reasoning", "Gemini analysis"),
                "provider": "gemini",
                "cost": result.get("_cost", 0)
            }

        except Exception as e:
            # Fall back to heuristics
            return await self._qualify_with_heuristics(url)

    def _extract_name_from_url(self, url: str) -> str:
        """Extract company name from URL."""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc
            name = domain.replace("www.", "").split(".")[0]
            return name.title()
        except Exception:
            return "Unknown"


# Entry point
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Certify Scout - Competitor Discovery Agent (v5.0.2)")
    parser.add_argument("--live", action="store_true", help="Use live DuckDuckGo search")
    parser.add_argument("--ai", action="store_true", help="Use AI for qualification (Gemini or OpenAI)")
    parser.add_argument("--provider", type=str, choices=["openai", "gemini", "hybrid"],
                        default=None, help="Prefer specific AI provider")
    parser.add_argument("--max", type=int, default=10, help="Maximum candidates to return")
    args = parser.parse_args()

    print(f"🔍 Certify Scout v5.0.2")
    print(f"   Gemini Available: {GEMINI_AVAILABLE}")
    print(f"   OpenAI Available: {OPENAI_AVAILABLE}")

    agent = DiscoveryAgent(
        use_live_search=args.live,
        use_ai=args.ai,
        prefer_provider=args.provider
    )

    if args.ai:
        print(f"   AI Provider: {agent._get_ai_provider()}")

    results = asyncio.run(agent.run_discovery_loop(max_candidates=args.max))

    print("\n📋 Final Results:")
    for r in results:
        provider = r.get("provider", "heuristics")
        print(f"  - {r['name']} ({r['relevance_score']}%): {r['url']} [{provider}]")
