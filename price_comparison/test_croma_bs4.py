from curl_cffi import requests
from bs4 import BeautifulSoup

url = "https://www.croma.com/searchB?q=Apple%20iPhone%2015%20128%20GB%3A"
response = requests.get(url, impersonate="chrome110")
soup = BeautifulSoup(response.text, 'html.parser')
products = soup.select("li.product-item, .plp-card, .product-info, h3, .cp-product")
print("Found elements:", len(products))
if products:
    print("First product HTML snippet:", str(products[0])[:200])
else:
    print("No products found in the HTML. Maybe it's CSR (Client Side Rendered).")
    
# Let's search for json blocks or window.__INITIAL_STATE__
scripts = soup.find_all('script')
for s in scripts:
    if s.string and 'window.__INITIAL_STATE__' in s.string:
        print("Found __INITIAL_STATE__ script!")
    if s.string and 'searchResult' in s.string:
        print("Found searchResult in script!")
