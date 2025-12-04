import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_features():
    print("--- Testing Deduplication ---")
    # Create a dummy file with duplicates
    content = "https://example.com\nhttps://example.com\nhttps://google.com\n"
    files = {'file': ('test_dupes.txt', content)}
    
    res = requests.post(f"{BASE_URL}/api/upload", files=files)
    data = res.json()
    print(f"Upload response: {data}")
    
    if data['count'] != 2:
        print(f"FAILED: Expected 2 URLs, got {data['count']}")
        sys.exit(1)
    else:
        print("PASSED: Deduplication worked.")

    print("\n--- Testing Pause/Resume ---")
    # Start check
    print("1. Starting check...")
    res = requests.post(f"{BASE_URL}/api/start", json={
        "concurrency": 1,
        "requests_per_second": 1,
        "timeout": 5,
        "resume": False
    })
    if res.status_code != 200:
        print(f"Start failed: {res.text}")
        sys.exit(1)
        
    time.sleep(1)
    
    # Pause (Stop)
    print("2. Pausing...")
    res = requests.post(f"{BASE_URL}/api/stop")
    if res.status_code != 200:
        print(f"Pause failed: {res.text}")
        sys.exit(1)
        
    # Wait for graceful shutdown
    time.sleep(5)
        
    # Check status - should be not running
    res = requests.get(f"{BASE_URL}/api/status")
    data = res.json()
    print(f"Status after pause: {data}")
    if data['running']:
        print("FAILED: Job should be stopped")
        sys.exit(1)
        
    # Resume
    print("3. Resuming...")
    res = requests.post(f"{BASE_URL}/api/start", json={
        "concurrency": 1,
        "requests_per_second": 1,
        "timeout": 5,
        "resume": True
    })
    if res.status_code != 200:
        print(f"Resume failed: {res.text}")
        sys.exit(1)
        
    print("4. Checking final status...")
    while True:
        res = requests.get(f"{BASE_URL}/api/status")
        data = res.json()
        if not data['running']:
            break
        time.sleep(0.5)
        
    print(f"Final status: {data}")
    if data['checked'] != 2:
        print(f"FAILED: Expected 2 checked, got {data['checked']}")
    else:
        print("PASSED: Resume worked.")

if __name__ == "__main__":
    try:
        test_features()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
