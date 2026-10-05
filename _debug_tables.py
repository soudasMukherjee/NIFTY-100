import sqlite3
conn = sqlite3.connect('nifty100.db')
cursor = conn.cursor()

# Check market_cap table
cursor.execute("PRAGMA table_info(market_cap)")
print('market_cap schema:')
for row in cursor.fetchall():
    print(f'  {row[1:]}')

cursor.execute('SELECT COUNT(*) FROM market_cap')
count = cursor.fetchone()[0]
print(f'Total rows in market_cap: {count}')

cursor.execute('SELECT company_id, year FROM market_cap LIMIT 5')
print('\nSample market_cap data:')
for row in cursor.fetchall():
    print(f'  company_id={row[0]}, year={row[1]} (type: {type(row[1]).__name__})')

# Check profitandloss table
print('\n\nprofitandloss sample:')
cursor.execute('SELECT company_id, year FROM profitandloss WHERE period_type="ANNUAL" LIMIT 5')
for row in cursor.fetchall():
    print(f'  company_id={row[0]}, year={row[1]} (type: {type(row[1]).__name__})')
