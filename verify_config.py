import requests
import time
import sys

BASE_URL = "http://127.0.0.1:8000"

def test_config_update():
    print("1. Uploading URLs...")
    # Upload enough URLs to give us time to pause
    urls = "\n".join([f"http://example.com/{i}" for i in range(100)])
    files = {"file": ("test.txt", urls)}
    requests.post(f"{BASE_URL}/api/upload", files=files)

    print("2. Starting check with Concurrency=10...")
    # Start with concurrency 10
    payload = {
        "concurrency": 10,
        "requests_per_second": 10,
        "timeout": 5,
        "retries": 0,
        "resume": False
    }
    requests.post(f"{BASE_URL}/api/start", json=payload)
    
    time.sleep(1)
    
    print("3. Pausing...")
    requests.post(f"{BASE_URL}/api/stop")
    time.sleep(2) # Wait for stop
    
    print("4. Resuming with Concurrency=50 (CHANGED)...")
    # Resume with DIFFERENT config
    payload_resume = {
        "concurrency": 50,
        "requests_per_second": 100,
        "timeout": 10,
        "retries": 3,
        "resume": True
    }
    res = requests.post(f"{BASE_URL}/api/start", json=payload_resume)
    print(f"Resume response: {res.json()}")
    
    print("\nCHECK SERVER LOGS ABOVE. You should see two '--- Starting Job ---' blocks.")
    print("The second one should show Concurrency=50, Retries=3.")

if __name__ == "__main__":
    test_config_update()
