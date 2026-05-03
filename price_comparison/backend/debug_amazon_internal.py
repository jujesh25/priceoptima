import sys
import os
import time

# Add parent directory to path so we can import from scrapers
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers.amazon import AmazonScraper

def debug_amazon_direct():
    scraper = AmazonScraper()
    url = "https://www.amazon.in/dp/B0CHX6N27Y"
    print(f"Direct Debug of Amazon Scraper: {url}")
    
    try:
        # We'll use headless=False for a moment if we could, but we can't see it.
        # Let's try headless=True first.
        print("Starting driver...")
        scraper.setup_driver(headless=True)
        print("Driver started. Navigating...")
        scraper.driver.get(url)
        time.sleep(10) # Give it plenty of time
        
        print("Page loaded. Current Title:", scraper.driver.title)
        
        if "Robot Check" in scraper.driver.title or "CAPTCHA" in scraper.driver.page_source:
             print("BOT DETECTION DETECTED!")
        
        # Manually extract title
        title_selectors = ["#productTitle", "#title", "h1.a-size-large"]
        for sel in title_selectors:
            try:
                elem = scraper.driver.find_element("css selector", sel)
                print(f"Found title with {sel}: {elem.text.strip()}")
            except:
                pass
                
        # Run the actual scrape method
        print("Running scrape_url logic...")
        # We need to monkeypatch teardown if we want to keep it alive here, but we'll just run it.
        # Actually scrape_url sets up its own driver, so let's call it directly.
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        scraper.teardown_driver()

if __name__ == "__main__":
    debug_amazon_direct()
