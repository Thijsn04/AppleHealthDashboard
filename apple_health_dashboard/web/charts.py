from __future__ import annotations

import altair as alt
import pandas as pd

# Consistent colour palette
PRIMARY = "#2E7D6E"
SECONDARY = "#4CAF91"
ACCENT = "#FF6B6B"
MUTED = "#94A3B8"

SCHEME = "tealblues"


def _base_theme() -> dict:
    return {
        "config": {
            "background": "transparent",
            "axis": {"labelColor": "#12312B", "titleColor": "#12312B", "gridColor": "#E2EAE8"},
            "title": {"color": "#12312B"},
            "mark": {"color": PRIMARY},
        }
    }


# Register a custom theme
alt.themes.register("ahd", lambda: _base_theme())
alt.themes.enable("ahd")


def area_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    title: str = "",
    y_title: str = "",
    color: str = PRIMARY,
    height: int = 220,
    tooltip_extra: list[str] | None = None,
) -> alt.Chart:
    """A smooth area chart with a line overlay."""
    tooltip = [alt.Tooltip(x, title="Date"), alt.Tooltip(y, title=y_title or y, format=".1f")]
    if tooltip_extra:
        tooltip += [alt.Tooltip(c) for c in tooltip_extra]

    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:T", axis=alt.Axis(labelAngle=-30, title="")),
        y=alt.Y(f"{y}:Q", axis=alt.Axis(title=y_title or y)),
        tooltip=tooltip,
    )

    area = base.mark_area(
        line={"color": color, "strokeWidth": 2},
        color=alt.Gradient(
            gradient="linear",
            stops=[
                alt.GradientStop(color=color, offset=0),
                alt.GradientStop(color="rgba(255,255,255,0)", offset=1),
            ],
            x1=1,
            x2=1,
            y1=1,
            y2=0,
        ),
    )

    return (area).properties(title=title, height=height)


def line_chart(
    df: pd.DataFrame,
    x: str,
    y: str | list[str],
    *,
    title: str = "",
    y_title: str = "",
    height: int = 220,
    rolling_avg_days: int | None = None,
    show_trendline: bool = False,
) -> alt.Chart:
    """A line chart. Supports multiple y columns (via fold) or optional rolling average."""
    if isinstance(y, list):
        # Multiple series — use a safe value_name that won't clash with any existing column
        melted = df.melt(id_vars=[x], value_vars=y, var_name="metric", value_name="_val")
        chart = (
            alt.Chart(melted)
            .mark_line(strokeWidth=2)
            .encode(
                x=alt.X(f"{x}:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y("_val:Q", axis=alt.Axis(title=y_title)),
                color=alt.Color("metric:N"),
                tooltip=[
                    alt.Tooltip(f"{x}:T", title="Date"),
                    alt.Tooltip("metric:N"),
                    alt.Tooltip("_val:Q", format=".1f"),
                ],
            )
            .properties(title=title, height=height)
        )
        return chart

    # Single series, optionally with rolling average overlay
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:T", axis=alt.Axis(labelAngle=-30, title="")),
    )

    line = base.mark_line(color=PRIMARY, strokeWidth=2).encode(
        y=alt.Y(f"{y}:Q", axis=alt.Axis(title=y_title or y)),
        tooltip=[
            alt.Tooltip(f"{x}:T", title="Date"),
            alt.Tooltip(f"{y}:Q", title=y_title or y, format=".1f"),
        ],
    )

    layers: list[alt.Chart] = [line]

    if rolling_avg_days and len(df) > rolling_avg_days:
        roll_col = f"{y}_roll"
        df2 = df.copy()
        df2[roll_col] = df2[y].rolling(rolling_avg_days, min_periods=1).mean()
        roll_line = (
            alt.Chart(df2)
            .mark_line(color=ACCENT, strokeWidth=1.5, strokeDash=[4, 4])
            .encode(
                x=alt.X(f"{x}:T"),
                y=alt.Y(f"{roll_col}:Q"),
                tooltip=[
                    alt.Tooltip(f"{x}:T", title="Date"),
                    alt.Tooltip(f"{roll_col}:Q", title=f"{rolling_avg_days}d avg", format=".1f"),
                ],
            )
        )
        layers.append(roll_line)

    if show_trendline:
        # We need a numeric x for regression, but we use :T for datetime.
        # Altair handles datetime regression in newer versions, but we'll try it simply.
        trend = (
            alt.Chart(df)
            .transform_regression(x, y)
            .mark_line(color=ACCENT, strokeWidth=1.5, strokeDash=[2, 2])
            .encode(x=alt.X(f"{x}:T"), y=alt.Y(f"{y}:Q"))
        )
        layers.append(trend)

    return alt.layer(*layers).properties(title=title, height=height)


def bar_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    title: str = "",
    y_title: str = "",
    color: str = PRIMARY,
    height: int = 220,
    horizontal: bool = False,
) -> alt.Chart:
    """A bar chart."""
    if horizontal:
        chart = (
            alt.Chart(df)
            .mark_bar(color=color)
            .encode(
                y=alt.Y(f"{x}:N", sort="-x", axis=alt.Axis(title="")),
                x=alt.X(f"{y}:Q", axis=alt.Axis(title=y_title or y)),
                tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{y}:Q", format=".1f")],
            )
            .properties(title=title, height=max(height, len(df) * 24))
        )
    else:
        chart = (
            alt.Chart(df)
            .mark_bar(color=color)
            .encode(
                x=alt.X(f"{x}:T", axis=alt.Axis(labelAngle=-30, title="")),
                y=alt.Y(f"{y}:Q", axis=alt.Axis(title=y_title or y)),
                tooltip=[
                    alt.Tooltip(f"{x}:T", title="Date"),
                    alt.Tooltip(f"{y}:Q", format=".1f"),
                ],
            )
            .properties(title=title, height=height)
        )
    return chart


