import sqlite3
conn = sqlite3.connect('nifty100.db')
cursor = conn.cursor()
# Get the schema for financial_ratios
cursor.execute("PRAGMA table_info(financial_ratios)")
print('financial_ratios schema:')
for row in cursor.fetchall():
    print(f'  {row}')

# Get sample data
cursor.execute('SELECT company_id, year FROM financial_ratios LIMIT 5')
print('\nSample data:')
for row in cursor.fetchall():
    print(f'  company_id={row[0]}, year={row[1]} (type: {type(row[1]).__name__})')
    
# Check if there's an issue with JOIN
cursor.execute("""
    SELECT fr.company_id, fr.year, pl.year_raw
    FROM financial_ratios fr
    LEFT JOIN profitandloss pl ON fr.company_id = pl.company_id AND fr.year = pl.year
    LIMIT 5
""")
print('\nJOIN test:')
for row in cursor.fetchall():
    print(f'  fr.year={row[1]}, pl.year_raw={row[2]}')
