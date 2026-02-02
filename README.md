# Apple Health Dashboard

Lokale dashboard-app om je Apple Health export te analyseren.

## Belangrijk: 100% lokaal
- Je data wordt **niet** naar een cloud geüpload.
- Uploads worden tijdelijk opgeslagen in `./.tmp/`.
- De app importeert data naar een lokale SQLite database: `./health.db`.
- Deze bestanden staan in `.gitignore` zodat je ze niet per ongeluk commit.

## Apple Health export maken
Op je iPhone:
1. Open **Gezondheid**
2. Tik op je **profiel** (rechtsboven)
3. Kies **Exporteer alle gezondheidsgegevens**

Je krijgt een `.zip` met (meestal) `apple_health_export/export.xml`.

## 5 minuten quickstart (Windows / PowerShell)
1) Ga naar de projectmap:

```powershell
cd "C:\Users\thijs\PycharmProjects\AppleHealthDashboard"
```

2) Installeer dependencies:

```powershell
python -m pip install -U pip
python -m pip install -e ".[dev]"
```

3) Start de dashboard:

```powershell
python -m streamlit run app.py
```

4) In de app:
- Upload `export.zip` of `export.xml`
- Klik **Import naar database**

## Reset / data verwijderen
In de app kun je lokaal opgeslagen data verwijderen via de knop **Delete local data**.
Dat verwijdert `health.db` en `./.tmp/`.

## Project layout
- `app.py` — Streamlit UI
- `apple_health_dashboard/ingest/` — streaming parsers + importer
- `apple_health_dashboard/storage/` — SQLite schema + read/write helpers
- `apple_health_dashboard/services/` — aggregaties (pandas)
- `tests/` — unit tests

## Development
Tests:

```powershell
python -m pytest
```

Lint:

```powershell
python -m ruff check .
```

## Troubleshooting
- **streamlit niet gevonden**: gebruik `python -m streamlit run app.py`
- **Import is traag**: grote exports kunnen enkele minuten duren (zeker bij 1e import)
- **Geen data zichtbaar**: klik eerst op **Import naar database** en daarna op refresh
