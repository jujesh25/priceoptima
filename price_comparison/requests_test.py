import requests
from bs4 import BeautifulSoup
import urllib.parse

def test_reliance():
    print("Testing Reliance...")
    url = "https://www.reliancedigital.in/search?q=Apple%20iPhone%2015%20128%20GB"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    }
    response = requests.get(url, headers=headers)
    print("Status code:", response.status_code)
    soup = BeautifulSoup(response.content, 'html.parser')
    
    print("Page Title:", soup.title.text if soup.title else "No Title")
    
    # Try finding products
    products = soup.select("li.gridItem, div.pl__container div[data-id], .sp__product")
    print(f"Found {len(products)} products on Reliance")
    
def test_croma():
    print("\nTesting Croma...")
    url = "https://www.croma.com/searchB?q=Apple%20iPhone%2015%20128%20GB%3A"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36',
    }
    response = requests.get(url, headers=headers)
    print("Status code:", response.status_code)
    soup = BeautifulSoup(response.content, 'html.parser')
    print("Page Title:", soup.title.text if soup.title else "No Title")
    products = soup.select("li.product-item, .plp-card, .product-info")
    print(f"Found {len(products)} products on Croma")

if __name__ == '__main__':
    test_reliance()
    test_croma()
