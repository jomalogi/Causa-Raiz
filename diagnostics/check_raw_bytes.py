import requests

url = "https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927"
r = requests.get(url, timeout=10)
raw = r.content

# Let's see some samples around "Dañado" or "Técnico"
print("Raw sample containing bytes:")
for chunk in raw.split(b"\n")[:10]:
    print(repr(chunk))
