from curl_cffi import requests

print("Testing Croma with curl_cffi...")
url = "https://www.croma.com/searchB?q=Apple%20iPhone%2015%20128%20GB%3A"
response = requests.get(url, impersonate="chrome110")
print("Status code:", response.status_code)
if response.status_code != 200:
    print(response.text[:200])
else:
    print("Success! Title:", response.text[response.text.find('<title>'):response.text.find('</title>')+8])
