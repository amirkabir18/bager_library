import sqlite3
from datetime import date

conn = sqlite3.connect('bager_library.db')
cursor = conn.cursor()
today = date.today()

query = """SELECT *, ABS(julianday(return_date) - julianday(?)) as days_diff FROM loans ORDER BY days_diff LIMIT 1 """

cursor.execute(query, (today))
result = cursor.fetchone()

if result:
    columns = [description[0] for description in cursor.description]
    print("نزدیک‌ترین تاریخ:")
    for i, col in enumerate(columns[:-1]):
        print(f"{col}: {result[i]}")
    print(f"فاصله: {int(result[-1])} روز")
else:
    print("هیچ رکوردی یافت نشد!")