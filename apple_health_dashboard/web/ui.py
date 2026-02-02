from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Brand:
    app_name: str = "Apple Health Dashboard"
    tagline: str = "Calm overview. Smart insights. Everything local."


DEFAULT_BRAND = Brand()


def apply_base_ui(brand: Brand = DEFAULT_BRAND) -> None:
    """Apply consistent branding/layout.

    Streamlit theming is mostly controlled via .streamlit/config.toml.
    This function focuses on layout, copy, and a tiny bit of CSS for spacing.
    """
    st.set_page_config(page_title=brand.app_name, layout="wide")

    st.markdown(
        """
<style>
.block-container { padding-top: 2rem; padding-bottom: 2rem; }

h1, h2, h3 { letter-spacing: -0.01em; }

/* Softer, more app-like cards */
.ahd-card {
  background: rgba(46, 125, 110, 0.06);
  border: 1px solid rgba(46, 125, 110, 0.18);
  padding: 14px 16px;
  border-radius: 14px;
}
.ahd-muted { opacity: 0.9; }

/* Calm separators */
hr { margin: 1.2rem 0; opacity: 0.25; }

/* Make dataframes look a bit more native */
[data-testid="stDataFrame"] { border-radius: 12px; }
</style>
""",
        unsafe_allow_html=True,
    )

    st.title(brand.app_name)
    st.caption(brand.tagline)


def info_card(title: str, body: str) -> None:
    st.markdown(
        f"""
<div class="ahd-card">
  <div style="font-weight: 650; margin-bottom: 6px;">{title}</div>
  <div class="ahd-muted">{body}</div>
</div>
""",
        unsafe_allow_html=True,
    )


def stat_row(items: list[tuple[str, str]]) -> None:
    """Render a compact row of key/value stats."""
    cols = st.columns(len(items))
    for col, (k, v) in zip(cols, items, strict=False):
        with col:
            st.markdown(
                f"""
<div class="ahd-card">
  <div style="font-size: 0.85rem; opacity: 0.76;">{k}</div>
  <div style="font-size: 1.1rem; font-weight: 650;">{v}</div>
</div>
""",
                unsafe_allow_html=True,
            )
