import time
import random
import re
from difflib import SequenceMatcher
from bs4 import BeautifulSoup

try:
    import undetected_chromedriver as uc
    UC_AVAILABLE = True
except ImportError:
    UC_AVAILABLE = False
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service as ChromeService
    try:
        from webdriver_manager.chrome import ChromeDriverManager
        WDM_AVAILABLE = True
    except ImportError:
        WDM_AVAILABLE = False


class BaseScraper:
    def __init__(self, use_selenium=True):
        self.use_selenium = use_selenium
        self.driver = None

    def setup_driver(self, headless=True):
        """Setup Chrome driver — prefers undetected_chromedriver for bot bypass."""
        if UC_AVAILABLE:
            options = uc.ChromeOptions()
            options.add_argument("--no-sandbox")
            options.add_argument("--disable-dev-shm-usage")
            options.add_argument("--window-size=1920,1080")
            options.add_argument("--disable-gpu")
            options.add_argument("--lang=en-IN")
            if headless:
                options.add_argument("--headless=new")
            try:
                self.driver = uc.Chrome(options=options, use_subprocess=True)
            except Exception as e:
                print(f"UC driver init failed: {e}, falling back")
                self._setup_standard_driver(headless)
        else:
            self._setup_standard_driver(headless)

    def _setup_standard_driver(self, headless=True):
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        chrome_options = Options()
        if headless:
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--lang=en-IN")

        user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        ]
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")

        try:
            from webdriver_manager.chrome import ChromeDriverManager
            from selenium.webdriver.chrome.service import Service as ChromeService
            service = ChromeService(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        except Exception:
            self.driver = webdriver.Chrome(options=chrome_options)

        try:
            self.driver.execute_script(
                "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
            )
        except Exception:
            pass

    def teardown_driver(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception:
                pass
            self.driver = None

    def get_headers(self):
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        }

    # Keep old name for compat
    def get_curl_headers(self):
        return self.get_headers()

    def clean_price(self, price_str):
        if not price_str:
            return None
        price_str = str(price_str)
        # Remove currency symbols, commas, spaces
        clean_str = re.sub(r'[^\d.]', '', price_str.replace(',', ''))
        # Handle multiple dots (keep only first)
        parts = clean_str.split('.')
        if len(parts) > 2:
            clean_str = parts[0] + '.' + ''.join(parts[1:])
        if not clean_str:
            return None
        try:
            val = float(clean_str)
            # Price sanity: must be > 100 and < 50,00,000 (5 million INR)
            return val if 100 < val < 5_000_000 else None
        except ValueError:
            return None

    def similarity_score(self, a: str, b: str) -> float:
        """Return a 0-1 similarity ratio between two product name strings."""
        if not a or not b:
            return 0.0
        a_clean = re.sub(r'[^a-z0-9\s]', ' ', a.lower()).strip()
        b_clean = re.sub(r'[^a-z0-9\s]', ' ', b.lower()).strip()
        return SequenceMatcher(None, a_clean, b_clean).ratio()

    def name_is_relevant(self, result_name: str, query_name: str, threshold: float = 0.25) -> bool:
        """Return True if result_name is sufficiently similar to query_name."""
        score = self.similarity_score(result_name, query_name)
        print(f"  [similarity] {score:.2f} | {result_name[:60].encode('ascii', 'ignore').decode()} vs query")
        return score >= threshold

    def scrape_url(self, url: str):
        """Scrape a specific product URL. Override in subclasses."""
        raise NotImplementedError("scrape_url() not implemented for this scraper")

    def search_product(self, product_name):
        raise NotImplementedError("Subclasses must implement this method")
