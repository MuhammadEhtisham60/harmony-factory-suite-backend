import requests
import json
import time

url = "http://127.0.0.1:8000/api/v1/yarn-intakes/"
token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ0b2tlbl90eXBlIjoiYWNjZXNzIiwiZXhwIjoxNzkxMzE3OTE3LCJpYXQiOjE3OTEyODkxMTcsImp0aSI6IjVlNTJkZGRhNGNiMzRiNDVhZmZkNTZmZjMwN2Q2YTJmIiwidXNlcl9pZCI6IjQifQ.iWN2j85dUtbCYuKSzEz3lretSH9Nhz8zCpYhjGZNrNA"
headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json"
}

payload_template = {
    "yarnName": "cotton",
    "yarnType": "100% Ring Spun Cotton",
    "yarnCount": "20s / 1",
    "setNo": "LOT-YRN-412",
    "supplier": 1,
    "bags": 120,
    "conesPerBag": 24,
    "weightPerBagKg": "45.360",
    "ratePerBag": "125000.00",
    "intakeDate": "2026-10-06",
    "notes": "",
    "yarn_name": "cotton",
    "yarn_type": "100% Ring Spun Cotton",
    "yarn_count": "20s / 1",
    "set_no": "LOT-YRN-412",
    "cones_per_bag": 24,
    "weight_per_bag_kg": "45.360",
    "rate_per_bag": "125000.00",
    "intake_date": "2026-10-06"
}

success_count = 0
for i in range(1, 26):
    payload = payload_template.copy()
    payload["setNo"] = f"LOT-YRN-412-{i}"
    payload["set_no"] = f"LOT-YRN-412-{i}"
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code in (200, 201):
            success_count += 1
            print(f"Record {i} created successfully.")
        else:
            print(f"Failed to create record {i}. Status: {response.status_code}, Response: {response.text}")
    except Exception as e:
        print(f"Error on record {i}: {e}")
    time.sleep(0.1)

print(f"Finished. Created {success_count} records.")
