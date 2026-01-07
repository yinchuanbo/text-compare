import requests
import json

url = "http://127.0.0.1:5000/api/get_file_content"
payload = {
    "repo_path": "C:/Users/Administrator/Desktop/text-compare",
    "commit_id": "556c61fb67efc9ce43b02ebaf4c2260708129533",
    "file_path": "repro.py"
}
try:
    response = requests.post(url, json=payload)
    data = response.json()
    print("Old Content:", repr(data.get('old_content')))
    print("New Content:", repr(data.get('new_content')))
except Exception as e:
    print(e)
