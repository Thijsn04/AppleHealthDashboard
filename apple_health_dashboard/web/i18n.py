from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Copy:
    # App
    app_tagline: str

    # Sidebar
    sidebar_import_title: str
    sidebar_upload_help: str
    sidebar_local_caption: str
    sidebar_tips_title: str
    sidebar_delete_local_title: str
    sidebar_delete_local_body: str
    sidebar_delete_local_confirm: str
    sidebar_delete_local_button: str

    # Buttons
    button_import: str
    button_refresh: str

    # Main cards
    card_privacy_title: str
    card_privacy_body: str
    card_scale_title: str
    card_scale_body: str
    card_insight_title: str
    card_insight_body: str

    # Tabs
    tab_dashboard: str
    tab_explore: str
    tab_workouts: str
    tab_rings: str
    tab_sleep: str
    tab_metadata: str

    # Filters
    filters_header: str
    filter_metric: str
    filter_date_range: str
    filter_custom_date: str
    filter_select_dates: str


COPY_EN = Copy(
    app_tagline="Calm overview. Smart insights. Everything local.",
    sidebar_import_title="Import",
    sidebar_upload_help="Upload `export.xml` or `export.zip` from Apple Health.",
    sidebar_local_caption="Everything stays on your computer.",
    sidebar_tips_title="Tips",
    sidebar_delete_local_title="Manage local data",
    sidebar_delete_local_body="Delete all locally stored data (database + temporary uploads).",
    sidebar_delete_local_confirm="I understand this deletes everything locally",
    sidebar_delete_local_button="Delete local data",
    button_import="Import to database",
    button_refresh="Refresh",
    card_privacy_title="Privacy-first",
    card_privacy_body="Your export is never uploaded to a cloud. We process everything locally.",
    card_scale_title="Scalable",
    card_scale_body="We import into SQLite so reloads stay fast.",
    card_insight_title="Explore",
    card_insight_body="Pick a metric and browse workouts, rings, sleep and raw data.",
    tab_dashboard="Dashboard",
    tab_explore="Explore",
    tab_workouts="Workouts",
    tab_rings="Rings",
    tab_sleep="Sleep",
    tab_metadata="Metadata",
    filters_header="Filters",
    filter_metric="Metric",
    filter_date_range="Date range",
    filter_custom_date="Custom date range",
    filter_select_dates="Select dates",
)

COPY_NL = Copy(
    app_tagline="Rustig overzicht. Slimme inzichten. Alles lokaal.",
    sidebar_import_title="Import",
    sidebar_upload_help="Upload `export.xml` of `export.zip` vanuit Apple Gezondheid.",
    sidebar_local_caption="Alles blijft lokaal op je computer.",
    sidebar_tips_title="Tips",
    sidebar_delete_local_title="Local data beheren",
    sidebar_delete_local_body=(
        "Verwijder alle lokaal opgeslagen data (database + tijdelijke uploads)."
    ),
    sidebar_delete_local_confirm="Ik snap dat dit alles lokaal verwijdert",
    sidebar_delete_local_button="Delete local data",
    button_import="Import naar database",
    button_refresh="Refresh",
    card_privacy_title="Privacy-first",
    card_privacy_body="Je export wordt niet geüpload naar een cloud. We verwerken alles lokaal.",
    card_scale_title="Schaalbaar",
    card_scale_body="We importeren naar SQLite zodat reloads snel blijven.",
    card_insight_title="Inzicht",
    card_insight_body="Kies een metric en bekijk workouts, rings, slaap en ruwe data.",
    tab_dashboard="Dashboard",
    tab_explore="Explore",
    tab_workouts="Workouts",
    tab_rings="Rings",
    tab_sleep="Sleep",
    tab_metadata="Metadata",
    filters_header="Filters",
    filter_metric="Metric",
    filter_date_range="Date range",
    filter_custom_date="Custom date range",
    filter_select_dates="Select dates",
)


def get_copy(lang: str) -> Copy:
    key = (lang or "en").lower()
    if key.startswith("nl"):
        return COPY_NL
    return COPY_EN
