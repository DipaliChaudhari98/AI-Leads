"""
website_research_agents.py
Role   : Website Crawler Agent
Goal   : Visit company website from extracted lead, crawl homepage and important
         pages (About, Products, Services, Contact, Careers, Blog), extract clean
         readable text, and return structured JSON for downstream agents.
Rules  : Same domain only. Max depth 2. No summarization. No inference.
"""
import asyncio, logging, json, re
from pydantic import BaseModel
from crewai import Agent, Task, Crew
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("WebsiteCrawlerAgent")

IMPORTANT_KEYWORDS = ["about","product","service","solution","contact","career","blog","team","platform","feature"]
NOISE_TAGS = ["script","style","noscript","iframe","nav","header","footer","aside","form","button","input","select","textarea","svg","img","video","audio","figure","figcaption","meta","link","head"]

class CrawledPage(BaseModel):
    url: str
    title: str
    page_type: str
    clean_text: str
    word_count: int

class WebsiteCrawlerResult(BaseModel):
    website_url: str
    company_name: Optional[str] = None
    pages: List[CrawledPage] = []
    crawl_status: str = "pending"
    error: Optional[str] = None
    crawler: str = "playwright"
    crawl_time_ms: int = 0

    def to_json(self) -> Dict[str, Any]:
        return {
            "website_url": self.website_url,
            "company_name": self.company_name,
            "crawl_status": self.crawl_status,
            "crawler": self.crawler,
            "crawl_time_ms": self.crawl_time_ms,
            "pages_crawled": len(self.pages),
            "pages": [{"url":p.url,"title":p.title,"page_type":p.page_type,"word_count":p.word_count,"content":p.clean_text} for p in self.pages],
            "full_text": "\n\n".join(f"=== {p.page_type.upper()} ({p.url}) ===\n{p.clean_text}" for p in self.pages),
        }

class WebsiteResearchData(BaseModel):
    companyName: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    employeeCount: Optional[str] = None
    revenue: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    techStack: Optional[List[str]] = None
    products: Optional[List[str]] = None
    services: Optional[List[str]] = None
    socialLinks: Optional[Dict[str, str]] = None

class EnrichedCompanyProfile(BaseModel):
    companyName: Optional[str] = None
    industry: Optional[str] = None
    description: Optional[str] = None
    employeeCount: Optional[str] = None
    revenue: Optional[str] = None
    address: Optional[str] = None
    website: Optional[str] = None
    techStack: Optional[List[str]] = None
    products: Optional[List[str]] = None
    services: Optional[List[str]] = None
    socialLinks: Optional[Dict[str, str]] = None

def _classify_page_type(url: str) -> str:
    u = url.lower()
    for kw in ["about","team","company"]:
        if kw in u: return "about"
    for kw in ["product","platform","feature"]:
        if kw in u: return "products"
    for kw in ["service","solution","offering"]:
        if kw in u: return "services"
    for kw in ["contact","reach","support"]:
        if kw in u: return "contact"
    for kw in ["career","job","hire","talent"]:
        if kw in u: return "careers"
    for kw in ["blog","news","article","post","press"]:
        if kw in u: return "blog"
    return "homepage"

def _clean_raw_text(raw: str) -> str:
    """Remove duplicate lines, strip noise, collapse blanks, limit 4000 chars."""
    if not raw: return ""
    seen, cleaned = set(), []
    for line in raw.splitlines():
        s = line.strip()
        if not s or len(s) <= 2 or s in seen: continue
        seen.add(s)
        cleaned.append(s)
    result = re.sub(r"\n{3,}", "\n\n", "\n".join(cleaned))
    return result[:4000].strip()

