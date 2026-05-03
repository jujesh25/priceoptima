"""
Price Comparison Backend
- Accepts product URLs from ANY website (Amazon, Flipkart, Croma, Reliance Digital, or any other)
- Auto-detects source platform and routes accordingly
- Searches all other platforms concurrently
- NEVER generates estimated/fake prices — shows "Not Found" if unavailable
"""
import concurrent.futures
import urllib.parse
import traceback
import re
from urllib.parse import urlparse

try:
    from curl_cffi import requests as cffi_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False

import requests as std_requests
from bs4 import BeautifulSoup
from flask import Flask, request, jsonify
from flask_cors import CORS

from scrapers.amazon import AmazonScraper
from scrapers.flipkart import FlipkartScraper
from scrapers.croma import CromaScraper
from scrapers.reliance import RelianceScraper

app = Flask(__name__)
CORS(app)

PLATFORM_TIMEOUT = 40  # seconds per platform


# ── Platform detection ────────────────────────────────────────────────────────

PLATFORM_DOMAINS = {
    'amazon':   ['amazon.in', 'amazon.com'],
    'flipkart': ['flipkart.com'],
    'croma':    ['croma.com'],
    'reliance': ['reliancedigital.in'],
}

SCRAPER_MAP = {
    'amazon':   AmazonScraper,
    'flipkart': FlipkartScraper,
    'croma':    CromaScraper,
    'reliance': RelianceScraper,
}


def detect_platform(url: str) -> str | None:
    """Return platform key if URL belongs to a known platform, else None."""
    try:
        host = urlparse(url).netloc.lower().replace('www.', '')
        for platform, domains in PLATFORM_DOMAINS.items():
            for domain in domains:
                if host == domain or host.endswith('.' + domain):
                    return platform
    except Exception:
        pass
    return None


def extract_product_name_from_url(url: str) -> str | None:
    """
    Extract a usable product name from an arbitrary URL by fetching the page
    and reading the <title> / OG title / H1. Used for non-platform URLs.
    """
    try:
        headers = {
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/124.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'en-IN,en-US;q=0.9',
        }
        
        # Prefer curl_cffi for generic extraction to bypass simple bot checks
        if CURL_AVAILABLE:
            resp = cffi_requests.get(url, impersonate="chrome124", timeout=12)
        else:
            resp = std_requests.get(url, headers=headers, timeout=12, allow_redirects=True)

        if resp.status_code != 200:
            return None
        soup = BeautifulSoup(resp.text, 'html.parser')

        # Try Open Graph title first (most accurate for product pages)
        og = soup.find('meta', property='og:title')
        if og and og.get('content'):
            return og['content'].strip()

        # Twitter card title
        tw = soup.find('meta', attrs={'name': 'twitter:title'})
        if tw and tw.get('content'):
            return tw['content'].strip()

        # H1
        h1 = soup.find('h1')
        if h1 and h1.get_text(strip=True):
            return h1.get_text(strip=True)

        # Page title (strip site name after ' - ' or ' | ')
        title = soup.find('title')
        if title:
            t = title.get_text(strip=True)
            for sep in [' - ', ' | ', ' – ', ' — ']:
                if sep in t:
                    t = t.split(sep)[0].strip()
                    break
            if t:
                return t

    except Exception as e:
        print(f"[extract_name] Failed: {e}")
    return None


def scrape_platform(scraper_class, name=None, url=None):
    """Instantiate scraper and run search or URL scrape with error capture."""
    try:
        scraper = scraper_class()
        if url:
            return scraper.scrape_url(url)
        elif name:
            return scraper.search_product(name)
    except Exception as e:
        print(f"[{scraper_class.__name__}] Exception: {e}")
        traceback.print_exc()
    return None


# ── Main route ────────────────────────────────────────────────────────────────

@app.route('/compare', methods=['POST'])
def compare_prices():
    data = request.json
    url = data.get('url', '').strip()

    if not url:
        return jsonify({'error': 'URL is required'}), 400

    # Basic URL sanity
    if not url.startswith('http'):
        url = 'https://' + url

    source_platform = detect_platform(url)
    print(f"\n{'='*60}")
    print(f"URL: {url}")
    print(f"Detected platform: {source_platform or 'Unknown (generic URL)'}")
    print(f"{'='*60}\n")

    product_name = None
    source_result = None

    try:
        # ── Step 1: Extract product name from the source URL ─────────────
        if source_platform and source_platform in SCRAPER_MAP:
            # Use the platform's own scraper (has scrape_url support)
            source_result = scrape_platform(SCRAPER_MAP[source_platform], url=url)
            if source_result and source_result.get('name'):
                product_name = source_result['name']
            else:
                # scrape_url failed — try generic extraction
                product_name = extract_product_name_from_url(url)
        else:
            # Unknown platform — extract name from page metadata
            product_name = extract_product_name_from_url(url)

        if not product_name:
            return jsonify({
                'error': (
                    'Could not extract a product name from that URL. '
                    'Please make sure it is a valid product page and try again.'
                )
            }), 400

        print(f"Product name: {product_name[:100]}")

        # ── Step 2: Build initial response ──────────────────────────────
        response_data = {
            "product_name": product_name,
            "source_platform": source_platform,
            "source_url": url,
            "amazon":   None,
            "flipkart": None,
            "croma":    None,
            "reliance": None,
            "best_price": None,
        }

        # If we already have the source platform result, store it
        if source_result and source_result.get('price'):
            key = source_platform  # e.g. 'amazon'
            response_data[key] = source_result

        # ── Step 3: Search all OTHER platforms concurrently ─────────────
        all_scrapers = [
            {'class': AmazonScraper,   'key': 'amazon'},
            {'class': FlipkartScraper, 'key': 'flipkart'},
            {'class': CromaScraper,    'key': 'croma'},
            {'class': RelianceScraper, 'key': 'reliance'},
        ]
        # Skip the platform we already have data for
        scrapers_to_run = [
            s for s in all_scrapers
            if response_data.get(s['key']) is None
        ]

        if scrapers_to_run:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                future_map = {
                    executor.submit(scrape_platform, s['class'], name=product_name): s
                    for s in scrapers_to_run
                }
                for future in concurrent.futures.as_completed(
                    future_map, timeout=PLATFORM_TIMEOUT * 2
                ):
                    s = future_map[future]
                    try:
                        result = future.result(timeout=PLATFORM_TIMEOUT)
                        # Only store REAL results — no estimated prices
                        if result and result.get('price'):
                            response_data[s['key']] = result
                            print(f"  {s['key']} -> Rs. {result['price']}")
                        else:
                            print(f"  {s['key']} -> Not found")
                    except concurrent.futures.TimeoutError:
                        print(f"  {s['key']} -> Timed out")
                    except Exception as exc:
                        print(f"  {s['key']} -> Error: {exc}")

        # ── Step 4: Find best REAL price ────────────────────────────────
        valid_prices = []
        for key in ['amazon', 'flipkart', 'croma', 'reliance']:
            entry = response_data.get(key)
            if entry and entry.get('price') and not entry.get('estimated'):
                valid_prices.append({
                    "site":      entry['platform'],
                    "price":     entry['price'],
                    "url":       entry.get('url', ''),
                    "estimated": False,
                })

        if valid_prices:
            best = min(valid_prices, key=lambda x: x['price'])
            response_data['best_price'] = best
            print(f"\nBest price -> {best['site']} at Rs. {best['price']}")

        return jsonify(response_data)

    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok'})


if __name__ == '__main__':
    app.run(debug=True, port=8000, threaded=True)
