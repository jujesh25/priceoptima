import requests; print(requests.post('http://127.0.0.1:8000/compare', json={'url': 'https://www.amazon.in/Apple-MacBook-Chip-13-inch-256GB/dp/B08N5W4NNB'}).text)