class WebsiteCrawlerAgent:
    """
    Role   : Website Crawler Agent
    Goal   : Crawl company website from extracted lead data.
             Visit homepage + up to 5 important subpages (About/Products/Services/
             Contact/Careers/Blog) on the same domain (max depth 2).
             Extract clean readable text. Return structured JSON.
    Rules  : Same domain only. Max depth 2. No summarization. No inference.
    """
    MAX_SUBPAGES = 5

    def __init__(self):
        self._cache: Dict[str, WebsiteCrawlerResult] = {}

    @staticmethod
    def _normalize_url(url: str) -> str:
        url = url.strip()
        if not url.startswith(("http://","https://")): url = f"https://{url}"
        return url.rstrip("/")

    @staticmethod
    def _same_domain(url: str, domain: str) -> bool:
        n = urlparse(url).netloc
        return n == domain or n.endswith(f".{domain}")

    @staticmethod
    def _is_important(href: str) -> bool:
        return any(kw in href.lower() for kw in IMPORTANT_KEYWORDS)

    async def _playwright_crawl(self, root_url: str, company_name: Optional[str]) -> WebsiteCrawlerResult:
        import time
        from playwright.async_api import async_playwright
        start = time.time()
        domain = urlparse(root_url).netloc
        pages_data: List[CrawledPage] = []
        visited = {root_url}

        EXTRACT_JS = """() => {
            ['script','style','noscript','iframe','nav','header','footer','aside',
             'form','button','input','select','textarea','svg','img','video','audio']
            .forEach(tag => document.querySelectorAll(tag).forEach(el => el.remove()));
            const pat = /nav|menu|sidebar|cookie|popup|modal|banner|overlay/i;
            document.querySelectorAll('[class],[id]').forEach(el => {
                if (pat.test((el.className||'') + ' ' + (el.id||''))) el.remove();
            });
            return document.body ? document.body.innerText : '';
        }"""

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True, args=["--no-sandbox","--disable-setuid-sandbox","--disable-dev-shm-usage"])
            ctx = await browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                viewport={"width":1280,"height":800}
            )
            pw_page = await ctx.new_page()

            async def _crawl_single(url: str, ptype: str) -> Optional[CrawledPage]:
                try:
                    resp = await pw_page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    if resp and resp.status >= 400: return None
                    title = (await pw_page.title()) or ""
                    raw = await pw_page.evaluate(EXTRACT_JS)
                    clean = _clean_raw_text(raw)
                    if not clean: return None
                    return CrawledPage(url=url, title=title.strip(), page_type=ptype, clean_text=clean, word_count=len(clean.split()))
                except Exception as e:
                    logger.warning(f"Playwright crawl failed {url}: {e}")
                    return None

            logger.info(f"WebsiteCrawlerAgent: homepage -> {root_url}")
            hp = await _crawl_single(root_url, "homepage")
            if hp: pages_data.append(hp)

            hrefs = []
            try:
                hrefs = await pw_page.evaluate("() => Array.from(document.querySelectorAll('a[href]')).map(a=>a.href).filter(h=>h.startsWith('http'))")
            except Exception: pass

            subpages = []
            for href in hrefs:
                clean_href = href.split("#")[0].rstrip("/")
                if not self._same_domain(clean_href, domain): continue
                if clean_href in visited: continue
                if not self._is_important(clean_href): continue
                subpages.append(clean_href)
                visited.add(clean_href)
                if len(subpages) >= self.MAX_SUBPAGES: break

            for sub in subpages:
                ptype = _classify_page_type(sub)
                logger.info(f"WebsiteCrawlerAgent: [{ptype}] -> {sub}")
                pg = await _crawl_single(sub, ptype)
                if pg: pages_data.append(pg)

            await browser.close()

        ms = int((time.time()-start)*1000)
        return WebsiteCrawlerResult(
            website_url=root_url, company_name=company_name, pages=pages_data,
            crawl_status="success" if pages_data else "failed", crawler="playwright", crawl_time_ms=ms
        )

    async def _http_fallback(self, root_url: str, company_name: Optional[str]) -> WebsiteCrawlerResult:
        import time, requests
        from bs4 import BeautifulSoup
        start = time.time()
        domain = urlparse(root_url).netloc
        pages_data: List[CrawledPage] = []
        visited = {root_url}
        headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36"}

        def _fetch(url: str, ptype: str):
            try:
                resp = requests.get(url, headers=headers, timeout=12)
                if resp.status_code >= 400: return None, []
                soup = BeautifulSoup(resp.text, "html.parser")
                for tag in NOISE_TAGS:
                    for el in soup.find_all(tag): el.decompose()
                pat = re.compile(r"nav|menu|sidebar|ad|cookie|popup|modal|banner|footer|header", re.I)
                for el in soup.find_all(True, {"class": pat}): el.decompose()
                for el in soup.find_all(True, {"id": pat}): el.decompose()
                title = soup.title.string.strip() if soup.title and soup.title.string else ""
                clean = _clean_raw_text(soup.get_text(separator="\n"))
                if not clean: return None, []
                links = []
                if ptype == "homepage":
                    for a in soup.find_all("a", href=True):
                        h = urljoin(url, a["href"]).split("#")[0].rstrip("/")
                        if self._same_domain(h, domain) and h not in visited and self._is_important(h):
                            links.append(h); visited.add(h)
                return CrawledPage(url=url, title=title, page_type=ptype, clean_text=clean, word_count=len(clean.split())), links
            except Exception as e:
                logger.warning(f"HTTP fallback failed {url}: {e}")
                return None, []

        logger.info(f"WebsiteCrawlerAgent (HTTP): homepage -> {root_url}")
        hp, subpages = _fetch(root_url, "homepage")
        if hp: pages_data.append(hp)

        for sub in subpages[:self.MAX_SUBPAGES]:
            ptype = _classify_page_type(sub)
            logger.info(f"WebsiteCrawlerAgent (HTTP): [{ptype}] -> {sub}")
            pg, _ = _fetch(sub, ptype)
            if pg: pages_data.append(pg)

        ms = int((time.time()-start)*1000)
        return WebsiteCrawlerResult(
            website_url=root_url, company_name=company_name, pages=pages_data,
            crawl_status="success" if pages_data else "failed", crawler="http_fallback", crawl_time_ms=ms
        )

    async def process(self, url: str, company_name: Optional[str] = None) -> WebsiteCrawlerResult:
        """
        Crawl a company website from extracted lead data.
        Args:
            url          : Website URL from the lead record.
            company_name : Company name from the lead (for context).
        Returns:
            WebsiteCrawlerResult with structured JSON content for downstream agents.
        """
        if not url:
            return WebsiteCrawlerResult(website_url="", crawl_status="failed", error="No URL provided")
        root_url = self._normalize_url(url)
        cache_key = root_url.lower()
        if cache_key in self._cache:
            logger.info(f"WebsiteCrawlerAgent: cached result for {cache_key}")
            return self._cache[cache_key]
        logger.info(f"WebsiteCrawlerAgent: starting crawl -> {root_url} (company: {company_name})")
        try:
            result = await self._playwright_crawl(root_url, company_name)
            self._cache[cache_key] = result
            logger.info(f"WebsiteCrawlerAgent: {len(result.pages)} pages in {result.crawl_time_ms}ms [playwright]")
            return result
        except Exception as e:
            logger.warning(f"WebsiteCrawlerAgent: playwright failed ({e}), trying HTTP fallback...")
            try:
                result = await self._http_fallback(root_url, company_name)
                self._cache[cache_key] = result
                logger.info(f"WebsiteCrawlerAgent: {len(result.pages)} pages in {result.crawl_time_ms}ms [http_fallback]")
                return result
            except Exception as e2:
                logger.error(f"WebsiteCrawlerAgent: both crawlers failed for {root_url}: {e2}")
                return WebsiteCrawlerResult(website_url=root_url, company_name=company_name, crawl_status="failed", error=str(e2))

