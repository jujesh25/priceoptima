"""
Croma scraper — multi-strategy approach:
  1. Croma Hybris JSON API (fastest, no bot issues)
  2. curl_cffi with Chrome TLS impersonation
  3. Selenium with UC fallback
  4. Google search result scrape as last resort

IMPORTANT: Never returns estimated prices. Returns None if no real price found.
Includes similarity check so wrong products are rejected.
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
    import requests as cffi_requests

import requests as std_requests
from .base import BaseScraper


class CromaScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_selenium=False)

    # ------------------------------------------------------------------ #
    #  scrape_url — for when a Croma URL is pasted directly               #
    # ------------------------------------------------------------------ #
    def scrape_url(self, url: str):
        """Scrape a specific Croma product page."""
        print(f"Croma: scrape_url -> {url}")

        # Try curl_cffi first (Croma uses Akamai WAF but cffi bypasses it)
        if CURL_AVAILABLE:
            try:
                resp = cffi_requests.get(
                    url, impersonate="chrome124", timeout=20,
                    headers={
                        'Accept-Language': 'en-IN,en-US;q=0.9',
                        'Referer': 'https://www.croma.com/',
                    }
                )
                if resp.status_code == 200:
                    result = self._parse_croma_pdp(resp.text, url)
                    if result:
                        return result
            except Exception as e:
                print(f"Croma scrape_url cffi failed: {e}")

        # Fallback: requests
        try:
            resp = std_requests.get(url, headers=self.get_headers(), timeout=12)
            if resp.status_code == 200:
                result = self._parse_croma_pdp(resp.text, url)
                if result:
                    return result
        except Exception as e:
            print(f"Croma scrape_url requests failed: {e}")

        return None

    def _parse_croma_pdp(self, html: str, url: str):
        """Parse a Croma product detail page."""
        soup = BeautifulSoup(html, 'html.parser')
        page_text = soup.get_text()

        if 'access denied' in page_text.lower() or 'robot' in page_text.lower():
            return None

        # Product name
        name = None
        for sel in ['h1', '.pdp-title', '.product-title', '[class*="productTitle"]', '[itemprop="name"]']:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                name = el.get_text(strip=True)
                break

        # Price
        price = None
        price_selectors = [
            '[class*="pdp-price"]',
            '.new-price',
            '[class*="selling-price"]',
            '[itemprop="price"]',
            '.product-price',
        ]
        for sel in price_selectors:
            el = soup.select_one(sel)
            if el:
                content = el.get('content') or el.get_text()
                p = self.clean_price(content)
                if p:
                    price = p
                    break

        # Scan page for ₹ if still no price
        if not price:
            matches = re.findall(r'₹\s*([\d,]+)', page_text)
            for m in matches:
                p = self.clean_price(m)
                if p and p > 100:
                    price = p
                    break

        if name and price:
            return {"name": name, "price": price, "url": url, "platform": "Croma"}
        return None

    # ------------------------------------------------------------------ #
    #  Strategy 1 : Croma internal Hybris search API (JSON)              #
    # ------------------------------------------------------------------ #
    def _try_api(self, product_name):
        """Croma's Hybris backend search API — returns JSON directly."""
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
        search_term = ' '.join(clean_name.split()[:6])
        encoded = urllib.parse.quote(search_term, safe='')

        api_endpoints = [
            # Primary Hybris API
            (
                f"https://api.croma.com/searchservices/v1/search?"
                f"query={encoded}%3Arelevance&currentPage=0&pageSize=10&fields=FULL"
            ),
            # Alternate endpoint
            (
                f"https://api.croma.com/searchservices/v2/search?"
                f"query={encoded}&currentPage=0&pageSize=10&fields=FULL"
            ),
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
            'Origin': 'https://www.croma.com',
            'Referer': 'https://www.croma.com/',
        }

        for api_url in api_endpoints:
            try:
                print(f"Croma API: {api_url[:90]}...")
                response = std_requests.get(api_url, headers=headers, timeout=12)
                print(f"  Status: {response.status_code}")
                if response.status_code == 200:
                    try:
                        data = response.json()
                        result = self._parse_croma_api_json(data, product_name)
                        if result:
                            return result
                    except json.JSONDecodeError:
                        pass
            except Exception as e:
                print(f"  Croma API endpoint failed: {str(e)[:60]}")

        return None

    def _parse_croma_api_json(self, data, product_name):
        """Parse JSON from Croma API — validates product relevance & price."""
        if not isinstance(data, dict):
            return None

        products = (
            data.get('products') or
            data.get('results') or
            data.get('data', {}).get('products') or
            []
        )

        if not isinstance(products, list) or not products:
            return None

        print(f"  Croma API: found {len(products)} products")

        for item in products[:5]:
            name = item.get('name', '') or item.get('title', '') or product_name

            # Reject unrelated products
            if not self.name_is_relevant(name, product_name):
                continue

            # Extract price
            price_info = item.get('price', {})
            price_val = None

            if isinstance(price_info, dict):
                # Priority order: value > specialPrice > formattedValue
                for key in ['value', 'specialPrice', 'sellingPrice', 'formattedValue']:
                    v = price_info.get(key)
                    if v is not None:
                        if isinstance(v, (int, float)) and v > 100:
                            price_val = v
                            break
                        elif isinstance(v, str):
                            p = self.clean_price(re.sub(r'[^\d.]', '', v.replace(',', '')))
                            if p:
                                price_val = p
                                break
            elif isinstance(price_info, (int, float)) and price_info > 100:
                price_val = price_info

            # Also check top-level fields
            if not price_val:
                for field in ['sellingPrice', 'specialPrice', 'mrp', 'salePrice']:
                    v = item.get(field)
                    if v:
                        p = self.clean_price(str(v))
                        if p:
                            price_val = p
                            break

            price = self.clean_price(str(price_val)) if price_val else None
            if not price:
                continue

            # Build URL
            slug = item.get('url', '') or item.get('slug', '') or ''
            product_url = (
                f"https://www.croma.com{slug}"
                if slug and not slug.startswith('http')
                else slug
            )

            if price and product_url:
                print(f"  Croma API result: {name[:60]} -> Rs. {price}")
                return {"name": name, "price": price, "url": product_url, "platform": "Croma"}

        return None

    # ------------------------------------------------------------------ #
    #  Strategy 2 : curl_cffi with TLS impersonation                     #
    # ------------------------------------------------------------------ #
    def _try_cffi(self, product_name):
        """Use curl_cffi to bypass Akamai WAF."""
        if not CURL_AVAILABLE:
            return None
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            search_term = ' '.join(clean_name.split()[:5])
            encoded = urllib.parse.quote(search_term, safe='')
            search_url = f"https://www.croma.com/searchB?q={encoded}%3Arelevance&text={encoded}"

            print(f"Croma cffi: {search_url}")
            response = cffi_requests.get(
                search_url,
                impersonate="chrome124",
                timeout=20,
                headers={
                    'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
                    'Referer': 'https://www.croma.com/',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                }
            )
            print(f"  cffi status: {response.status_code}")

            if response.status_code != 200:
                # Try alternate impersonation
                response = cffi_requests.get(
                    search_url, impersonate="chrome110", timeout=20,
                    headers={'Accept-Language': 'en-IN,en-US;q=0.9'}
                )

            if response.status_code == 200:
                return self._parse_croma_html(response.text, product_name)

        except Exception as e:
            print(f"Croma cffi failed: {str(e)[:80]}")
        return None

    # ------------------------------------------------------------------ #
    #  Strategy 3 : Selenium                                              #
    # ------------------------------------------------------------------ #
    def _try_selenium(self, product_name):
        """Selenium fallback for Croma."""
        try:
            self.setup_driver()
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            search_term = ' '.join(clean_name.split()[:5])
            encoded = urllib.parse.quote(search_term, safe='')
            search_url = f"https://www.croma.com/searchB?q={encoded}%3Arelevance&text={encoded}"

            print(f"Croma Selenium: {search_url}")
            self.driver.get(search_url)
            time.sleep(5)

            html = self.driver.page_source
            return self._parse_croma_html(html, product_name)

        except Exception as e:
            print(f"Croma Selenium failed: {str(e)[:120]}")
            return None
        finally:
            self.teardown_driver()

    # ------------------------------------------------------------------ #
    #  Strategy 4 : Google Shopping scrape                                #
    # ------------------------------------------------------------------ #
    def _try_google(self, product_name):
        """Scrape Google Shopping results for Croma price."""
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            query = f"{clean_name[:60]} price site:croma.com"
            encoded = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded}&num=10&hl=en&gl=in"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
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
                if 'croma.com' not in href:
                    continue
                # Decode Google's redirect
                if href.startswith('/url?q='):
                    href = href.split('/url?q=')[1].split('&')[0]
                    href = urllib.parse.unquote(href)

                # Only product pages (/p/NNNNN)
                if not re.search(r'/p/\d+', href):
                    continue

                # Find price near this element
                parent = a
                for _ in range(10):
                    if parent is None:
                        break
                    text = parent.get_text()
                    matches = re.findall(r'₹\s*([\d,]+)', text)
                    for m in matches:
                        p = self.clean_price(m)
                        if p and p > 100:
                            if best_price is None or p < best_price:
                                best_price = p
                                best_url = href
                                h = parent.find(['h3', 'h2', 'h4'])
                                if h:
                                    best_name = h.get_text(strip=True)
                            break
                    if best_price:
                        break
                    parent = parent.parent

            if best_price and best_url:
                print(f"  Croma Google: Rs. {best_price}")
                return {
                    "name": best_name or product_name,
                    "price": best_price,
                    "url": best_url,
                    "platform": "Croma"
                }

        except Exception as e:
            print(f"Croma Google fallback failed: {str(e)[:80]}")
        return None

    # ------------------------------------------------------------------ #
    #  HTML Parser                                                        #
    # ------------------------------------------------------------------ #
    def _parse_croma_html(self, html, product_name):
        """Parse Croma search results HTML to extract first relevant product."""
        soup = BeautifulSoup(html, 'html.parser')

        page_text = soup.get_text().lower()
        if 'access denied' in page_text or 'robot' in page_text or 'captcha' in page_text:
            print("Croma: Bot block detected")
            return None

        # Try multiple product selectors
        selectors = [
            'li.product-item',
            '.plp-card',
            '.cp-product',
            '.product-card',
            'li[data-product-id]',
            '[class*="product-item"]',
            '[class*="ProductCard"]',
        ]
        products = []
        for sel in selectors:
            products = soup.select(sel)
            if products:
                print(f"Croma HTML: found {len(products)} products with '{sel}'")
                break

        # Fallback: anchor links to /p/NNNNN
        if not products:
            product_links = soup.find_all('a', href=re.compile(r'/p/\d+'))
            for a in product_links[:8]:
                href = a.get('href', '')
                if not href.startswith('http'):
                    href = 'https://www.croma.com' + href

                parent = a
                for _ in range(10):
                    if parent is None:
                        break
                    match = re.search(r'₹\s*([\d,]+)', parent.get_text())
                    if match:
                        price = self.clean_price(match.group(1))
                        if price and price > 100:
                            name_tag = parent.find(['h3', 'h4', 'h2', 'p'])
                            name = name_tag.get_text(strip=True) if name_tag else product_name
                            if self.name_is_relevant(name, product_name):
                                return {"name": name, "price": price, "url": href, "platform": "Croma"}
                    parent = parent.parent
            return None

        # Parse product cards — find first relevant one
        for product in products[:6]:
            # Link
            link = None
            a_tag = product.find('a', href=True)
            if a_tag:
                link = a_tag['href']
                if link and not link.startswith('http'):
                    link = 'https://www.croma.com' + link

            # Name
            name = product_name
            for tag_name in ['h3', 'h4', 'h2', 'p']:
                tag = product.find(tag_name)
                if tag and tag.get_text(strip=True):
                    name = tag.get_text(strip=True)
                    break

            # Reject unrelated products
            if not self.name_is_relevant(name, product_name):
                continue

            # Price — scan all text nodes for ₹
            price = None
            for txt in product.find_all(string=True):
                if '₹' in txt:
                    p = self.clean_price(txt)
                    if p and p > 100:
                        price = p
                        break

            # Try data attributes
            if price is None:
                for tag in product.find_all(True):
                    for attr in ['data-price', 'data-selling-price', 'data-mrp']:
                        val = tag.get(attr)
                        if val:
                            p = self.clean_price(str(val))
                            if p and p > 100:
                                price = p
                                break
                    if price:
                        break

            if link and price:
                return {"name": name, "price": price, "url": link, "platform": "Croma"}

        return None

    # ------------------------------------------------------------------ #
    #  Main entry                                                          #
    # ------------------------------------------------------------------ #
    def search_product(self, product_name):
        print(f"Croma: Searching for '{product_name[:70]}'")

        # 1. Internal API (fastest)
        result = self._try_api(product_name)
        if result:
            print(f"Croma API: Rs. {result['price']}")
            return result

        # 2. curl_cffi (bypasses WAF)
        result = self._try_cffi(product_name)
        if result:
            print(f"Croma cffi: Rs. {result['price']}")
            return result

        # 3. Selenium
        print("Croma: Trying Selenium...")
        result = self._try_selenium(product_name)
        if result:
            print(f"Croma Selenium: Rs. {result['price']}")
            return result

        # 4. Google fallback
        print("Croma: Trying Google fallback...")
        result = self._try_google(product_name)
        if result:
            print(f"Croma Google: Rs. {result['price']}")
            return result

        print("Croma: All strategies exhausted — returning None (no fake price)")
        return None
