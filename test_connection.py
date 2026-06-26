import requests
from config import PASSWORD

url = "https://api.lyricapp.ru/tracks/get"
payload = {
    "user_id": 1,
    "password": PASSWORD,
    "slug": "valentin_strykalo_92"
}

response = requests.post(url, json=payload)

print("Status Code:", response.status_code)
print("Headers:", response.headers)
print("Raw Response:", response.text)