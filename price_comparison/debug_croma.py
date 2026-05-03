"""Quick debug: fetch Croma search results and analyze the HTML structure."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import re, urllib.parse
from bs4 import BeautifulSoup

try:
    from curl_cffi import requests as cffi_requests
    print("Using curl_cffi")
except ImportError:
    import requests as cffi_requests
    print("Using requests")

search_term = "Apple iPhone 15 128 GB"
encoded = urllib.parse.quote(search_term, safe='')
url = f"https://www.croma.com/searchB?q={encoded}%3Arelevance&text={encoded}"
print("URL:", url)

r = cffi_requests.get(url, impersonate="chrome110", timeout=20, headers={
    'Accept-Language': 'en-IN,en-US;q=0.9',
    'Referer': 'https://www.croma.com/',
})
print("Status:", r.status_code)

soup = BeautifulSoup(r.text, 'html.parser')
print("Title:", soup.title.text if soup.title else "N/A")

# Save for inspection
with open("croma_debug2.html", "w", encoding="utf-8") as f:
    f.write(r.text)
print("Saved croma_debug2.html")

# Search for product elements
for selector in ['li.product-item', '.plp-card', '.cp-product', '[data-product-id]', 'li', 'article']:
    items = soup.select(selector)
    if items:
        print(f"  Found {len(items)} items with '{selector}'")
        if len(items) < 20:  # Show only if reasonable count
            for item in items[:2]:
                print(f"    Sample: {str(item)[:200]}")
        break

# Find any prices
prices_found = re.findall(r'Rs\.?\s*[\d,]+|INR\s*[\d,]+', r.text)
print("Prices in text (Rs):", prices_found[:5])

# Also check for ₹ — may need unicode
import json
# Check for JSON embedded data
match = re.search(r'window\.__INITIAL_DATA__\s*=\s*({.*?})\s*;', r.text[:5000], re.DOTALL)
if match:
    print("Found __INITIAL_DATA__!")
else:
    print("No __INITIAL_DATA__ in first 5000 chars")

# Check for product name in text
if search_term.lower() in r.text.lower():
    print("Product name FOUND in HTML!")
else:
    print("Product name NOT found in HTML (possible JS rendering issue)")
