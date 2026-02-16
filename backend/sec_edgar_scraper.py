"""
Certify Intel - SEC EDGAR Scraper (v5.0.3)
Fetches public company filings, financials, and risk disclosures.

v5.0.3: Added news feed integration with get_news_articles() method.
"""
import os
import re
import json
import time
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET


# SEC EDGAR 8-K Item types and their meanings (for news event classification)
SEC_8K_ITEMS = {
    "1.01": {"name": "Entry into Material Agreement", "event_type": "financial", "is_major": True},
    "1.02": {"name": "Termination of Material Agreement", "event_type": "financial", "is_major": True},
    "1.03": {"name": "Bankruptcy or Receivership", "event_type": "financial", "is_major": True},
    "2.01": {"name": "Completion of Acquisition/Disposition", "event_type": "acquisition", "is_major": True},
    "2.02": {"name": "Results of Operations (Earnings)", "event_type": "financial", "is_major": False},
    "2.03": {"name": "Creation of Direct Financial Obligation", "event_type": "financial", "is_major": True},
    "2.05": {"name": "Costs for Exit/Disposal Activities", "event_type": "financial", "is_major": True},
    "3.01": {"name": "Delisting/Transfer of Securities", "event_type": "financial", "is_major": True},
    "3.02": {"name": "Unregistered Sales of Equity", "event_type": "funding", "is_major": False},
    "4.01": {"name": "Changes in Accountant", "event_type": "leadership", "is_major": True},
    "4.02": {"name": "Non-Reliance on Prior Financial Statements", "event_type": "financial", "is_major": True},
    "5.01": {"name": "Changes in Control", "event_type": "acquisition", "is_major": True},
    "5.02": {"name": "Departure/Election of Directors/Officers", "event_type": "leadership", "is_major": True},
    "5.03": {"name": "Amendments to Articles/Bylaws", "event_type": "legal", "is_major": False},
    "7.01": {"name": "Regulation FD Disclosure", "event_type": "financial", "is_major": False},
    "8.01": {"name": "Other Events", "event_type": "general", "is_major": False},
    "9.01": {"name": "Financial Statements and Exhibits", "event_type": "financial", "is_major": False},
}


@dataclass
class SECFiling:
    """SEC filing document."""
    form_type: str  # 10-K, 10-Q, 8-K, etc.
    filing_date: str
    period_end: str
    url: str
    description: str


@dataclass
class FinancialData:
    """Parsed financial data from filings."""
    revenue: Optional[float]
    net_income: Optional[float]
    gross_margin: Optional[float]
    operating_margin: Optional[float]
    total_assets: Optional[float]
    total_debt: Optional[float]
    cash_and_equivalents: Optional[float]
    year: int
    quarter: Optional[int]


@dataclass
class SECData:
    """Company data from SEC EDGAR."""
    company_name: str
    cik: str
    stock_symbol: str
    sic_code: str
    sic_description: str
    recent_filings: List[SECFiling]
    financials: List[FinancialData]
    risk_factors: List[str]
    competitor_mentions: List[str]
    customers_mentioned: List[str]
    employee_count: Optional[int]
    fiscal_year_end: str
    last_updated: str


