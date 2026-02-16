
import requests
import sys

url = "https://logo.clearbit.com/google.com"
print(f"Testing connection to {url}...")

try:
    resp = requests.get(url, timeout=5)
    print(f"Status: {resp.status_code}")
    print(f"Content-Type: {resp.headers.get('content-type')}")
    print(f"Content Length: {len(resp.content)}")
except Exception as e:
    print(f"Error: {e}")
