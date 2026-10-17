import sys
import requests
import pandas as pd
from io import StringIO

url = "https://docs.google.com/spreadsheets/d/1U_xNMkUFnu-rQpZu7mmbn8sfmbIQIjEO326jghA-U38/export?format=csv&gid=1234840927"
r = requests.get(url, timeout=10)
print("r.encoding default:", r.encoding)
r.encoding = 'utf-8'

df = pd.read_csv(StringIO(r.text))
print("Columns:", df.columns.tolist())
causa_col = [c for c in df.columns if 'Causa' in c and 'Principa' in c]
subcausa_col = [c for c in df.columns if 'Subcausa' in c]
print("Causa col:", causa_col)
print("Subcausa col:", subcausa_col)

if causa_col:
    print("\nUnique Causas with utf-8:")
    print(df[causa_col[0]].value_counts().head(10))

if subcausa_col:
    print("\nUnique Subcausas with utf-8:")
    print(df[subcausa_col[0]].value_counts().head(10))
