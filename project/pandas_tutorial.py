import pandas as pd

# خواندن فایل
df = pd.read_csv('filename.csv')

# دریافت ورودی از کاربر
search_term = input("چیزی که می‌خواهید جستجو کنید: ")

# جستجو در همه ستون‌ها (هر جا که عبارت پیدا شود)
result = df[df.apply(lambda row: row.astype(str).str.contains(search_term, case=False).any(), axis=1)]

# یا جستجو در یک ستون خاص (مثلاً ستون 'name')
# result = df[df['name'].astype(str).str.contains(search_term, case=False)]

# نمایش نتایج
if not result.empty:
    print(f"\n✅ {len(result)} نتیجه پیدا شد:")
    print(result)
else:
    print("❌ موردی پیدا نشد.")