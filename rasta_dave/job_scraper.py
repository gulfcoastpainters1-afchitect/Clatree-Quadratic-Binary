"""
job_scraper.py — Rasta Dave Job Search Engine
==============================================
Scrapes local job listings from:
  - Craigslist  (live; publicly accessible)
  - Indeed      (live; publicly accessible supplement)
  - Nextdoor    (stub — requires authenticated session cookies)
  - Facebook    (stub — requires authenticated session cookies)

Writes results to:
  - job_listings/jobs_<timestamp>.csv   (open in Excel / Google Sheets)
  - job_listings/jobs_<timestamp>.json  (machine-readable)

Usage (standalone):
    python job_scraper.py
    python job_scraper.py --city miami --query "painter" --sources craigslist indeed

Usage (as module):
    from job_scraper import run_job_search
    result = run_job_search({"craigslist_city": "miami", "query": "painter"})
    print(result["output_files"])
"""

import argparse
import csv
import json
import logging
import os
import re
import time
from datetime import datetime

import requests

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("rasta_dave.job_scraper")

# Output directory (relative to this file)
OUTPUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "job_listings")

# Shared browser-like headers to reduce blocks
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.5",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


# ---------------------------------------------------------------------------
# Craigslist scraper
# ---------------------------------------------------------------------------