def stacked_bar_chart(
    df: pd.DataFrame,
    x: str,
    y_cols: list[str],
    *,
    title: str = "",
    y_title: str = "",
    height: int = 260,
) -> alt.Chart:
    """A stacked bar chart."""
    melted = df.melt(id_vars=[x], value_vars=y_cols, var_name="stage", value_name="hours")
    chart = (
        alt.Chart(melted)
        .mark_bar()
        .encode(
            x=alt.X(f"{x}:T", axis=alt.Axis(labelAngle=-30, title="")),
            y=alt.Y("hours:Q", stack="zero", axis=alt.Axis(title=y_title or "Hours")),
            color=alt.Color(
                "stage:N",
                scale=alt.Scale(scheme=SCHEME),
            ),
            tooltip=[
                alt.Tooltip(f"{x}:T", title="Date"),
                alt.Tooltip("stage:N"),
                alt.Tooltip("hours:Q", format=".2f"),
            ],
        )
        .properties(title=title, height=height)
    )
    return chart


def donut_chart(
    df: pd.DataFrame,
    theta: str,
    color: str,
    *,
    title: str = "",
    inner_radius: int = 60,
) -> alt.Chart:
    """A donut/pie chart."""
    chart = (
        alt.Chart(df)
        .mark_arc(innerRadius=inner_radius)
        .encode(
            theta=alt.Theta(f"{theta}:Q"),
            color=alt.Color(f"{color}:N", scale=alt.Scale(scheme=SCHEME)),
            tooltip=[alt.Tooltip(f"{color}:N"), alt.Tooltip(f"{theta}:Q", format=".1f")],
        )
        .properties(title=title)
    )
    return chart


def scatter_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    *,
    title: str = "",
    x_title: str = "",
    y_title: str = "",
    color_col: str | None = None,
    height: int = 300,
    show_trendline: bool = False,
) -> alt.Chart:
    """A scatter plot with optional color encoding."""
    enc: dict = {
        "x": alt.X(f"{x}:Q", axis=alt.Axis(title=x_title or x)),
        "y": alt.Y(f"{y}:Q", axis=alt.Axis(title=y_title or y)),
        "tooltip": [
            alt.Tooltip(f"{x}:Q", format=".1f"),
            alt.Tooltip(f"{y}:Q", format=".1f"),
        ],
    }
    if color_col:
        enc["color"] = alt.Color(f"{color_col}:N")
        enc["tooltip"].append(alt.Tooltip(f"{color_col}:N"))  # type: ignore[attr-defined]

    chart = (
        alt.Chart(df)
        .mark_circle(size=60, opacity=0.7)
        .encode(**enc)
    )
    layers = [chart]

    if show_trendline:
        trend = (
            alt.Chart(df)
            .transform_regression(x, y)
            .mark_line(color=ACCENT, strokeWidth=1.5, strokeDash=[2, 2])
            .encode(x=alt.X(f"{x}:Q"), y=alt.Y(f"{y}:Q"))
        )
        layers.append(trend)

    return alt.layer(*layers).properties(title=title, height=height)


def heatmap_chart(
    df: pd.DataFrame,
    x: str,
    y: str,
    color: str,
    *,
    title: str = "",
    height: int = 200,
    color_scheme: str = "greens",
) -> alt.Chart:
    """A calendar-style heatmap."""
    chart = (
        alt.Chart(df)
        .mark_rect()
        .encode(
            x=alt.X(f"{x}:O", axis=alt.Axis(title="")),
            y=alt.Y(f"{y}:O", axis=alt.Axis(title="")),
            color=alt.Color(
                f"{color}:Q",
                scale=alt.Scale(scheme=color_scheme),
                legend=alt.Legend(title=color),
            ),
            tooltip=[
                alt.Tooltip(f"{x}:O"),
                alt.Tooltip(f"{y}:O"),
                alt.Tooltip(f"{color}:Q", format=".0f"),
            ],
        )
        .properties(title=title, height=height)
    )
    return chart


def ring_gauge(value: float, goal: float, label: str, color: str = PRIMARY) -> alt.Chart:
    """A simple circular progress indicator using arc marks."""
    pct = min(value / goal, 1.0) if goal > 0 else 0.0

    bg = pd.DataFrame({"theta": [2 * 3.14159], "label": ["bg"]})
    fg = pd.DataFrame({"theta": [pct * 2 * 3.14159], "label": [label]})

    bg_arc = (
        alt.Chart(bg)
        .mark_arc(innerRadius=45, outerRadius=60, color="#E2EAE8")
        .encode(theta=alt.Theta("theta:Q"))
    )

    fg_arc = (
        alt.Chart(fg)
        .mark_arc(innerRadius=45, outerRadius=60, color=color)
        .encode(theta=alt.Theta("theta:Q"))
    )

    text = (
        alt.Chart(pd.DataFrame({"v": [f"{int(pct * 100)}%"], "x": [0], "y": [0]}))
        .mark_text(fontSize=16, fontWeight="bold", color=color)
        .encode(x=alt.X("x:Q", axis=None), y=alt.Y("y:Q", axis=None), text="v:N")
    )

    return alt.layer(bg_arc, fg_arc, text).properties(title=label)
