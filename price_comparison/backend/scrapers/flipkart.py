"""
Flipkart scraper — multi-strategy:
  1. Flipkart internal search API (JSON)
  2. HTML scrape (curl_cffi or requests)
  3. Selenium with updated CSS selectors
  4. Google search fallback

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


class FlipkartScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_selenium=True)

    # ------------------------------------------------------------------ #
    #  scrape_url — for when a Flipkart URL is pasted directly            #
    # ------------------------------------------------------------------ #
    def scrape_url(self, url: str):
        """Scrape a specific Flipkart product page."""
        print(f"Flipkart: scrape_url -> {url}")

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-IN,en-US;q=0.9',
        }

        # Try curl_cffi first
        if CURL_AVAILABLE:
            try:
                resp = cffi_requests.get(url, impersonate="chrome124", headers=headers, timeout=15)
                if resp.status_code == 200:
                    result = self._parse_flipkart_pdp(resp.text, url)
                    if result:
                        return result
            except Exception as e:
                print(f"Flipkart scrape_url cffi failed: {e}")

        # Fallback: requests
        try:
            resp = std_requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                result = self._parse_flipkart_pdp(resp.text, url)
                if result:
                    return result
        except Exception as e:
            print(f"Flipkart scrape_url requests failed: {e}")

        # Selenium fallback
        try:
            self.setup_driver()
            self.driver.get(url)
            time.sleep(4)
            result = self._parse_flipkart_pdp(self.driver.page_source, url)
            if result:
                return result
        except Exception as e:
            print(f"Flipkart scrape_url Selenium failed: {e}")
        finally:
            self.teardown_driver()

        return None

    def _parse_flipkart_pdp(self, html: str, url: str):
        """Parse a Flipkart product detail page."""
        soup = BeautifulSoup(html, 'html.parser')
        page_text = soup.get_text()

        # Product name
        name = None
        for sel in ['h1.yhB1nd', 'h1._6EBuvT', 'h1', '[class*="title"]', 'span.B_NuCI']:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                name = el.get_text(strip=True)
                break

        # Price selectors for PDP
        price = None
        for sel in ['div.Nx9bqj', 'div._30jeq3', '._16Jk6d', '[class*="price"]']:
            el = soup.select_one(sel)
            if el:
                p = self.clean_price(el.get_text())
                if p:
                    price = p
                    break

        # Scan page for ₹
        if not price:
            matches = re.findall(r'₹\s*([\d,]+)', page_text)
            for m in matches:
                p = self.clean_price(m)
                if p and p > 100:
                    price = p
                    break

        if name and price:
            return {"name": name, "price": price, "url": url, "platform": "Flipkart"}
        return None

    # ------------------------------------------------------------------ #
    #  Strategy 1 : Flipkart internal API                                 #
    # ------------------------------------------------------------------ #
    def _try_api(self, product_name):
        """Try Flipkart's internal search API endpoints."""
        clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
        search_term = ' '.join(clean_name.split()[:6])
        encoded = urllib.parse.quote(search_term)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
            'Referer': 'https://www.flipkart.com/',
            'X-User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 FKUA/website/41/website/Desktop',
        }

        endpoints = [
            f"https://www.flipkart.com/api/4/page/fetch?url=%2Fsearch%3Fq%3D{encoded}%26otracker%3Dsearch%26marketplace%3DFLIPKART&type=SEARCH&id=%2Fsearch%3Fq%3D{encoded}",
        ]

        for api_url in endpoints:
            try:
                print(f"Flipkart API: {api_url[:90]}...")
                resp = std_requests.get(api_url, headers=headers, timeout=15)
                print(f"  Status: {resp.status_code}")
                if resp.status_code == 200:
                    data = resp.json()
                    result = self._parse_flipkart_api(data, product_name)
                    if result:
                        print(f"  Flipkart API success: Rs. {result['price']}")
                        return result
            except Exception as e:
                print(f"  Flipkart API failed: {str(e)[:60]}")

        return None

    def _parse_flipkart_api(self, data, product_name):
        """Recursively search the Flipkart page API JSON for a product with price."""
        if not isinstance(data, dict):
            return None

        results = []
        self._find_products_in_json(data, results)

        if results:
            # Filter relevant results
            relevant = [r for r in results if self.name_is_relevant(r.get('name', ''), product_name)]
            pool = relevant if relevant else results

            # Pick the lowest price among top results
            pool.sort(key=lambda x: x.get('price', float('inf')))
            first = pool[0]

            if first.get('price') and first.get('url'):
                return {
                    "name": first.get('name', product_name),
                    "price": first['price'],
                    "url": first['url'],
                    "platform": "Flipkart"
                }
        return None

    def _find_products_in_json(self, obj, results, depth=0):
        """Recursively find product name+price+url triplets in nested JSON."""
        if depth > 15:
            return
        if isinstance(obj, dict):
            price = None
            name = None
            url = None

            for pk in ['finalPrice', 'price', 'sellingPrice', 'value']:
                v = obj.get(pk)
                if isinstance(v, dict):
                    for vk in ['value', 'amount', 'mrp']:
                        pv = v.get(vk)
                        if isinstance(pv, (int, float)) and pv > 100:
                            price = pv
                            break
                elif isinstance(v, (int, float)) and v > 100:
                    price = v
                if price:
                    break

            for nk in ['title', 'name', 'productName']:
                v = obj.get(nk)
                if isinstance(v, str) and len(v) > 5:
                    name = v
                    break

            for uk in ['url', 'productUrl', 'webUrl']:
                v = obj.get(uk)
                if isinstance(v, str) and ('flipkart' in v or v.startswith('/')):
                    if not v.startswith('http'):
                        v = 'https://www.flipkart.com' + v
                    url = v
                    break

            if price and url:
                results.append({'name': name or '', 'price': price, 'url': url})

            for v in obj.values():
                self._find_products_in_json(v, results, depth + 1)

        elif isinstance(obj, list):
            for item in obj[:20]:
                self._find_products_in_json(item, results, depth + 1)

    # ------------------------------------------------------------------ #
    #  Strategy 2 : HTML scrape (curl_cffi or requests)                  #
    # ------------------------------------------------------------------ #
    def _try_html(self, product_name):
        """Scrape Flipkart search results page using curl_cffi or requests."""
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            search_term = ' '.join(clean_name.split()[:5])
            encoded = urllib.parse.quote(search_term)
            url = f"https://www.flipkart.com/search?q={encoded}&marketplace=FLIPKART"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
                'Referer': 'https://www.flipkart.com/',
            }

            print(f"Flipkart HTML: {url}")
            if CURL_AVAILABLE:
                resp = cffi_requests.get(url, impersonate="chrome124", headers=headers, timeout=20)
            else:
                resp = std_requests.get(url, headers=headers, timeout=15)

            print(f"  Status: {resp.status_code}")
            if resp.status_code == 200:
                return self._parse_flipkart_html(resp.text, product_name)

        except Exception as e:
            print(f"Flipkart HTML scrape failed: {str(e)[:80]}")
        return None

    # ------------------------------------------------------------------ #
    #  Strategy 3 : Selenium                                              #
    # ------------------------------------------------------------------ #
    def _try_selenium(self, product_name):
        """Selenium fallback for Flipkart."""
        try:
            self.setup_driver()
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            search_term = ' '.join(clean_name.split()[:4])
            encoded = urllib.parse.quote(search_term)
            search_url = f"https://www.flipkart.com/search?q={encoded}"

            print(f"Flipkart Selenium: {search_url}")
            self.driver.get(search_url)
            time.sleep(4)

            # Dismiss login popup if present
            for popup_sel in ["button._2KpZ6l._2doB4z", "button[class*='_2KpZ6l']"]:
                try:
                    close_btn = self.driver.find_element(By.CSS_SELECTOR, popup_sel)
                    close_btn.click()
                    time.sleep(1)
                    break
                except Exception:
                    pass

            html = self.driver.page_source
            return self._parse_flipkart_html(html, product_name)

        except Exception as e:
            print(f"Flipkart Selenium failed: {str(e)[:120]}")
            return None
        finally:
            self.teardown_driver()

    # ------------------------------------------------------------------ #
    #  Strategy 4 : Google fallback                                       #
    # ------------------------------------------------------------------ #
    def _try_google(self, product_name):
        """Google search for Flipkart price."""
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            query = f"{clean_name[:60]} price site:flipkart.com"
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
                if 'flipkart.com' not in href:
                    continue
                if href.startswith('/url?q='):
                    href = href.split('/url?q=')[1].split('&')[0]
                    href = urllib.parse.unquote(href)

                # Only product pages
                if not re.search(r'/p/', href):
                    continue

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
                                h = parent.find(['h3', 'h2'])
                                if h:
                                    best_name = h.get_text(strip=True)
                            break
                    if best_price:
                        break
                    parent = parent.parent

            if best_price and best_url:
                print(f"  Flipkart Google: Rs. {best_price}")
                return {
                    "name": best_name or product_name,
                    "price": best_price,
                    "url": best_url,
                    "platform": "Flipkart"
                }
        except Exception as e:
            print(f"Flipkart Google fallback failed: {str(e)[:80]}")
        return None

    # ------------------------------------------------------------------ #
    #  HTML parser                                                        #
    # ------------------------------------------------------------------ #
    def _parse_flipkart_html(self, html, product_name):
        """Parse Flipkart HTML search results."""
        soup = BeautifulSoup(html, 'html.parser')

        # Selectors for Flipkart product cards (frequently updated)
        product_selectors = [
            'div[data-id]',
            'div._1AtVbE',
            'div._13oc-S',
            'div.tUxRFH',
            'div._2kHMtA',
            'div.slAVV4',
            'div[class*="product"]',
        ]

        products = []
        for sel in product_selectors:
            products = soup.select(sel)
            if products and len(products) > 1:
                break

        for product in products[:10]:
            try:
                # Must have a product page link
                a_tag = product.find('a', href=re.compile(r'/p/'))
                if not a_tag:
                    a_tag = product.find('a', href=True)
                if not a_tag:
                    continue

                link = a_tag.get('href', '')
                if link and not link.startswith('http'):
                    link = 'https://www.flipkart.com' + link

                # Name
                name = product_name
                for name_sel in ['._4rR01T', '.IRpwTa', '.s1Q9rs', 'a[title]']:
                    try:
                        ne = product.select_one(name_sel)
                        if ne:
                            n = ne.get('title', '') or ne.get_text(strip=True)
                            if n and len(n) > 5:
                                name = n
                                break
                    except Exception:
                        continue

                # Skip unrelated results
                if not self.name_is_relevant(name, product_name):
                    continue

                # Price — text scan for ₹
                price = None
                for txt in product.find_all(string=True):
                    if '₹' in txt:
                        p = self.clean_price(txt)
                        if p and p > 100:
                            price = p
                            break

                # Class-based selectors
                if price is None:
                    for price_sel in ['._30jeq3', '.Nx9bqj', '._1_WHN1', '[class*="price"]']:
                        try:
                            pe = product.select_one(price_sel)
                            if pe:
                                p = self.clean_price(pe.get_text())
                                if p and p > 100:
                                    price = p
                                    break
                        except Exception:
                            continue

                if link and price:
                    return {"name": name, "price": price, "url": link, "platform": "Flipkart"}

            except Exception:
                continue

        # Last resort: scan entire page for /p/ links near ₹
        links = soup.find_all('a', href=re.compile(r'/p/'))
        for a in links[:10]:
            href = a.get('href', '')
            if not href.startswith('http'):
                href = 'https://www.flipkart.com' + href
            parent = a
            for _ in range(8):
                if parent is None:
                    break
                match = re.search(r'₹\s*([\d,]+)', parent.get_text())
                if match:
                    price = self.clean_price(match.group(1))
                    if price and price > 100:
                        return {"name": product_name, "price": price, "url": href, "platform": "Flipkart"}
                parent = parent.parent

        return None

    # ------------------------------------------------------------------ #
    #  Main entry point                                                   #
    # ------------------------------------------------------------------ #
    def search_product(self, product_name):
        print(f"Flipkart: Searching for '{product_name[:70]}'")

        # 1. Internal API
        result = self._try_api(product_name)
        if result:
            print(f"Flipkart API: Rs. {result['price']}")
            return result

        # 2. HTML scrape
        result = self._try_html(product_name)
        if result:
            print(f"Flipkart HTML: Rs. {result['price']}")
            return result

        # 3. Selenium
        print("Flipkart: Trying Selenium...")
        result = self._try_selenium(product_name)
        if result:
            print(f"Flipkart Selenium: Rs. {result['price']}")
            return result

        # 4. Google fallback
        print("Flipkart: Trying Google fallback...")
        result = self._try_google(product_name)
        if result:
            print(f"Flipkart Google: Rs. {result['price']}")
            return result

        print("Flipkart: All strategies exhausted — returning None (no fake price)")
        return None
