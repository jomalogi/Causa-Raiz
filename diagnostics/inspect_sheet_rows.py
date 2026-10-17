import requests
import io
import pandas as pd

url = "https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927"
r = requests.get(url, timeout=10)
df = pd.read_csv(io.BytesIO(r.content), encoding='utf-8')
print("Columns:", df.columns.tolist())
print("\nHead 3 rows:")
print(df.head(3).to_dict(orient='records'))
