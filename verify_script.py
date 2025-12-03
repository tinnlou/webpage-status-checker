import requests
import time
import sys

BASE_URL = "http://localhost:8000"

def test_api():
    print("1. Uploading file...")
    with open("test_urls.txt", "rb") as f:
        res = requests.post(f"{BASE_URL}/api/upload", files={"file": f})
    print(f"Upload response: {res.json()}")
    if res.status_code != 200:
        sys.exit(1)

    print("2. Starting check...")
    res = requests.post(f"{BASE_URL}/api/start", json={
        "concurrency": 10,
        "requests_per_second": 5,
        "timeout": 5
    })
    print(f"Start response: {res.json()}")
    if res.status_code != 200:
        sys.exit(1)

    print("3. Polling status...")
    while True:
        res = requests.get(f"{BASE_URL}/api/status")
        data = res.json()
        print(f"Status: {data}")
        if not data["running"] and data["checked"] == data["total"]:
            break
        time.sleep(1)

    print("4. Checking results...")
    res = requests.get(f"{BASE_URL}/api/results")
    if res.status_code == 200:
        print("Results downloaded successfully.")
        print("Content preview:")
        print(res.text[:500])
    else:
        print("Failed to download results")
        sys.exit(1)

if __name__ == "__main__":
    # Wait for server to start
    time.sleep(2)
    try:
        test_api()
    except Exception as e:
        print(f"Test failed: {e}")
        sys.exit(1)
