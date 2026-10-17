import json
import urllib.request

url = "http://127.0.0.1:8001/run"
prompt = "Write 3 facts about the current project into FACTS.txt."

payload = json.dumps({"prompt": prompt}).encode("utf-8")
request = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")

with urllib.request.urlopen(request) as response:
    body = response.read().decode("utf-8")
    print(body)
