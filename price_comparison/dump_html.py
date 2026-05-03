import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup

chrome_options = Options()
chrome_options.add_argument('--headless=new')
service = ChromeService(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service, options=chrome_options)

# Amazon
try:
    driver.get('https://www.amazon.in/Apple-New-MacBook-Air-M1/dp/B08N5W4NNB')
    time.sleep(3)
    with open('amazon_dump.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    print('amazon done')
except Exception as e: print(e)

# Croma
try:
    driver.get('https://www.croma.com/searchB?q=Apple%20MacBook%20Air%20M1')
    time.sleep(4)
    with open('croma_dump.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    print('croma done')
except Exception as e: print(e)

# Reliance
try:
    driver.get('https://www.reliancedigital.in/search?q=Apple%20MacBook%20Air%20M1')
    time.sleep(4)
    with open('reliance_dump.html', 'w', encoding='utf-8') as f:
        f.write(driver.page_source)
    print('reliance done')
except Exception as e: print(e)

driver.quit()
