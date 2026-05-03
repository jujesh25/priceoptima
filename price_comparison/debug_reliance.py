"""Quick debug: fetch Reliance Digital search API."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import re, urllib.parse, json

try:
    from curl_cffi import requests as cffi_requests
    print("Using curl_cffi")
except ImportError:
    import requests as cffi_requests
    print("Using requests")

search_term = "Apple iPhone 15 128 GB"
encoded = urllib.parse.quote(search_term, safe='')

# Try different API endpoints
endpoints = [
    f"https://www.reliancedigital.in/rildigitalws/v2/rrldigital/cms/pagedata/search?searchQuery={encoded}&currentPage=0&pageSize=5",
    f"https://api.reliancedigital.in/v1/products/search?searchString={encoded}&pageNo=0&pageSize=5",
    f"https://www.reliancedigital.in/search?q={encoded}",
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, text/html, */*',
    'Accept-Language': 'en-IN,en-US;q=0.9,en;q=0.8',
    'Referer': 'https://www.reliancedigital.in/',
    'Origin': 'https://www.reliancedigital.in',
}

for url in endpoints:
    print(f"\nTrying: {url[:80]}...")
    try:
        r = cffi_requests.get(url, impersonate="chrome110", headers=headers, timeout=15)
        print(f"Status: {r.status_code}, Content-Type: {r.headers.get('content-type', 'N/A')[:40]}")
        
        ctype = r.headers.get('content-type', '')
        if 'json' in ctype:
            try:
                data = r.json()
                print("JSON keys:", list(data.keys())[:10] if isinstance(data, dict) else type(data))
                print("Sample:", str(data)[:300])
            except Exception as e:
                print("JSON parse failed:", e)
                print("Raw (200 chars):", r.text[:200])
        else:
            # HTML page
            print("HTML page (200 chars):", r.text[:200])
            if 'iphone' in r.text.lower():
                print("  -> 'iphone' found in response!")
            else:
                print("  -> 'iphone' NOT found in response")
    except Exception as e:
        print(f"Error: {e}")