class WebsiteResearchAgent:
    """Extracts structured company info from crawled website content. Fully programmatic - no LLM."""
    TECH_KEYWORDS = ["react","angular","vue","python","node","aws","docker","kubernetes","salesforce","wordpress","shopify","azure","gcp","tensorflow","pytorch","django","fastapi","flutter","swift","java","dotnet",".net","ruby","php","laravel","spark","hadoop"]

    async def process(self, crawler_result: WebsiteCrawlerResult) -> WebsiteResearchData:
        if not crawler_result or not crawler_result.pages:
            return WebsiteResearchData()
        logger.info("WebsiteResearchAgent: extracting structured data from crawled content...")
        full_text = crawler_result.to_json().get("full_text","")
        found_tech = [kw.title() for kw in self.TECH_KEYWORDS if re.search(r"\b"+re.escape(kw)+r"\b", full_text, re.I)]
        social_links: Dict[str,str] = {}
        for plat in ["linkedin","twitter","facebook","github","youtube"]:
            m = re.search(r"https?://(?:www\.)?"+plat+r"\.com/[a-zA-Z0-9_\-/]+", full_text)
            if m: social_links[plat] = m.group(0)
        hp = next((p for p in crawler_result.pages if p.page_type=="homepage"), None)
        desc = hp.clean_text[:400].strip() if hp else None
        data = WebsiteResearchData(
            companyName=crawler_result.company_name, website=crawler_result.website_url,
            description=desc, techStack=found_tech or None, socialLinks=social_links or None
        )
        logger.info(f"WebsiteResearchAgent: done. Tech={found_tech}, Social={list(social_links.keys())}")
        return data

