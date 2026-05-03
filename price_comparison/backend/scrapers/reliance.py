"""
Reliance Digital scraper — multi-strategy:
  1. Reliance Digital Solr/Hybris search API (JSON) — fastest
  2. curl_cffi HTML scrape
  3. Selenium (UC) as fallback
  4. Google search fallback — only if price found next to reliancedigital.in link

IMPORTANT: Never returns estimated prices. Returns None if no real price found.
"""
import re
import time
import json
import urllib.parse
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False

import requests as std_requests

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseScraper


class RelianceScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_selenium=True)

    # ------------------------------------------------------------------ #
    #  scrape_url — for when a Reliance Digital URL is pasted directly    #
    # ------------------------------------------------------------------ #
    def scrape_url(self, url: str):
        """Scrape a specific Reliance Digital product page."""
        print(f"Reliance: scrape_url -> {url}")

        # 1. Try curl_cffi FIRST (Fast)
        if CURL_AVAILABLE:
            try:
                print("Reliance: Trying curl_cffi...")
                resp = cffi_requests.get(url, impersonate="chrome124", timeout=15)
                if resp.status_code == 200:
                    result = self._parse_reliance_pdp(resp.text, url)
                    if result:
                        print(f"Reliance cffi: Rs. {result['price']}")
                        return result
            except Exception as e:
                print(f"Reliance scrape_url cffi failed: {e}")

        # 2. Try Selenium (Browser fallback)
        try:
            print("Reliance: Trying Selenium (browser)...")
            self.setup_driver()
            self.driver.get(url)
            time.sleep(5)
            html = self.driver.page_source
        except Exception as e:
            print(f"Reliance scrape_url Selenium failed: {e}")
            html = None
        finally:
            self.teardown_driver()

        if html:
            result = self._parse_reliance_pdp(html, url)
            if result:
                print(f"Reliance Selenium: Rs. {result['price']}")
                return result

        return None

    def _parse_reliance_pdp(self, html: str, url: str):
        """Parse Reliance Digital product detail page."""
        soup = BeautifulSoup(html, 'html.parser')
        page_text = soup.get_text()

        if 'access denied' in page_text.lower() or 'captcha' in page_text.lower():
            return None

        # Product name
        name = None
        for sel in ['h1', '.product__title', '.pdp__title', '[class*="productTitle"]']:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                name = el.get_text(strip=True)
                break

        # Price — look for ₹ in page text near known price selectors
        price = None
        price_selectors = [
            '.pdp__price',
            '.product-price',
            '[class*="sellingPrice"]',
            '[class*="price"]',
            '.priceSection',
        ]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el:
                match = re.search(r'₹\s*([\d,]+)', el.get_text())
                if match:
                    p = self.clean_price(match.group(1))
                    if p:
                        price = p
                        break

        # Wider scan
        if not price:
            matches = re.findall(r'₹\s*([\d,]+)', page_text)
            for m in matches:
                p = self.clean_price(m)
                if p and p > 100:
                    price = p
                    break

        if name and price:
            return {"name": name, "price": price, "url": url, "platform": "Reliance Digital"}
        return None

    # ------------------------------------------------------------------ #
    #  Strategy 1 : Official REST API                                     #
    # ------------------------------------------------------------------ #
    def _try_api(self, product_name):
        """Try Reliance Digital search API endpoints."""
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
        search_term = ' '.join(clean_name.split()[:6])
        encoded = urllib.parse.quote(search_term)

        # Current working endpoints (2024-2025)
        endpoints = [
            f"https://www.reliancedigital.in/rildigitalws/v2/rrldigital/cms/pagedata/search?searchQuery={encoded}&currentPage=0&pageSize=10&fields=FULL",
            f"https://www.reliancedigital.in/rildigitalws/v2/rrldigital/products/search?query={encoded}&currentPage=0&pageSize=10&fields=FULL",
            f"https://www.reliancedigital.in/search?q={encoded}&format=json",
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://www.reliancedigital.in/',
            'Origin': 'https://www.reliancedigital.in',
            'X-Requested-With': 'XMLHttpRequest',
        }

        for api_url in endpoints:
            try:
                print(f"Reliance API: {api_url[:90]}...")
                resp = std_requests.get(api_url, headers=headers, timeout=12)
                print(f"  Status: {resp.status_code}")
                if resp.status_code == 200:
                    ct = resp.headers.get('content-type', '')
                    if 'json' in ct:
                        try:
                            data = resp.json()
                            result = self._parse_api_response(data, product_name)
                            if result:
                                return result
                        except json.JSONDecodeError:
                            pass
            except Exception as e:
                print(f"  Endpoint failed: {str(e)[:60]}")

        return None

    def _parse_api_response(self, data, product_name):
        """Parse JSON from Reliance API — handles multiple response schemas."""
        if not isinstance(data, dict):
            return None

        # Find products list across known API response shapes
        products = None
        paths = [
            ['searchResults', 'products'],
            ['products'],
            ['results'],
            ['data', 'products'],
            ['response', 'products'],
            ['searchResult', 'products'],
            ['items'],
        ]
        for path in paths:
            d = data
            try:
                for key in path:
                    d = d[key]
                if isinstance(d, list) and len(d) > 0:
                    products = d
                    break
            except (KeyError, TypeError):
                continue

        if not products:
            return None

        print(f"  Reliance API: found {len(products)} products")

        # Try each product — pick first one that has a real price AND is relevant
        for first in products[:5]:
            name = (
                first.get('name', '') or
                first.get('title', '') or
                product_name
            )

            # Skip if result is clearly unrelated
            if not self.name_is_relevant(name, product_name):
                continue

            price_val = self._extract_price_from_product(first)
            price = self.clean_price(str(price_val)) if price_val else None

            if not price:
                continue

            # Build product URL
            product_url = (
                first.get('url', '') or
                first.get('productUrl', '') or
                first.get('pdpUrl', '') or
                ''
            )
            if product_url and not product_url.startswith('http'):
                product_url = 'https://www.reliancedigital.in' + product_url
            if not product_url:
                slug = first.get('slug', '') or str(first.get('id', ''))
                if slug:
                    product_url = f"https://www.reliancedigital.in/{slug}/p/{slug}"

            if price and product_url:
                print(f"  Reliance API result: {name[:60]} -> Rs. {price}")
                return {
                    "name": name,
                    "price": price,
                    "url": product_url,
                    "platform": "Reliance Digital"
                }

        return None

    def _extract_price_from_product(self, product: dict):
        """Extract price value from a product dict, handling multiple schemas."""
        # Direct selling price fields (most reliable)
        for field in ['sellingPrice', 'specialPrice', 'salePrice', 'discountPrice', 'offerPrice']:
            v = product.get(field)
            if v and isinstance(v, (int, float)) and v > 100:
                return v
            if v and isinstance(v, str):
                p = self.clean_price(v)
                if p:
                    return p

        # Nested price object
        price_info = product.get('price', {})
        if isinstance(price_info, dict):
            for key in ['value', 'sellingPrice', 'specialPrice', 'formattedValue']:
                v = price_info.get(key)
                if v:
                    if isinstance(v, (int, float)) and v > 100:
                        return v
                    if isinstance(v, str):
                        # Strip currency symbols
                        p = self.clean_price(re.sub(r'[^\d.]', '', v.replace(',', '')))
                        if p:
                            return p
        elif isinstance(price_info, (int, float)) and price_info > 100:
            return price_info

        # MRP as last numeric resort
        mrp = product.get('mrp')
        if mrp and isinstance(mrp, (int, float)) and mrp > 100:
            return mrp

        return None

    # ------------------------------------------------------------------ #
    #  Strategy 2 : curl_cffi                                             #
    # ------------------------------------------------------------------ #
    def _try_cffi(self, product_name):
        if not CURL_AVAILABLE:
            return None
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            search_term = ' '.join(clean_name.split()[:5])
            encoded = urllib.parse.quote(search_term)
            search_url = f"https://www.reliancedigital.in/search?q={encoded}"

            print(f"Reliance cffi: {search_url}")
            resp = cffi_requests.get(
                search_url,
                impersonate="chrome124",
                timeout=20,
                headers={
                    'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
                    'Referer': 'https://www.reliancedigital.in/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                }
            )
            print(f"  cffi status: {resp.status_code}")
            if resp.status_code == 200:
                return self._parse_reliance_html(resp.text, product_name)
        except Exception as e:
            print(f"Reliance cffi failed: {str(e)[:80]}")
        return None

    # ------------------------------------------------------------------ #
    #  Strategy 3 : Selenium                                              #
    # ------------------------------------------------------------------ #
    def _try_selenium(self, product_name):
        """Selenium with JS rendering for Reliance Digital (React SPA)."""
        try:
            self.setup_driver()
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            search_term = ' '.join(clean_name.split()[:5])
            encoded = urllib.parse.quote(search_term)
            search_url = f"https://www.reliancedigital.in/search?q={encoded}"

            print(f"Reliance Selenium: {search_url}")
            self.driver.get(search_url)

            # React SPA — wait for product cards
            selectors_to_wait = [
                '.sp__product',
                'li.gridItem',
                '[class*="product"]',
                '[class*="Product"]',
                '.plp-card',
                '[class*="ProductCard"]',
            ]
            for sel in selectors_to_wait:
                try:
                    WebDriverWait(self.driver, 12).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, sel))
                    )
                    break
                except Exception:
                    continue

            time.sleep(3)
            html = self.driver.page_source
            return self._parse_reliance_html(html, product_name)

        except Exception as e:
            print(f"Reliance Selenium failed: {str(e)[:120]}")
            return None
        finally:
            self.teardown_driver()

    # ------------------------------------------------------------------ #
    #  Strategy 4 : Google fallback                                       #
    # ------------------------------------------------------------------ #
    def _try_google(self, product_name):
        """Google search for Reliance Digital price."""
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            # Use Google Shopping tab for better price extraction
            query = f"{clean_name[:60]} price site:reliancedigital.in"
            encoded = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded}&num=10&hl=en&gl=in"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-IN,en-US;q=0.9',
            }
            resp = std_requests.get(url, headers=headers, timeout=12)
            if resp.status_code != 200:
                return None

            soup = BeautifulSoup(resp.text, 'html.parser')

            best_price = None
            best_url = None
            best_name = None

            for a in soup.find_all('a', href=True):
                href = a['href']
                if 'reliancedigital.in' not in href:
                    continue
                # Decode Google's redirect wrapper
                if href.startswith('/url?q='):
                    href = href.split('/url?q=')[1].split('&')[0]
                    href = urllib.parse.unquote(href)

                # Skip non-product URLs (category pages, homepage, etc.)
                if not re.search(r'/p/\d+|/p-[a-zA-Z0-9]+', href):
                    continue

                # Walk up tree to find price
                parent = a
                for _ in range(10):
                    if parent is None:
                        break
                    text = parent.get_text()
                    # Look for ₹ price
                    matches = re.findall(r'₹\s*([\d,]+)', text)
                    for m in matches:
                        p = self.clean_price(m)
                        if p and p > 100:
                            # Prefer smaller prices (selling price < MRP)
                            if best_price is None or p < best_price:
                                best_price = p
                                best_url = href
                                # Try to find product name
                                h_tag = parent.find(['h3', 'h2', 'h4'])
                                if h_tag:
                                    best_name = h_tag.get_text(strip=True)
                            break
                    if best_price:
                        break
                    parent = parent.parent

            if best_price and best_url:
                return {
                    "name": best_name or product_name,
                    "price": best_price,
                    "url": best_url,
                    "platform": "Reliance Digital"
                }

        except Exception as e:
            print(f"Reliance Google fallback failed: {str(e)[:80]}")
        return None

    # ------------------------------------------------------------------ #
    #  HTML Parser                                                        #
    # ------------------------------------------------------------------ #
    def _parse_reliance_html(self, html, product_name):
        """Parse Reliance Digital HTML to extract first relevant product."""
        soup = BeautifulSoup(html, 'html.parser')

        page_text = soup.get_text().lower()
        if 'access denied' in page_text or 'captcha' in page_text:
            print("Reliance: Access denied")
            return None

        # Product card selectors — ordered by reliability
        product_selectors = [
            'li.gridItem',
            '.sp__product',
            '[class*="productCard"]',
            '[class*="ProductCard"]',
            '.productItem',
            'div[class*="product-card"]',
            '[class*="plp-card"]',
        ]
        products = []
        for sel in product_selectors:
            products = soup.select(sel)
            if products:
                print(f"Reliance HTML: found {len(products)} products with '{sel}'")
                break

        # Fallback: anchor pattern
        if not products:
            patterns = [
                re.compile(r'/p-[a-zA-Z0-9]+'),
                re.compile(r'/[a-zA-Z0-9-]+/p/'),
            ]
            for pattern in patterns:
                links = soup.find_all('a', href=pattern)
                if links:
                    for link_tag in links[:5]:
                        href = link_tag.get('href', '')
                        if not href.startswith('http'):
                            href = 'https://www.reliancedigital.in' + href
                        parent = link_tag
                        for _ in range(10):
                            if parent is None:
                                break
                            match = re.search(r'₹\s*([\d,]+)', parent.get_text())
                            if match:
                                price = self.clean_price(match.group(1))
                                if price and price > 100:
                                    # Find name
                                    h = parent.find(['h3', 'h4', 'h2'])
                                    name = h.get_text(strip=True) if h else product_name
                                    if self.name_is_relevant(name, product_name):
                                        return {
                                            "name": name,
                                            "price": price,
                                            "url": href,
                                            "platform": "Reliance Digital"
                                        }
                            parent = parent.parent
            return None

        # Parse product cards — find first relevant one
        for product in products[:5]:
            link = None
            a_tag = product.find('a', href=True)
            if a_tag:
                link = a_tag['href']
                if link and not link.startswith('http'):
                    link = 'https://www.reliancedigital.in' + link

            # Extract name
            name = product_name
            for tag in ['h3', 'h4', 'h2', 'p']:
                el = product.find(tag)
                if el and el.get_text(strip=True):
                    name = el.get_text(strip=True)
                    break

            # Skip unrelated products
            if not self.name_is_relevant(name, product_name):
                continue

            # Extract price
            price = None
            # Scan all text nodes for ₹
            for txt in product.find_all(string=True):
                if '₹' in txt:
                    p = self.clean_price(txt)
                    if p and p > 100:
                        price = p
                        break

            # Try data attributes
            if price is None:
                for tag in product.find_all(True):
                    for attr in ['data-price', 'data-selling-price', 'data-mrp', 'data-special-price']:
                        val = tag.get(attr)
                        if val:
                            p = self.clean_price(str(val))
                            if p and p > 100:
                                price = p
                                break
                    if price:
                        break

            if link and price:
                return {"name": name, "price": price, "url": link, "platform": "Reliance Digital"}

        return None

    # ------------------------------------------------------------------ #
    #  Main entry point                                                   #
    # ------------------------------------------------------------------ #
    def search_product(self, product_name):
        print(f"Reliance: Searching for '{product_name[:70]}'")

        # 1. REST API (fastest)
        result = self._try_api(product_name)
        if result:
            print(f"Reliance API: Rs. {result['price']}")
            return result

        # 2. curl_cffi
        result = self._try_cffi(product_name)
        if result:
            print(f"Reliance cffi: Rs. {result['price']}")
            return result

        # 3. Selenium
        print("Reliance: Trying Selenium...")
        result = self._try_selenium(product_name)
        if result:
            print(f"Reliance Selenium: Rs. {result['price']}")
            return result

        # 4. Google fallback
        print("Reliance: Trying Google fallback...")
        result = self._try_google(product_name)
        if result:
            print(f"Reliance Google: Rs. {result['price']}")
            return result

        print("Reliance: All strategies exhausted — returning None (no fake price)")
        return None
