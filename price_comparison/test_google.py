import urllib.parse
from curl_cffi import requests
from bs4 import BeautifulSoup
import re

def get_google_price(site, product_name):
    query = f"site:{site} {product_name} price in India"
    url = f"https://www.google.com/search?q={urllib.parse.quote(query)}"
    print(f"Fetching: {url}")
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, impersonate="chrome110", timeout=10)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Google search results often contain price in snippets or formatted blocks
        # Let's log titles and snippets
        for g in soup.find_all('div', class_='g'):
            title = g.find('h3')
            title = title.text if title else ""
            link = g.find('a')
            href = link['href'] if link else ""
            
            snippet = g.text
            print("Title:", title)
            print("Snippet:", snippet[:200])
            print("Link:", href)
            
            # extract price
            price_match = re.search(r'(?:₹|Rs\.?)\s*([\d,]+)', snippet, re.IGNORECASE)
            if price_match:
                price_str = price_match.group(1).replace(',', '')
                print("Found Price:", price_str)
                return {
                    'name': title,
                    'price': float(price_str),
                    'url': href,
                    'platform': 'Croma' if 'croma' in site else 'Reliance Digital'
                }
            print("-" * 20)
    except Exception as e:
        print("Error:", e)
    return None

if __name__ == "__main__":
    res = get_google_price("croma.com", "Apple iPhone 15 128 GB")
    print("Final Res:", res)
    res2 = get_google_price("reliancedigital.in", "Apple iPhone 15 128 GB")
    print("Final Res2:", res2)