def scrape_craigslist_jobs(city="miami", query="", max_results=50):
    """
    Scrape job listings from Craigslist.

    Args:
        city:        Craigslist city subdomain (e.g. 'miami', 'losangeles', 'sfbay').
        query:       Search keywords (e.g. 'painter', 'construction').
        max_results: Cap on total listings returned.

    Returns:
        list of dicts with keys: title, url, location, price, posted_at, source.
    """
    results = []
    base_url = f"https://{city}.craigslist.org/search/jjj"
    params = {}
    if query:
        params["query"] = query
    start = 0

    while len(results) < max_results:
        if start > 0:
            params["start"] = start
        try:
            resp = requests.get(base_url, params=params, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Craigslist request failed: %s", exc)
            break

        listings = _parse_craigslist_html(resp.text, city)
        if not listings:
            logger.info("No more Craigslist listings at offset %d.", start)
            break

        results.extend(listings)
        if len(listings) < 25:          # Craigslist returns ~25 per page; fewer means last page
            break

        start += len(listings)
        time.sleep(1.5)                  # polite crawl delay

    return results[:max_results]


def _parse_craigslist_html(html_text, city):
    """
    Extract job listings from a Craigslist search-results page.

    Tries JSON-LD embedded data first; falls back to regex HTML parsing.
    """
    listings = []

    # --- attempt 1: JSON embedded in page (newer CL design) ---
    json_match = re.search(
        r'window\.__NEXT_DATA__\s*=\s*(\{.*?\});\s*</script>',
        html_text, re.DOTALL
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            items = (
                data.get("props", {})
                    .get("pageProps", {})
                    .get("initialData", {})
                    .get("data", {})
                    .get("items", [])
            )
            for item in items:
                title = item.get("title", "")
                path = item.get("url", "") or item.get("path", "")
                url = (
                    path if path.startswith("http")
                    else f"https://{city}.craigslist.org{path}"
                )
                area = item.get("area", {})
                location = area.get("name", "") if isinstance(area, dict) else item.get("location", "")
                listings.append({
                    "title": title,
                    "url": url,
                    "location": location,
                    "price": item.get("price", ""),
                    "posted_at": item.get("date", ""),
                    "source": "craigslist",
                })
        except (json.JSONDecodeError, KeyError):
            pass

    # --- attempt 2: href + title attribute pattern ---
    if not listings:
        pattern = re.compile(
            r'href="(/[a-z0-9/]+/[a-z]{3}/\d+\.html)"[^>]*title="([^"]*)"'
        )
        seen = set()
        for m in pattern.finditer(html_text):
            path, title = m.group(1), m.group(2).strip()
            if path not in seen and title:
                seen.add(path)
                listings.append({
                    "title": title,
                    "url": f"https://{city}.craigslist.org{path}",
                    "location": "",
                    "price": "",
                    "posted_at": "",
                    "source": "craigslist",
                })

    # --- attempt 3: span label inside posting-title anchor ---
    if not listings:
        anchor_pat = re.compile(
            r'<a[^>]+href="([^"]+\.html)"[^>]*>.*?'
            r'<span[^>]*class="[^"]*label[^"]*"[^>]*>([^<]+)</span>',
            re.DOTALL,
        )
        seen = set()
        for m in anchor_pat.finditer(html_text):
            url, title = m.group(1).strip(), m.group(2).strip()
            if url not in seen and title:
                seen.add(url)
                listings.append({
                    "title": title,
                    "url": url if url.startswith("http") else f"https://{city}.craigslist.org{url}",
                    "location": "",
                    "price": "",
                    "posted_at": "",
                    "source": "craigslist",
                })

    return listings


# ---------------------------------------------------------------------------
# Indeed scraper (good local-job supplement)
# ---------------------------------------------------------------------------

def scrape_indeed_jobs(query="", location="", max_results=50):
    """
    Scrape job listings from Indeed.

    Args:
        query:       Job title / keywords.
        location:    City + state string (e.g. 'Miami, FL').
        max_results: Cap on total listings returned.

    Returns:
        list of dicts with keys: title, company, url, location, price, posted_at, source.
    """
    results = []
    base_url = "https://www.indeed.com/jobs"
    params = {}
    if query:
        params["q"] = query
    if location:
        params["l"] = location
    start = 0

    while len(results) < max_results:
        if start > 0:
            params["start"] = start
        try:
            resp = requests.get(base_url, params=params, headers=_HEADERS, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as exc:
            logger.error("Indeed request failed: %s", exc)
            break

        listings = _parse_indeed_html(resp.text)
        if not listings:
            break

        results.extend(listings)
        if len(listings) < 10:
            break

        start += 10
        time.sleep(2)

    return results[:max_results]


def _parse_indeed_html(html_text):
    """Extract job listings from an Indeed search-results page."""
    listings = []

    # Indeed embeds job cards in a JS variable
    json_match = re.search(
        r'window\.mosaic\.providerData\["mosaic-provider-jobcards"\]\s*=\s*(\{.*?\});\s*window',
        html_text, re.DOTALL
    )
    if json_match:
        try:
            data = json.loads(json_match.group(1))
            results = (
                data.get("metaData", {})
                    .get("mosaicProviderJobCardsModel", {})
                    .get("results", [])
            )
            for r in results:
                title = r.get("displayTitle") or r.get("jobTitle", "")
                job_key = r.get("jobkey", "")
                salary_obj = r.get("extractedSalary", {})
                salary_str = ""
                if isinstance(salary_obj, dict) and salary_obj:
                    lo = salary_obj.get("min", "")
                    hi = salary_obj.get("max", "")
                    salary_str = f"${lo}-${hi}" if lo and hi else str(salary_obj)
                listings.append({
                    "title": title,
                    "company": r.get("company", ""),
                    "url": f"https://www.indeed.com/viewjob?jk={job_key}" if job_key else "",
                    "location": r.get("formattedLocation", "") or r.get("jobLocationCity", ""),
                    "price": salary_str,
                    "posted_at": r.get("formattedRelativeTime", ""),
                    "source": "indeed",
                })
        except (json.JSONDecodeError, KeyError, AttributeError):
            pass

    # Fallback: h2.jobTitle span text
    if not listings:
        for m in re.finditer(
            r'<h2[^>]*class="[^"]*jobTitle[^"]*"[^>]*>.*?<span[^>]*>([^<]+)</span>',
            html_text, re.DOTALL
        ):
            title = m.group(1).strip()
            if title and title.lower() != "new":
                listings.append({
                    "title": title,
                    "company": "",
                    "url": "",
                    "location": "",
                    "price": "",
                    "posted_at": "",
                    "source": "indeed",
                })

    return listings


# ---------------------------------------------------------------------------
# Nextdoor stub  (requires authenticated session)
# ---------------------------------------------------------------------------

def scrape_nextdoor_jobs(credentials=None):
    """
    Nextdoor job/services scraper stub.

    Nextdoor requires an authenticated session. To enable this scraper:
      1. Log into nextdoor.com in your browser.
      2. Export your session cookies to a JSON file (use a browser extension
         such as "EditThisCookie" or "Cookie-Editor").
      3. Pass credentials={'cookie_file': '/path/to/cookies.json'} to this function.

    Returns:
        list of job dicts (empty until authentication is configured).
    """
    logger.warning(
        "Nextdoor scraper requires authentication — "
        "configure credentials['cookie_file'] to enable."
    )
    # TODO: load cookies, GET https://nextdoor.com/find-services/, parse results
    return []


# ---------------------------------------------------------------------------
# Facebook stub  (requires authenticated session)
# ---------------------------------------------------------------------------

def scrape_facebook_jobs(credentials=None):
    """
    Facebook Marketplace / Jobs scraper stub.

    Facebook blocks unauthenticated automated access. Options:
      1. Official Facebook Jobs Graph API (requires Meta app approval).
      2. Browser automation (Selenium / Playwright) with a real logged-in session.
      3. Pass credentials={'cookie_file': '/path/to/fb_cookies.json'} here once
         you have exported your browser cookies.

    Returns:
        list of job dicts (empty until authentication is configured).
    """
    logger.warning(
        "Facebook scraper requires authentication — "
        "configure credentials['cookie_file'] or use browser automation to enable."
    )
    # TODO: implement with requests + cookie jar, or Selenium session
    return []


# ---------------------------------------------------------------------------
# Output writers
# ---------------------------------------------------------------------------

def save_to_csv(listings, filename=None):
    """
    Write job listings to a CSV file (opens cleanly in Excel / Google Sheets).

    Returns the path to the written file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(OUTPUT_DIR, f"jobs_{ts}.csv")

    if not listings:
        logger.info("No listings to save — CSV not written.")
        return filename

    fieldnames = ["title", "company", "location", "price", "posted_at", "url", "source", "scraped_at"]
    scraped_at = datetime.now().isoformat()

    with open(filename, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for listing in listings:
            listing.setdefault("company", "")
            listing.setdefault("location", "")
            listing.setdefault("price", "")
            listing.setdefault("posted_at", "")
            listing["scraped_at"] = scraped_at
            writer.writerow(listing)

    logger.info("Saved %d listings → %s", len(listings), filename)
    return filename


def save_to_json(listings, filename=None):
    """
    Write job listings to a JSON file.

    Returns the path to the written file.
    """
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    if filename is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(OUTPUT_DIR, f"jobs_{ts}.json")

    output = {
        "scraped_at": datetime.now().isoformat(),
        "count": len(listings),
        "listings": listings,
    }
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info("Saved %d listings → %s", len(listings), filename)
    return filename


# ---------------------------------------------------------------------------
# Main orchestrator
# ---------------------------------------------------------------------------

def run_job_search(config):
    """
    Run a full job search across all configured sources and save the results.

    Args:
        config (dict): Search configuration with keys:
            craigslist_city         (str)  — Craigslist city subdomain (default: 'miami')
            query                   (str)  — Job keywords (default: '')
            location                (str)  — Human-readable location for Indeed (default: '')
            sources                 (list) — Sources to query; any of:
                                             'craigslist', 'indeed', 'nextdoor', 'facebook'
                                             (default: ['craigslist', 'indeed'])
            max_results_per_source  (int)  — Per-source result cap (default: 50)

    Returns:
        dict: {
            'listings': [...],        # combined list of all job dicts
            'output_files': [...]     # paths to CSV + JSON files written
        }
    """
    city = config.get("craigslist_city", "miami")
    query = config.get("query", "")
    location = config.get("location", "")
    sources = config.get("sources", ["craigslist", "indeed"])
    max_results = config.get("max_results_per_source", 50)

    all_listings = []

    if "craigslist" in sources:
        logger.info("==> Craigslist [%s] — query: %r", city, query or "(all jobs)")
        cl = scrape_craigslist_jobs(city=city, query=query, max_results=max_results)
        logger.info("    Craigslist: %d listings found.", len(cl))
        all_listings.extend(cl)
        time.sleep(2)

    if "indeed" in sources:
        loc = location or city
        logger.info("==> Indeed — query: %r  location: %r", query or "(all)", loc)
        ind = scrape_indeed_jobs(query=query, location=loc, max_results=max_results)
        logger.info("    Indeed: %d listings found.", len(ind))
        all_listings.extend(ind)
        time.sleep(2)

    if "nextdoor" in sources:
        nd = scrape_nextdoor_jobs()
        all_listings.extend(nd)

    if "facebook" in sources:
        fb = scrape_facebook_jobs()
        all_listings.extend(fb)

    output_files = []
    if all_listings:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        csv_path = os.path.join(OUTPUT_DIR, f"jobs_{ts}.csv")
        json_path = os.path.join(OUTPUT_DIR, f"jobs_{ts}.json")
        save_to_csv(all_listings, csv_path)
        save_to_json(all_listings, json_path)
        output_files.extend([csv_path, json_path])
    else:
        logger.warning("No job listings found across all sources.")

    return {"listings": all_listings, "output_files": output_files}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_arg_parser():
    p = argparse.ArgumentParser(
        description="Rasta Dave Job Search Engine — scrapes Craigslist + Indeed."
    )
    p.add_argument("--city", default="miami",
                   help="Craigslist city subdomain (default: miami)")
    p.add_argument("--query", default="",
                   help="Job search keywords (e.g. 'painter construction')")
    p.add_argument("--location", default="",
                   help="Location string for Indeed (e.g. 'Miami, FL')")
    p.add_argument("--sources", nargs="+",
                   default=["craigslist", "indeed"],
                   choices=["craigslist", "indeed", "nextdoor", "facebook"],
                   help="Sources to scrape (default: craigslist indeed)")
    p.add_argument("--max-results", type=int, default=50,
                   help="Max results per source (default: 50)")
    return p


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    config = {
        "craigslist_city": args.city,
        "query": args.query,
        "location": args.location,
        "sources": args.sources,
        "max_results_per_source": args.max_results,
    }
    result = run_job_search(config)
    print("\n=== Job Search Complete ===")
    print(f"Total listings: {len(result['listings'])}")
    for path in result["output_files"]:
        print(f"  Output file: {path}")
