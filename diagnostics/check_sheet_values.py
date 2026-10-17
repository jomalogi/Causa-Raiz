import requests
import io
import pandas as pd

url = "https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927"
r = requests.get(url, timeout=10)
df = pd.read_csv(io.BytesIO(r.content), encoding='utf-8')

print("Aliados in Google Sheet:")
print(df['Aliado'].value_counts(dropna=False))

print("\nCiudades in Google Sheet:")
print(df['Ciudad'].value_counts(dropna=False).head(15))

print("\nTipo de Red in Google Sheet:")
print(df['Tipo de Red'].value_counts(dropna=False))
