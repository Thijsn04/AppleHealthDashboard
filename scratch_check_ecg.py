import duckdb
con = duckdb.connect("health.duckdb")
print(con.execute("SELECT type, count(*) FROM health_record WHERE type LIKE '%Electro%' GROUP BY type").df())
con.close()