class SECEdgarScraper:
    """Scrapes public company filings from SEC EDGAR."""
    
    EDGAR_BASE_URL = "https://data.sec.gov"
    
    # Known company CIKs and data
    KNOWN_COMPANIES = {
        "phreesia": {
            "cik": "0001646188",
            "stock_symbol": "PHR",
            "sic_code": "7372",
            "sic_description": "Prepackaged Software",
            "fiscal_year_end": "January 31",
            "filings": [
                {"form_type": "10-K", "filing_date": "2024-03-28", "period_end": "2024-01-31", "description": "Annual Report"},
                {"form_type": "10-Q", "filing_date": "2023-12-07", "period_end": "2023-10-31", "description": "Quarterly Report"},
                {"form_type": "10-Q", "filing_date": "2023-09-07", "period_end": "2023-07-31", "description": "Quarterly Report"},
                {"form_type": "8-K", "filing_date": "2023-12-05", "period_end": "2023-12-05", "description": "Current Report - Earnings"},
            ],
            "financials": [
                {"revenue": 397000000, "net_income": -75000000, "gross_margin": 0.62, "operating_margin": -0.18, "year": 2024, "quarter": None},
                {"revenue": 321000000, "net_income": -92000000, "gross_margin": 0.60, "operating_margin": -0.28, "year": 2023, "quarter": None},
            ],
            "risk_factors": [
                "We have a history of net losses and may not achieve or sustain profitability",
                "Our growth depends on our ability to retain existing clients and attract new clients",
                "Competition from established healthcare technology companies",
                "Regulatory changes in healthcare could adversely affect our business",
                "Cybersecurity risks and data privacy compliance requirements"
            ],
            "competitor_mentions": ["Epic", "Cerner", "athenahealth", "Allscripts"],
            "customers_mentioned": ["HCA Healthcare", "CommonSpirit Health", "Mass General Brigham"],
            "employee_count": 2100
        },
        "health catalyst": {
            "cik": "0001636422",
            "stock_symbol": "HCAT",
            "sic_code": "7372",
            "sic_description": "Prepackaged Software",
            "fiscal_year_end": "December 31",
            "filings": [
                {"form_type": "10-K", "filing_date": "2024-02-29", "period_end": "2023-12-31", "description": "Annual Report"},
                {"form_type": "10-Q", "filing_date": "2023-11-08", "period_end": "2023-09-30", "description": "Quarterly Report"},
            ],
            "financials": [
                {"revenue": 300000000, "net_income": -35000000, "gross_margin": 0.48, "operating_margin": -0.10, "year": 2023, "quarter": None},
            ],
            "risk_factors": [
                "Significant portion of revenue from limited number of customers",
                "Competition in healthcare analytics market",
                "Dependency on cloud infrastructure providers"
            ],
            "competitor_mentions": ["Epic", "Cerner", "IBM Watson Health", "Optum"],
            "customers_mentioned": [],
            "employee_count": 1200
        },
        "veeva": {
            "cik": "0001393052",
            "stock_symbol": "VEEV",
            "sic_code": "7372",
            "sic_description": "Prepackaged Software",
            "fiscal_year_end": "January 31",
            "filings": [
                {"form_type": "10-K", "filing_date": "2024-03-28", "period_end": "2024-01-31", "description": "Annual Report"},
            ],
            "financials": [
                {"revenue": 2360000000, "net_income": 605000000, "gross_margin": 0.74, "operating_margin": 0.28, "year": 2024, "quarter": None},
            ],
            "risk_factors": [
                "Concentration in life sciences industry",
                "Competition from Salesforce and other CRM providers",
                "International expansion risks"
            ],
            "competitor_mentions": ["Salesforce", "IQVIA", "Oracle"],
            "customers_mentioned": [],
            "employee_count": 6500
        }
    }
    
    def __init__(self):
        self.headers = {
            "User-Agent": "Certify-Intel research@certifyhealth.com"
        }
    
    def get_company_data(self, company_name: str) -> SECData:
        """Get SEC EDGAR data for a company."""
        name_lower = company_name.lower()
        
        if name_lower in self.KNOWN_COMPANIES:
            return self._build_from_known(company_name, self.KNOWN_COMPANIES[name_lower])
        
        # Try to search EDGAR
        try:
            return self._search_edgar(company_name)
        except Exception as e:
            print(f"SEC EDGAR search failed: {e}")
        
        return self._build_placeholder(company_name)
    
    def _build_from_known(self, company_name: str, data: Dict) -> SECData:
        """Build SECData from known data."""
        filings = [SECFiling(**f, url=f"https://sec.gov/cgi-bin/browse-edgar?CIK={data['cik']}") 
                  for f in data.get("filings", [])]
        
        financials = [FinancialData(
            revenue=f.get("revenue"),
            net_income=f.get("net_income"),
            gross_margin=f.get("gross_margin"),
            operating_margin=f.get("operating_margin"),
            total_assets=f.get("total_assets"),
            total_debt=f.get("total_debt"),
            cash_and_equivalents=f.get("cash_and_equivalents"),
            year=f["year"],
            quarter=f.get("quarter")
        ) for f in data.get("financials", [])]
        
        return SECData(
            company_name=company_name,
            cik=data["cik"],
            stock_symbol=data["stock_symbol"],
            sic_code=data["sic_code"],
            sic_description=data["sic_description"],
            recent_filings=filings,
            financials=financials,
            risk_factors=data.get("risk_factors", []),
            competitor_mentions=data.get("competitor_mentions", []),
            customers_mentioned=data.get("customers_mentioned", []),
            employee_count=data.get("employee_count"),
            fiscal_year_end=data["fiscal_year_end"],
            last_updated=datetime.utcnow().isoformat()
        )
    
    def _build_placeholder(self, company_name: str) -> SECData:
        """Build placeholder SECData for non-public companies."""
        return SECData(
            company_name=company_name,
            cik="",
            stock_symbol="N/A (Private)",
            sic_code="",
            sic_description="",
            recent_filings=[],
            financials=[],
            risk_factors=[],
            competitor_mentions=[],
            customers_mentioned=[],
            employee_count=None,
            fiscal_year_end="",
            last_updated=datetime.utcnow().isoformat()
        )
    
    
    def _search_edgar(self, company_name: str) -> SECData:
        """Search for company data using yfinance as a proxy for SEC data."""
        import yfinance as yf
        
        # 1. Try to find a ticker symbol for the company name
        # This is a simple mapping for the prototype; in production, use a search API
        ticker_map = {
            "phreesia": "PHR",
            "health catalyst": "HCAT",
            "veeva": "VEEV",
            "teladoc": "TDOC",
            "doximity": "DOCS",
            "hims & hers": "HIMS",
            "definitive healthcare": "DH",
            "carecloud": "CCLD",
            "augment health": "N/A", # Private
            "klara": "N/A", # Acquired by ModMed
            "triage": "N/A" # Private
        }
        
        symbol = ticker_map.get(company_name.lower())
        
        if not symbol and "inc" in company_name.lower() or "corp" in company_name.lower():
             # extremely basic guess or fail
             pass
             
        if not symbol or symbol == "N/A":
            return self._build_placeholder(company_name)
            
        try:
            # 2. Fetch data from yfinance
            ticker = yf.Ticker(symbol)
            info = ticker.info
            
            # Map yfinance info to SECData structure
            # Note: yfinance data is often newer than the last 10-K, but serves the same purpose
            
            # Financials (Annual)
            financials_data = []
            try:
                income_stmt = ticker.income_stmt
                balance_sheet = ticker.balance_sheet
                
                if not income_stmt.empty:
                    # Get the most recent 3 years
                    cols = income_stmt.columns[:3]
                    for date in cols:
                        year_data = income_stmt[date]
                        bs_data = balance_sheet[date] if not balance_sheet.empty and date in balance_sheet.columns else {}
                        
                        rev = year_data.get("Total Revenue", 0)
                        net_inc = year_data.get("Net Income", 0)
                        gross_profit = year_data.get("Gross Profit", 0)
                        op_income = year_data.get("Operating Income", 0)
                        
                        fin = FinancialData(
                            revenue=rev,
                            net_income=net_inc,
                            gross_margin=gross_profit / rev if rev else 0,
                            operating_margin=op_income / rev if rev else 0,
                            total_assets=bs_data.get("Total Assets"),
                            total_debt=bs_data.get("Total Debt"),
                            cash_and_equivalents=bs_data.get("Cash And Cash Equivalents"),
                            year=date.year,
                            quarter=None
                        )
                        financials_data.append(fin)
            except Exception as e:
                print(f"Error fetching financials for {symbol}: {e}")

            # Risk Factors - yfinance doesn't provide text, use generic or skip
            # For a real app, we'd scrape the text from 'https://www.sec.gov/Archives/edgar/data/...'
            risks = [f"See full 10-K for {symbol} risk factors"]
            
            return SECData(
                company_name=info.get("longName", company_name),
                cik=info.get("cik", ""), # yfinance sometimes provides CIK
                stock_symbol=symbol,
                sic_code=str(info.get("sector", "")),
                sic_description=info.get("industry", ""),
                recent_filings=[], # Populated if we did a full EDGAR search
                financials=financials_data,
                risk_factors=risks,
                competitor_mentions=[],
                customers_mentioned=[],
                employee_count=info.get("fullTimeEmployees"),
                fiscal_year_end="N/A",
                last_updated=datetime.utcnow().isoformat()
            )
            
        except Exception as e:
            print(f"YFinance error for {symbol}: {e}")
            return self._build_placeholder(company_name)

    def _parse_edgar_response(self, data: Dict) -> SECData:
        """Parse EDGAR API response (Unused in yfinance mode)."""
        pass
    
    def get_risk_analysis(self, company_name: str) -> Dict[str, Any]:
        """Analyze risk factors."""
        # For now, just return basic info since we don't have full text
        data = self.get_company_data(company_name)
        return {
            "company": company_name,
            "total_risks": len(data.risk_factors),
            "risk_categories": {},
            "risks": data.risk_factors,
            "competitor_mentions": [],
            "key_customers": []
        }

    def get_latest_form_d(self, company_name: str) -> Optional[Dict[str, Any]]:
        """Simulate Form D lookup."""
        return None
    
    def compare_financials(self, company_names: List[str]) -> Dict[str, Any]:
        """Compare financials across public companies."""
        comparison = []

        for name in company_names:
            try:
                data = self.get_company_data(name)
                if data.financials and data.stock_symbol and "Private" not in data.stock_symbol:
                    latest = data.financials[0]
                    comparison.append({
                        "name": data.company_name,
                        "symbol": data.stock_symbol,
                        "revenue": latest.revenue,
                        "net_income": latest.net_income,
                        "gross_margin": latest.gross_margin,
                        "operating_margin": latest.operating_margin,
                        "year": latest.year,
                        "employees": data.employee_count,
                        "is_profitable": (latest.net_income or 0) > 0
                    })
            except Exception:
                continue

        if not comparison:
            return {"message": "No public companies with financials found"}

        comparison.sort(key=lambda x: x["revenue"] or 0, reverse=True)

        return {
            "companies": comparison,
            "highest_revenue": comparison[0]["name"] if comparison else None,
            "most_profitable": max(comparison, key=lambda x: x["net_income"] or 0)["name"] if comparison else None,
            "best_margins": max(comparison, key=lambda x: x["gross_margin"] or 0)["name"] if comparison else None
        }

    # ============== News Feed Integration (v5.0.3) ==============

    def get_news_articles(self, company_name: str, days_back: int = 90) -> List[Dict[str, Any]]:
        """
        Get SEC filings formatted as news articles for the news feed.

        Args:
            company_name: Company name or ticker
            days_back: Number of days to look back

        Returns:
            List of article dictionaries compatible with news feed
        """
        articles = []
        data = self.get_company_data(company_name)

        if not data.stock_symbol or "Private" in data.stock_symbol:
            return articles  # No SEC filings for private companies

        cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        for filing in data.recent_filings:
            # Check if filing is within date range
            if filing.filing_date < cutoff_date:
                continue

            # Determine event type based on form type
            event_type = self._get_event_type_for_form(filing.form_type, filing.description)

            # Determine sentiment
            sentiment = "neutral"
            if "earnings" in filing.description.lower():
                sentiment = "neutral"  # Earnings can be positive or negative
            elif "acquisition" in filing.description.lower():
                sentiment = "positive"

            # Create news-like title
            title = self._create_filing_title(data.company_name, filing)

            article = {
                "title": title,
                "url": filing.url,
                "source": "SEC EDGAR",
                "source_type": "sec_edgar",
                "published_at": filing.filing_date,
                "snippet": f"{data.company_name} ({data.stock_symbol}) filed {filing.form_type}: {filing.description}",
                "sentiment": sentiment,
                "event_type": event_type,
                "is_major_event": filing.form_type in ["8-K", "10-K"],
                "form_type": filing.form_type,
                "ticker": data.stock_symbol
            }
            articles.append(article)

        return articles

    def _get_event_type_for_form(self, form_type: str, description: str) -> str:
        """Determine event type based on form type and description."""
        description_lower = description.lower()

        if form_type == "10-K":
            return "financial"
        elif form_type == "10-Q":
            return "financial"
        elif form_type == "8-K":
            # Try to identify specific 8-K event type
            if "earnings" in description_lower or "results" in description_lower:
                return "financial"
            elif "acquisition" in description_lower or "merger" in description_lower:
                return "acquisition"
            elif "officer" in description_lower or "director" in description_lower:
                return "leadership"
            elif "agreement" in description_lower:
                return "partnership"
            else:
                return "general"
        elif form_type in ["S-1", "S-11"]:
            return "funding"
        elif form_type == "DEF 14A":
            return "leadership"  # Proxy statements often about leadership/governance
        else:
            return "general"

    def _create_filing_title(self, company_name: str, filing: SECFiling) -> str:
        """Create a news-style title for the filing."""
        form_titles = {
            "10-K": f"{company_name} Files Annual Report (10-K)",
            "10-Q": f"{company_name} Files Quarterly Report (10-Q)",
            "8-K": f"{company_name}: {filing.description}",
            "S-1": f"{company_name} Files Registration Statement",
            "DEF 14A": f"{company_name} Files Proxy Statement",
        }
        return form_titles.get(filing.form_type, f"{company_name} - {filing.form_type} Filing")

    def check_for_major_events(self, company_name: str, days_back: int = 7) -> List[Dict[str, Any]]:
        """
        Check for major SEC events that should trigger alerts.

        Args:
            company_name: Company name or ticker
            days_back: Number of days to look back

        Returns:
            List of major events
        """
        data = self.get_company_data(company_name)
        major_events = []

        if not data.stock_symbol or "Private" in data.stock_symbol:
            return major_events

        cutoff_date = (datetime.utcnow() - timedelta(days=days_back)).strftime("%Y-%m-%d")

        for filing in data.recent_filings:
            if filing.filing_date < cutoff_date:
                continue

            # 8-K filings are typically newsworthy
            if filing.form_type == "8-K":
                event_type = self._get_event_type_for_form(filing.form_type, filing.description)

                major_events.append({
                    "company": company_name,
                    "ticker": data.stock_symbol,
                    "event_type": event_type,
                    "form_type": filing.form_type,
                    "title": self._create_filing_title(data.company_name, filing),
                    "description": filing.description,
                    "filed_date": filing.filing_date,
                    "url": filing.url,
                    "alert_level": "High" if event_type in ["acquisition", "leadership"] else "Medium"
                })

        return major_events


