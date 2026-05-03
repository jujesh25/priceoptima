"""
Test script for Amazon, Croma, and Reliance Digital scrapers.
Run from the price_comparison directory with:
    venv\Scripts\python.exe test_scraper.py
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

from scrapers.amazon import AmazonScraper
from scrapers.croma import CromaScraper
from scrapers.reliance import RelianceScraper

PRODUCT_URL = "https://www.amazon.in/Apple-iPhone-15-128-GB/dp/B0CHX1W1XY"
SEARCH_TERM = "Apple iPhone 15 128 GB"

def test_amazon():
    print("\n" + "="*50)
    print("TESTING AMAZON")
    print("="*50)
    scraper = AmazonScraper()
    res = scraper.scrape_url(PRODUCT_URL)
    print(f"Result: {res}")
    return res

def test_croma(product_name):
    print("\n" + "="*50)
    print(f"TESTING CROMA for: '{product_name}'")
    print("="*50)
    scraper = CromaScraper()
    res = scraper.search_product(product_name)
    print(f"Result: {res}")
    return res

def test_reliance(product_name):
    print("\n" + "="*50)
    print(f"TESTING RELIANCE DIGITAL for: '{product_name}'")
    print("="*50)
    scraper = RelianceScraper()
    res = scraper.search_product(product_name)
    print(f"Result: {res}")
    return res

if __name__ == "__main__":
    amazon_res = test_amazon()
    
    search_name = amazon_res['name'] if amazon_res and amazon_res.get('name') else SEARCH_TERM
    
    croma_res = test_croma(search_name)
    reliance_res = test_reliance(search_name)

    print("\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    all_results = [r for r in [amazon_res, croma_res, reliance_res] if r]
    if not all_results:
        print("No results found from any platform.")
    else:
        for r in all_results:
            platform = r.get('platform', 'Unknown')
            price = r.get('price', 'N/A')
            url = r.get('url', 'N/A')[:60]
            price_str = f"Rs.{price:,.0f}" if price else "Price not found"
        print(f"  {platform}: {price_str} -> {url}...")
        
        prices = [(r['platform'], r['price']) for r in all_results if r.get('price')]
        if prices:
            best = min(prices, key=lambda x: x[1])
            print(f"\nBest price found: {best[0]} at Rs.{best[1]:,.0f}")
