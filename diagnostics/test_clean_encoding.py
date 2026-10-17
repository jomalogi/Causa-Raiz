import requests
import io
import pandas as pd
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

url = "https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927"
r = requests.get(url, timeout=10)
df = pd.read_csv(io.BytesIO(r.content), encoding='utf-8')

# Check Causas
print("Clean Causas:")
for c in df['Causa Principal'].dropna().unique():
    print(" -", c)

print("\nClean Subcausas (first 10):")
for s in df['Subcausa'].dropna().unique()[:10]:
    print(" -", s)
