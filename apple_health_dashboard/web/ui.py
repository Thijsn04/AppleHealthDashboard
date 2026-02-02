from __future__ import annotations

from dataclasses import dataclass

import streamlit as st


@dataclass(frozen=True)
class Brand:
    app_name: str = "Apple Health Dashboard"
    tagline: str = "Rustig overzicht. Slimme inzichten. Alles lokaal."


DEFAULT_BRAND = Brand()


def apply_base_ui(brand: Brand = DEFAULT_BRAND) -> None:
    """Apply consistent branding/layout.

    Streamlit theming is mostly controlled via .streamlit/config.toml.
    This function focuses on layout, copy, and a tiny bit of CSS for spacing.
    """
    st.set_page_config(page_title=brand.app_name, layout="wide")

    # Minimal CSS tweaks (keep it subtle and maintainable)
    st.markdown(
        """
<style>
/* Slightly soften default spacing and make headers feel calmer */
.block-container { padding-top: 2rem; padding-bottom: 2rem; }
h1, h2, h3 { letter-spacing: -0.01em; }
/* Make dataframe font a bit easier on the eyes */
[data-testid="stDataFrame"] { border-radius: 12px; }
</style>
""",
        unsafe_allow_html=True,
    )

    st.title(brand.app_name)
    st.caption(brand.tagline)


def info_card(title: str, body: str) -> None:
    """A small reusable info block."""
    st.markdown(
        f"""
<div style="background: rgba(46,125,110,0.06); padding: 14px 16px; border-radius: 14px;">
  <div style="font-weight: 600; margin-bottom: 6px;">{title}</div>
  <div style="opacity: 0.9;">{body}</div>
</div>
""",
        unsafe_allow_html=True,
    )
