"""
Amazon scraper — multi-strategy:
  1. Selenium / undetected_chromedriver (best bypass)
  2. curl_cffi with Chrome TLS impersonation
  3. Google search fallback (ultimate bypass)

scrape_url(): Scrapes a specific Amazon product page.
search_product(): Searches Amazon for a product by name.
"""
import time
import re
import urllib.parse
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    CURL_AVAILABLE = True
except ImportError:
    CURL_AVAILABLE = False
    import requests as cffi_requests

import requests as std_requests
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from .base import BaseScraper


class AmazonScraper(BaseScraper):
    def __init__(self):
        super().__init__(use_selenium=True)

    # ------------------------------------------------------------------ #
    #  scrape_url — scrape a specific Amazon product page                 #
    # ------------------------------------------------------------------ #
    def scrape_url(self, url: str):
        """Scrape a specific Amazon product URL."""
        print(f"Amazon: scrape_url -> {url}")

        # 1. Try curl_cffi FIRST (Fastest if not blocked)
        if CURL_AVAILABLE:
            try:
                print("Amazon: Trying curl_cffi...")
                resp = cffi_requests.get(
                    url, impersonate="chrome124", timeout=15,
                    headers=self.get_headers()
                )
                if resp.status_code == 200 and "Robot Check" not in resp.text:
                    soup = BeautifulSoup(resp.text, 'html.parser')
                    title_tag = soup.select_one('#productTitle')
                    if title_tag:
                        title = title_tag.get_text(strip=True)
                        price = self._extract_price_from_soup(soup)
                        if title and price:
                            print(f"Amazon cffi: Rs. {price}")
                            return {"name": title, "price": price, "url": url, "platform": "Amazon"}
            except Exception as e:
                print(f"Amazon cffi failed: {e}")

        # 2. Try Selenium (Slower, but best for bot detection)
        try:
            print("Amazon: Trying Selenium (browser)...")
            self.setup_driver()
            self.driver.get(url)
            time.sleep(4)

            if "Robot Check" in self.driver.title or "enter the characters" in self.driver.page_source.lower():
                print("Amazon Selenium: Blocked by Robot Check")
            else:
                title = None
                for selector in ["#productTitle", "#title span", "h1.a-size-large"]:
                    try:
                        elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                        title = elem.text.strip()
                        if title:
                            break
                    except Exception:
                        continue

                if title:
                    price = self._extract_price_from_driver()
                    if price:
                        print(f"Amazon Selenium: Rs. {price}")
                        return {"name": title, "price": price, "url": url, "platform": "Amazon"}
        except Exception as e:
            print(f"Amazon Selenium Error: {e}")
        finally:
            self.teardown_driver()

        # 3. Google fallback
        print("Amazon: Trying Google fallback...")
        return self._try_google_for_amazon(url)

    def _extract_price_from_driver(self):
        """Extract price from Selenium driver using multiple selectors."""
        price_selectors = [
            "span.priceToPay span.a-price-whole",
            ".apexPriceToPay span.a-price-whole",
            "#corePrice_feature_div span.a-price-whole",
            "#priceblock_ourprice",
            "#priceblock_dealprice",
            "span.a-price-whole",
            ".a-price .a-offscreen",
        ]
        for selector in price_selectors:
            try:
                elem = self.driver.find_element(By.CSS_SELECTOR, selector)
                text = elem.get_attribute("textContent") or elem.text
                p = self.clean_price(text)
                if p and p > 100:
                    return p
            except Exception:
                continue
        return None

    def _extract_price_from_soup(self, soup: BeautifulSoup):
        """Extract price from BeautifulSoup object of Amazon page."""
        selectors = [
            'span.priceToPay span.a-price-whole',
            '.apexPriceToPay span.a-price-whole',
            '#corePrice_feature_div span.a-price-whole',
            'span.a-price-whole',
            '.a-price .a-offscreen',
        ]
        for sel in selectors:
            el = soup.select_one(sel)
            if el:
                p = self.clean_price(el.get_text())
                if p and p > 100:
                    return p
        # Scan for ₹
        text = soup.get_text()
        matches = re.findall(r'₹\s*([\d,]+)', text)
        for m in matches:
            p = self.clean_price(m)
            if p and p > 100:
                return p
        return None

    def _try_google_for_amazon(self, amazon_url: str):
        """Scrape Google for the Amazon product price when direct scraping fails."""
        try:
            # Extract ASIN from URL for a better query
            asin_match = re.search(r'/dp/([A-Z0-9]{10})', amazon_url)
            if asin_match:
                query = f"amazon.in product {asin_match.group(1)} price ₹"
            else:
                query = f"price {amazon_url}"
            encoded = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded}&hl=en&gl=in"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-IN,en-US;q=0.9',
            }
            resp = std_requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')
                text = soup.get_text()

                # Extract title from Google snippet
                title = None
                for a in soup.find_all('a', href=True):
                    if 'amazon.in' in a.get('href', ''):
                        parent = a
                        for _ in range(6):
                            if parent is None:
                                break
                            h = parent.find(['h3', 'h2'])
                            if h and h.get_text(strip=True):
                                title = h.get_text(strip=True)
                                break
                            parent = parent.parent
                        if title:
                            break

                prices = re.findall(r'₹\s*([\d,]+)', text)
                for p_str in prices:
                    p = self.clean_price(p_str)
                    if p and p > 100:
                        return {
                            "name": title or "Amazon Product",
                            "price": p,
                            "url": amazon_url,
                            "platform": "Amazon"
                        }
        except Exception as e:
            print(f"Amazon Google fallback failed: {e}")
        return None

    # ------------------------------------------------------------------ #
    #  search_product — search Amazon by product name                     #
    # ------------------------------------------------------------------ #
    def search_product(self, product_name):
        """Search Amazon for a product by name — uses search results page."""
        print(f"Amazon: Searching for '{product_name[:70]}'")

        # Strategy 1: Selenium on search results
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            encoded = urllib.parse.quote(clean_name)
            search_url = f"https://www.amazon.in/s?k={encoded}"

            self.setup_driver()
            self.driver.get(search_url)
            time.sleep(3)

            results = self.driver.find_elements(By.CSS_SELECTOR, "[data-component-type='s-search-result']")
            for res in results[:5]:
                # Skip sponsored
                if res.find_elements(By.CSS_SELECTOR, ".s-sponsored-label-text"):
                    continue
                try:
                    name_el = res.find_element(By.CSS_SELECTOR, "h2 span")
                    name = name_el.text.strip()
                    if not name or not self.name_is_relevant(name, product_name):
                        continue

                    link_el = res.find_element(By.CSS_SELECTOR, "h2 a")
                    link = link_el.get_attribute("href")

                    price_el = res.find_element(By.CSS_SELECTOR, ".a-price-whole")
                    price = self.clean_price(price_el.text.strip())

                    if link and price:
                        print(f"Amazon Selenium search: Rs. {price}")
                        return {"name": name, "price": price, "url": link, "platform": "Amazon"}
                except Exception:
                    continue
        except Exception as e:
            print(f"Amazon Search Selenium Error: {e}")
        finally:
            self.teardown_driver()

        # Strategy 2: Google -> Amazon
        print("Amazon: Trying Google search fallback...")
        try:
            clean_name = re.sub(r'[^a-zA-Z0-9\s]', ' ', product_name).strip()
            query = f"{clean_name[:70]} site:amazon.in price"
            encoded = urllib.parse.quote(query)
            url = f"https://www.google.com/search?q={encoded}&num=10&hl=en&gl=in"

            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
                'Accept-Language': 'en-IN,en-US;q=0.9',
            }
            resp = std_requests.get(url, headers=headers, timeout=12)
            if resp.status_code == 200:
                soup = BeautifulSoup(resp.text, 'html.parser')

                for a in soup.find_all('a', href=True):
                    href = a['href']
                    if 'amazon.in' not in href:
                        continue
                    if href.startswith('/url?q='):
                        href = href.split('/url?q=')[1].split('&')[0]
                        href = urllib.parse.unquote(href)

                    if '/dp/' not in href:
                        continue

                    parent = a
                    for _ in range(10):
                        if parent is None:
                            break
                        matches = re.findall(r'[\u20b9\d,]+', parent.get_text())
                        for m in matches:
                            p = self.clean_price(m)
                            if p and p > 100:
                                h = parent.find(['h3', 'h2'])
                                name = h.get_text(strip=True) if h else product_name
                                print(f"Amazon Google: Rs. {p}")
                                return {
                                    "name": name,
                                    "price": p,
                                    "url": href,
                                    "platform": "Amazon"
                                }
                        parent = parent.parent
        except Exception as e:
            print(f"Amazon Google search fallback failed: {e}")

        print("Amazon: All strategies exhausted — returning None")
        return None
