import sqlite3

conn = sqlite3.connect('nifty100.db')
cursor = conn.cursor()

# Check if financial_ratios actually has a year_raw column
cursor.execute("PRAGMA table_info(financial_ratios)")
print("financial_ratios columns:")
for row in cursor.fetchall():
    print(f"  {row}")

# Check distinct values of year to see if there are string values mixed in
cursor.execute("SELECT DISTINCT year FROM financial_ratios ORDER BY typeof(year), year")
print("\nDistinct year values (first 20):")
for i, row in enumerate(cursor.fetchall()):
    if i >= 20:
        break
    print(f"  {row[0]} (type: {type(row[0]).__name__})")

# Check if there are any rows where year is not an integer
cursor.execute("SELECT COUNT(*) FROM financial_ratios WHERE typeof(year) != 'integer'")
non_int_count = cursor.fetchone()[0]
print(f"\nRows where year is not integer: {non_int_count}")

if non_int_count > 0:
    cursor.execute("SELECT company_id, year FROM financial_ratios WHERE typeof(year) != 'integer' LIMIT 10")
    print("Sample non-integer years:")
    for row in cursor.fetchall():
        print(f"  company_id={row[0]}, year={row[1]}")
