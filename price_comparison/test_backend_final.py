import requests
import json
import time

def test_compare():
    url = "http://127.0.0.1:8000/compare"
    # Using a confirmed valid iPhone 15 URL for testing
    payload = {
        "url": "https://www.amazon.in/dp/B0CHX6N27Y" 
    }
    headers = {
        "Content-Type": "application/json"
    }
    
    print(f"--- Starting Backend Test ---")
    print(f"Testing with URL: {payload['url']}")
    print(f"Note: This may take up to 60 seconds...")
    
    try:
        start_time = time.time()
        response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=120)
        end_time = time.time()
        
        print(f"Status Code: {response.status_code}")
        print(f"Time Taken: {end_time - start_time:.2f} seconds")
        
        if response.status_code == 200:
            data = response.json()
            print("\nProduct Found:")
            print(f"Name: {data.get('product_name')}")
            print(f"Amazon Price: ₹{data.get('amazon', {}).get('price')}")
            
            # Check other platforms
            for plat in ['flipkart', 'croma', 'reliance']:
                p_data = data.get(plat)
                if p_data:
                    status = "Scraped" if not p_data.get('estimated') else "Estimated"
                    print(f"{plat.capitalize()}: ₹{p_data.get('price')} ({status})")
                else:
                    print(f"{plat.capitalize()}: Not Found")
        else:
            print(f"Error Response: {response.text}")
            
    except Exception as e:
        print(f"Detailed Error: {e}")

if __name__ == "__main__":
    test_compare()
