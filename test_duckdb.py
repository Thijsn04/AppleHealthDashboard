import zipfile
from pathlib import Path
from apple_health_dashboard.ingest.importer import import_export_xml_to_sqlite_all

zip_path = Path("export.zip")
extract_dir = Path(".tmp")

if not extract_dir.exists():
    extract_dir.mkdir()

print("Extracting...")
with zipfile.ZipFile(zip_path, 'r') as zip_ref:
    zip_ref.extractall(extract_dir)

xml_path = extract_dir / "apple_health_export" / "export.xml"
db_path = Path("health.duckdb")

if db_path.exists():
    db_path.unlink()

def progress(t, n):
    if n % 10000 == 0:
        print(f"{t}: {n}")

print("Importing to DuckDB...")
res = import_export_xml_to_sqlite_all(xml_path, db_path, on_progress=progress)
print(res)

import duckdb
con = duckdb.connect(str(db_path))
print("Count records:", con.execute("SELECT COUNT(*) FROM health_record").fetchone())
print("Count workouts:", con.execute("SELECT COUNT(*) FROM workout").fetchone())
