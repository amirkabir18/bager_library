import csv
import pandas as pd
import sys
sys.stdout.reconfigure(encoding='utf-8')
with open('Book1_csv.csv', 'r') as csvfile:
  csv_reader = csv.reader(csvfile)
for row in csv_reader:
     print(row)
df = pd.read_csv('Book1_csv.csv')
result = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]
if not result.empty:
    print(f"\n✅ {len(result)} نتیجه پیدا شد:")
    print(result)
else:
    print("❌ موردی پیدا نشد.")