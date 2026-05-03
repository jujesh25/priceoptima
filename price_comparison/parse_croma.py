import json
import re
from bs4 import BeautifulSoup

def parse_croma():
    with open("croma_debug.html", "r", encoding="utf-8") as f:
        html = f.read()
    
    match = re.search(r'window\.__INITIAL_DATA__=\s*(\{.*?\});\s*(?:</script>|var )', html, re.DOTALL)
    if not match:
        match = re.search(r'window\.__INITIAL_DATA__=\s*(\{.*\})', html)
        
    if match:
        data_str = match.group(1)
        # Handle some JS specific trailing stuff if needed
        try:
            data = json.loads(data_str)
            print("Successfully loaded JSON")
            
            # Find products in the state. Usually under something like productSearch or searchReducer
            # Let's just recursively search the dict for "products" or "results"
            
            def find_products(d):
                if isinstance(d, dict):
                    if 'products' in d and isinstance(d['products'], list):
                        return d['products']
                    if 'results' in d and isinstance(d['results'], list):
                        return d['results']
                    for k, v in d.items():
                        res = find_products(v)
                        if res:
                            return res
                elif isinstance(d, list):
                    for item in d:
                        res = find_products(item)
                        if res:
                            return res
                return None
                
            products = find_products(data)
            if products:
                print(f"Found {len(products)} products!")
                print("First product sample:", {k: products[0][k] for k in ('name', 'price', 'url') if k in products[0]} if isinstance(products[0], dict) else products[0])
            else:
                print("Could not find products list in JSON.")
                print("Keys available:", list(data.keys()))
                
        except Exception as e:
            print("Error parsing JSON:", e)
    else:
        print("Could not find __INITIAL_DATA__")

if __name__ == "__main__":
    parse_croma()
