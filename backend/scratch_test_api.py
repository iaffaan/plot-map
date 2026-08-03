import urllib.request
import json
import urllib.error

payload = {
    "plot": {"width": 43.75, "depth": 41.0},
    "setbacks": {"left": 1.5, "right": 1.5, "front": 3.0, "back": 2.0},
    "floors": 3,
    "description": "Generate an optimized residential building layout with maximum cross-ventilation and natural light",
    "time_limit_sec": 15
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(
    "http://127.0.0.1:8001/compile", 
    data=data, 
    headers={'Content-Type': 'application/json'}
)

try:
    print("Sending POST request to http://127.0.0.1:8001/compile...")
    with urllib.request.urlopen(req, timeout=20) as response:
        status_code = response.getcode()
        print(f"Status Code: {status_code}")
        res = json.loads(response.read().decode('utf-8'))
        if res.get("success"):
            print("Success! Metadata:")
            print(json.dumps(res.get("metadata"), indent=2))
            print("Rooms placed:")
            for name, room in res.get("layout", {}).items():
                print(f" - {name}: x={room['x']}, y={room['y']}, w={room['width']}, h={room['height']}")
        else:
            print(f"Compilation Failed: {res.get('error')}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    print("Response body:")
    print(e.read().decode('utf-8'))
except Exception as e:
    print(f"API request failed: {e}")
