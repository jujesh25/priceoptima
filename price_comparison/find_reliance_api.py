"""
Find Reliance Digital's actual search API by trying known mobile/web API patterns.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))

import re, urllib.parse, json

try:
    from curl_cffi import requests as cffi_requests
    print("Using curl_cffi")
except ImportError:
    import requests as cffi_requests

search_term = "Apple iPhone 15"
encoded = urllib.parse.quote(search_term, safe='')

# Known Reliance Digital API patterns
api_candidates = [
    # Solr-like search APIs
    f"https://www.reliancedigital.in/search/resources/store/10151/productview/bySearchTerm/{encoded}?pageNumber=0&pageSize=5&currency=INR",
    f"https://www.reliancedigital.in/rildigitalws/v2/rrldigital/products/search?searchTerm={encoded}&pageNumber=0&pageSize=5",
    f"https://www.reliancedigital.in/wcs/resources/store/10151/productview/bySearchTerm/{encoded}?pageNumber=1&pageSize=5&sortBy=3&intentSearchTerm={encoded}&currency=INR",
    # GraphQL-style
    f"https://www.reliancedigital.in/graphql?query={{products(search:\"{search_term}\"){{items{{name,sku,price_range{{minimum_price{{final_price{{value}}}}}}}}}}}}",
    # Direct product listing
    f"https://www.reliancedigital.in/api/catalog_system/pub/facets/search/{encoded}?map=ft&_from=0&_to=4",
]

headers_json = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
    'Accept': 'application/json, */*',
    'Accept-Language': 'en-IN,en;q=0.9',
    'Referer': 'https://www.reliancedigital.in/',
}

for url in api_candidates:
    print(f"\nTrying: {url[:100]}...")
    try:
        r = cffi_requests.get(url, impersonate="chrome110", headers=headers_json, timeout=10)
        print(f"  Status: {r.status_code}")
        ctype = r.headers.get('content-type', '')
        
        if r.status_code == 200:
            text = r.text[:500]
            if 'json' in ctype or text.strip().startswith('{') or text.strip().startswith('['):
                print(f"  JSON response! Sample: {text}")
            else:
                print(f"  HTML response: {text[:150]}")
    except Exception as e:
        print(f"  Error: {str(e)[:60]}")
