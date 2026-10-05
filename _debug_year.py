import sqlite3

conn = sqlite3.connect('nifty100.db')
cursor = conn.cursor()

# Check what's happening with the subquery
query = """
    SELECT fr.company_id, fr.year, MAX(fr.year) OVER (PARTITION BY fr.company_id) as max_year
    FROM financial_ratios fr
    LIMIT 10
"""

cursor.execute(query)
print("Testing subquery approach:")
for row in cursor.fetchall():
    print(f"  company_id={row[0]}, year={row[1]}, max_year={row[2]}")

# Let's also check what the MAX returns directly
query2 = """
    SELECT company_id, MAX(year) FROM financial_ratios GROUP BY company_id LIMIT 10
"""

cursor.execute(query2)
print("\nDirect MAX(year) per company:")
for row in cursor.fetchall():
    print(f"  company_id={row[0]}, max_year={row[1]}")

# Now let's check what the original WHERE clause is doing
query3 = """
    SELECT fr.company_id, fr.year, 
           (SELECT MAX(year) FROM financial_ratios fr2 WHERE fr2.company_id = fr.company_id) as max_year
    FROM financial_ratios fr
    WHERE fr.year = (
        SELECT MAX(year) FROM financial_ratios fr2
        WHERE fr2.company_id = fr.company_id
    )
    LIMIT 10
"""

cursor.execute(query3)
print("\nWith WHERE clause:")
for row in cursor.fetchall():
    print(f"  company_id={row[0]}, year={row[1]}, max_year={row[2]}")
    
# Check if there are any unusual data types
query4 = """
    SELECT typeof(year), year, COUNT(*) FROM financial_ratios GROUP BY typeof(year), year LIMIT 10
"""

cursor.execute(query4)
print("\nData types in year column:")
for row in cursor.fetchall():
    print(f"  type={row[0]}, year={row[1]}, count={row[2]}")
