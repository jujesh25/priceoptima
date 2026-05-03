import sys, os
sys.path.insert(0, os.path.dirname(__file__))

import requests as req

# 1. Health check
try:
    r = req.get('http://127.0.0.1:8000/health', timeout=5)
    print('Health:', r.json())
except Exception as e:
    print('Health check failed (server may not be running):', e)

# 2. Platform detection
from app import detect_platform

tests = [
    ('https://www.amazon.in/dp/B0CHWRHZNR',                              'amazon'),
    ('https://www.flipkart.com/apple-iphone-15/p/itm6ea3a87c834a9',      'flipkart'),
    ('https://www.croma.com/apple-iphone-15-128gb-black/p/265716',       'croma'),
    ('https://www.reliancedigital.in/apple-iphone-15-128-gb-black/p/1',   'reliance'),
    ('https://www.apple.com/in/shop/buy-iphone/iphone-15',               None),
    ('https://www.samsung.com/in/smartphones/galaxy-s24/',                None),
]

print('\nPlatform detection:')
all_pass = True
for url, expected in tests:
    result = detect_platform(url)
    status = 'PASS' if result == expected else 'FAIL'
    if status == 'FAIL':
        all_pass = False
    short = url[:60] + ('...' if len(url) > 60 else '')
    print(f'  [{status}] {short}')
    print(f'         expected={expected!r}  got={result!r}')

print()
print('All tests passed!' if all_pass else 'SOME TESTS FAILED.')