class CompanyEnrichmentAgent:
    """Merges lead data with website-crawled content into a normalized company profile using LLM."""
    def __init__(self):
        from core.llm_config import get_llm
        self.llm = get_llm()

    async def process(self, lead_data: Dict[str,Any], research_data: WebsiteResearchData) -> EnrichedCompanyProfile:
        logger.info("CompanyEnrichmentAgent: merging lead data with website research...")
        agent = Agent(role="Company Enrichment Agent",
            goal="Merge lead data with website research data into a normalized company profile.",
            backstory="You merge data from multiple sources. Prefer website research values. Never overwrite valid values with null. Return only valid JSON.",
            verbose=False, allow_delegation=False, llm=self.llm)
        task = Task(
            description=f"Merge the following into a normalized company profile.\nRules:\n- Prefer website research values when available.\n- Never overwrite valid values with null.\n- Remove duplicates.\n- Return ONLY valid JSON.\n\nLead Data:\n{json.dumps(lead_data, indent=2)}\n\nWebsite Research:\n{research_data.model_dump_json(indent=2)}",
            expected_output="Valid JSON representing the merged company profile.",
            agent=agent, output_pydantic=EnrichedCompanyProfile)
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(loop.run_in_executor(None, crew.kickoff), timeout=90.0)
            if result.pydantic:
                logger.info("CompanyEnrichmentAgent: merge complete.")
                return result.pydantic
            return EnrichedCompanyProfile()
        except asyncio.TimeoutError:
            logger.error("CompanyEnrichmentAgent: timed out.")
            return EnrichedCompanyProfile()
        except Exception as e:
            logger.error(f"CompanyEnrichmentAgent failed: {e}")
            return EnrichedCompanyProfile()

class ApifyDataCleaningAgent:
    """Cleans and normalizes the final enriched company profile for database storage."""
    def __init__(self):
        from core.llm_config import get_llm
        self.llm = get_llm()

    async def process(self, profile: EnrichedCompanyProfile) -> EnrichedCompanyProfile:
        logger.info("ApifyDataCleaningAgent: cleaning and normalizing...")
        agent = Agent(role="Data Cleaning Agent",
            goal="Clean, normalize, validate, and prepare the company record for database storage.",
            backstory="You clean and normalize records for database storage. Validate URLs, emails, phone numbers. Return valid JSON.",
            verbose=False, allow_delegation=False, llm=self.llm)
        task = Task(
            description=f"Clean and normalize the following company profile for database storage.\nRemove duplicates, fix formatting, validate URLs.\n\nProfile:\n{profile.model_dump_json(indent=2)}",
            expected_output="Valid JSON representing the final clean company profile.",
            agent=agent, output_pydantic=EnrichedCompanyProfile)
        crew = Crew(agents=[agent], tasks=[task], verbose=False)
        loop = asyncio.get_running_loop()
        try:
            result = await asyncio.wait_for(loop.run_in_executor(None, crew.kickoff), timeout=60.0)
            if result.pydantic:
                logger.info("ApifyDataCleaningAgent: done.")
                return result.pydantic
            return profile
        except asyncio.TimeoutError:
            logger.error("ApifyDataCleaningAgent: timed out.")
            return profile
        except Exception as e:
            logger.error(f"ApifyDataCleaningAgent failed: {e}")
            return profile

