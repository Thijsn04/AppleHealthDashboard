# Apple Health Dashboard

A local, privacy-first dashboard to explore your Apple Health export.

## Privacy (100% local)
- Your data is **never** uploaded to a cloud.
- Uploads are stored temporarily in `./.tmp/`.
- The app imports data into a local SQLite database: `./health.db`.
- These files are listed in `.gitignore` so you don’t accidentally commit them.

## Create an Apple Health export
On your iPhone:
1. Open **Health**
2. Tap your **profile** (top-right)
3. Choose **Export All Health Data**

You’ll get a `.zip` that usually contains `apple_health_export/export.xml`.

## 5-minute quickstart (Windows / PowerShell)
1) Go to the project folder:

```powershell
cd "C:\Users\thijs\PycharmProjects\AppleHealthDashboard"
```

2) Install dependencies:

```powershell
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

3) Start the dashboard:

```powershell
python -m streamlit run app.py
```

4) In the app:
- Upload `export.zip` or `export.xml`
- Click **Import to database**

## Reset / delete local data
In the app you can delete locally stored data via **Delete local data**.
This removes `health.db` and `./.tmp/`.

## Project layout
- `app.py` — Streamlit UI
- `apple_health_dashboard/ingest/` — streaming parsers + importer
- `apple_health_dashboard/storage/` — SQLite schema + read/write helpers
- `apple_health_dashboard/services/` — pandas aggregations
- `apple_health_dashboard/web/` — UI helpers (styling, explore browser, i18n)
- `tests/` — unit tests

## Development
Run tests:

```powershell
python -m pytest
```

Run lint:

```powershell
python -m ruff check .
```

## Troubleshooting
- **Streamlit not found**: use `python -m streamlit run app.py`
- **Import is slow**: large exports can take a few minutes (especially the first import)
- **No data visible**: import first, then use refresh if needed
