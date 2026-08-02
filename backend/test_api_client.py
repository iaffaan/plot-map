import urllib.request
import json

url = "http://127.0.0.1:8000/compile"
payload = {
    "plot": {"width": 40.0, "depth": 40.0},
    "setbacks": {"left": 5.0, "right": 5.0, "bottom": 5.0, "top": 5.0},
    "stair_core": {"width": 10.0, "height": 10.0, "edge": "bottom-left"},
    "rooms": [
        {"name": "Main Door", "type": "Entrance", "min_area": 9.0, "min_width": 3.0, "min_height": 3.0, "requires_ventilation": False, "adjacent_to_road": True},
        {"name": "Living Room", "type": "Living Room", "min_area": 100.0, "min_width": 10.0, "min_height": 10.0, "requires_ventilation": True, "adjacent_to_road": True},
        {"name": "Kitchen", "type": "Kitchen", "min_area": 64.0, "min_width": 8.0, "min_height": 8.0, "requires_ventilation": True, "adjacent_to_road": False},
        {"name": "Bedroom", "type": "Bedroom", "min_area": 100.0, "min_width": 10.0, "min_height": 10.0, "requires_ventilation": True, "adjacent_to_road": False}
    ],
    "adjacencies": [
        ["Main Door", "Living Room"],
        ["Living Room", "Kitchen"],
        ["Living Room", "Bedroom"]
    ]
}

data = json.dumps(payload).encode('utf-8')
req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'}, method='POST')

try:
    print(f"Sending POST request to {url}...")
    with urllib.request.urlopen(req) as response:
        res_data = response.read().decode('utf-8')
        result = json.loads(res_data)
        print("\n[SUCCESS] Response from building compiler:\n")
        print(json.dumps(result, indent=2))
except urllib.error.HTTPError as e:
    print(f"\n[HTTP ERROR {e.code}]: {e.read().decode('utf-8')}")
except Exception as e:
    print(f"\n[ERROR] Connection failed: {e}")
