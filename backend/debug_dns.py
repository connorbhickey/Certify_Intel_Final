
import requests
import sys

url = "https://www.google.com"
print(f"Testing connection to {url}...")

try:
    resp = requests.get(url, timeout=5)
    print(f"Status: {resp.status_code}")
except Exception as e:
    print(f"Error: {e}")