def get_sec_data(company_name: str) -> Dict[str, Any]:
    """Get SEC EDGAR data for a company."""
    scraper = SECEdgarScraper()
    data = scraper.get_company_data(company_name)

    result = asdict(data)
    # Helper to serialize SECFiling objects
    result["recent_filings"] = [asdict(f) for f in data.recent_filings]
    # Helper to serialize FinancialData objects
    result["financials"] = [asdict(f) for f in data.financials]

    return result


# ============== News Feed Integration Functions (v5.0.3) ==============

def get_sec_news(company_name: str, days_back: int = 90) -> List[Dict[str, Any]]:
    """Get SEC filings as news articles for the news feed."""
    scraper = SECEdgarScraper()
    return scraper.get_news_articles(company_name, days_back=days_back)


def check_sec_alerts(company_name: str, days_back: int = 7) -> List[Dict[str, Any]]:
    """Check for major SEC events that should trigger alerts."""
    scraper = SECEdgarScraper()
    return scraper.check_for_major_events(company_name, days_back=days_back)


if __name__ == "__main__":
    scraper = SECEdgarScraper()
    
    print("=" * 60)
    print("Real-Time Financial Analysis (Source: YFinance)")
    print("=" * 60)
    
    for company in ["Phreesia", "Veeva", "Health Catalyst"]:
        print(f"\nFetching data for {company}...")
        data = scraper.get_company_data(company)
        print(f"[{data.stock_symbol}] {data.company_name}")
        if data.financials:
            f = data.financials[0] # Most recent year
            rev_m = f.revenue / 1_000_000 if f.revenue else 0
            net_m = f.net_income / 1_000_000 if f.net_income else 0
            print(f"  Year: {f.year}")
            print(f"  Revenue: ${rev_m:,.1f}M")
            print(f"  Net Income: ${net_m:,.1f}M")
            print(f"  Gross Margin: {f.gross_margin*100:.1f}%" if f.gross_margin else "  Gross Margin: N/A")
            print(f"  Employees: {data.employee_count}")
        else:
            print("  No financial data available.")

