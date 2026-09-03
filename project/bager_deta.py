import pandas as pd
column_name = "نویسنده"
search_value = "مسلم کامیاب"
file_path = "Book1.xlsx"
df = pd.read_excel(file_path, sheet_name=0)
results = df[df[column_name] == search_value]
if not results.empty:
    print(f"✅ {len(results)} ردیف در ستون '{column_name}' پیدا شد:")
    print(results)
else:
    print("❌ پیدا نشد.")