class ApifyWorkflowOrchestrator:
    """
    Orchestrates the Website Research Pipeline:
    Lead Data -> WebsiteCrawlerAgent -> WebsiteResearchAgent
             -> CompanyEnrichmentAgent -> ApifyDataCleaningAgent
             -> Enriched Company Profile (JSON)
    """
    def __init__(self):
        self.crawler_agent    = WebsiteCrawlerAgent()
        self.research_agent   = WebsiteResearchAgent()
        self.enrichment_agent = CompanyEnrichmentAgent()
        self.cleaning_agent   = ApifyDataCleaningAgent()

    async def execute_pipeline(self, lead_data: Dict[str,Any], scraped_text: str="", update_status_cb=None) -> Dict[str,Any]:
        try:
            website_url  = lead_data.get("website") or lead_data.get("website_url") or lead_data.get("url") or ""
            company_name = lead_data.get("companyName") or lead_data.get("company") or None

            if not website_url:
                logger.warning("ApifyWorkflowOrchestrator: no website URL in lead data - skipping crawl.")
                crawler_json   = {}
                research_data  = WebsiteResearchData()
            else:
                if update_status_cb: update_status_cb(f"Website Crawler Agent: crawling {website_url}...")
                logger.info(f"ApifyWorkflowOrchestrator: crawling {website_url} for {company_name}")
                crawler_result = await self.crawler_agent.process(website_url, company_name)
                crawler_json   = crawler_result.to_json()
                logger.info(f"ApifyWorkflowOrchestrator: crawler done - status={crawler_result.crawl_status}, pages={len(crawler_result.pages)}")
                if update_status_cb: update_status_cb("Website Research Agent: extracting structured data...")
                research_data = await self.research_agent.process(crawler_result)

            if update_status_cb: update_status_cb("Company Enrichment Agent: merging data...")
            enriched_profile = await self.enrichment_agent.process(lead_data, research_data)

            if update_status_cb: update_status_cb("Data Cleaning Agent: finalizing profile...")
            cleaned_profile = await self.cleaning_agent.process(enriched_profile)

            if update_status_cb: update_status_cb("Lead Scoring Agent: scoring company...")
            from agents.apollo_processing_agents import LeadScoringAgent
            scoring_agent = LeadScoringAgent()
            
            # --- IMPLEMENT LINKEDIN FALLBACK RULE ---
            cleaned_dict = cleaned_profile.model_dump(exclude_none=True)
            fallback_sources = {}
            
            def get_li_val(field):
                company_obj = lead_data.get("company") or {}
                if field == "companyName": return company_obj.get("name") or lead_data.get("companyName")
                if field == "industry":
                    industries = company_obj.get("industries", [])
                    return industries[0].get("name") if industries else lead_data.get("industry")
                if field == "companySize":
                    return lead_data.get("employeeCount") or lead_data.get("employeeCountRange") or company_obj.get("employeeCount")
                if field == "foundedYear": return company_obj.get("foundedOn", {}).get("year")
                if field == "companyLocation": return company_obj.get("location", {}).get("parsed", {}).get("text") or lead_data.get("location")
                if field == "aboutText": return company_obj.get("description")
                if field == "hiring": return lead_data.get("hiring") or lead_data.get("openToWork")
                if field == "specialities": return company_obj.get("specialities")
                if field == "decisionMaker":
                    positions = lead_data.get("currentPosition", [])
                    if isinstance(positions, list) and positions:
                        return positions[0].get("position")
                    return lead_data.get("title")
                return None

            for field in ["companyName", "industry", "companySize", "foundedYear", "companyLocation", "aboutText", "hiring", "specialities", "decisionMaker"]:
                primary_val = cleaned_dict.get(field)
                if primary_val in (None, "", []):
                    li_val = get_li_val(field)
                    if li_val not in (None, "", []):
                        cleaned_dict[field] = li_val
                        fallback_sources[f"{field}_source"] = "linkedin"
                    else:
                        fallback_sources[f"{field}_source"] = "none"
                else:
                    fallback_sources[f"{field}_source"] = "website"
                    
            # Combine lead metadata, cleaned profile (with fallbacks), and source tracking for scoring
            combined_data = {**lead_data, **cleaned_dict, **fallback_sources}
            
            # Run scoring (synchronous helper, execute in thread pool or run directly if fast)
            loop = asyncio.get_running_loop()
            scored_lead = await loop.run_in_executor(None, scoring_agent.score, combined_data)

            if update_status_cb: update_status_cb("Storage Agent: saving to database...")
            from tools.db_tools import DatabaseManager
            db_manager = DatabaseManager()
            try:
                await loop.run_in_executor(None, db_manager.save_leads, [scored_lead])
            finally:
                db_manager.close()

            if update_status_cb: update_status_cb("Completed!")
            return {
                "status": "success",
                "message": "Website research and scoring pipeline executed successfully.",
                "profile": cleaned_profile.model_dump(),
                "crawler_result": crawler_json,
                "scored_lead": {
                    "lead_score": scored_lead.lead_score,
                    "priority": scored_lead.priority,
                    "buying_probability": scored_lead.buying_probability,
                    "summary": scored_lead.ai_summary,
                    "strengths": scored_lead.strengths,
                    "weaknesses": scored_lead.weaknesses,
                    "recommended_services": scored_lead.recommended_services,
                    "next_action": scored_lead.next_action
                }
            }

        except Exception as e:
            logger.error(f"ApifyWorkflowOrchestrator failed: {e}")
            if update_status_cb: update_status_cb(f"Failed: {e}")
            return {"status":"error","message":str(e),"profile":{},"crawler_result":{}}

async def run_apify_pipeline(apify_data: Dict[str,Any], scraped_text: str="", update_status_cb=None) -> Dict[str,Any]:
    """
    Public entry point for the Website Research Pipeline.
    Args:
        apify_data       : Lead data dict (must include 'website' or 'website_url').
        scraped_text     : Optional legacy pre-scraped text (ignored if website URL present).
        update_status_cb : Optional callback for real-time status updates.
    """
    orchestrator = ApifyWorkflowOrchestrator()
    return await orchestrator.execute_pipeline(apify_data, scraped_text, update_status_cb)
