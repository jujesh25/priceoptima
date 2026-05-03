import time
from scrapers.amazon import AmazonScraper

def debug_amazon():
    scraper = AmazonScraper()
    url = "https://www.amazon.in/dp/B0DGDZ8BML"
    print(f"Debugging Amazon Scraper with URL: {url}")
    
    try:
        # Setup driver manually to keep it open or dump source
        scraper.setup_driver(headless=True) # Let's try headless first
        scraper.driver.get(url)
        time.sleep(5)
        
        # Save page source for inspection
        with open("amazon_debug_dump.html", "w", encoding="utf-8") as f:
            f.write(scraper.driver.page_source)
        print("HTML source dumped to amazon_debug_dump.html")
        
        # Manually try selectors
        title_selectors = ["#productTitle", "#title", "h1.a-size-large"]
        found_title = None
        for sel in title_selectors:
            try:
                elem = scraper.driver.find_element("css selector", sel)
                print(f"Found title with {sel}: {elem.text.strip()}")
                found_title = elem.text.strip()
            except:
                pass
        
        # Use scraper method
        result = scraper.scrape_url(url)
        print("Scraper Result:")
        print(result)
        
    except Exception as e:
        print(f"Debug Error: {e}")
    finally:
        scraper.teardown_driver()

if __name__ == "__main__":
    debug_amazon()
