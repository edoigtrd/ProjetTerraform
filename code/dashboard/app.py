"""Streamlit dashboard for the Bluesky "iphone" posts dataset.

All data comes from the Scaleway Serverless Function's `/stats*` routes.
The function is the only thing that talks to the database, and it also does
all the heavy lifting (filtering by date, counting categories, bucketing by
word count, counting emojis) so this app only ever pulls small, already
aggregated JSON - never the raw post rows.
"""

import os
from collections import defaultdict
from datetime import datetime

import pandas as pd
import plotly.express as px
import requests
import streamlit as st

FUNCTION_URL = os.environ.get("FUNCTION_URL", "http://localhost:8080").rstrip("/")

# Fixed categorical order (never cycled) - see code/dashboard/consigne.txt.
CATEGORY_PALETTE = [
    "#2a78d6",  # blue
    "#eb6834",  # orange
    "#1baf7a",  # aqua
    "#eda100",  # yellow
    "#e87ba4",  # magenta
    "#008300",  # green
    "#4a3aa7",  # violet
    "#e34948",  # red
]
OTHER_COLOR = "#898781"  # muted ink, for categories folded into "autre"
MAX_CATEGORIES = len(CATEGORY_PALETTE)
WORD_BUCKET_ORDER = ["0-10", "10-20", "20-30", "30-50", "50-75", "75-100", "100+"]

st.set_page_config(page_title="Bluesky iPhone posts", layout="wide")


@st.cache_data(ttl=300)
def load_bounds():
    resp = requests.get(f"{FUNCTION_URL}/stats/bounds", timeout=30)
    resp.raise_for_status()
    data = resp.json()
    if not data["min"] or not data["max"]:
        return None, None
    return datetime.fromisoformat(data["min"]), datetime.fromisoformat(data["max"])


@st.cache_data(ttl=60)
def load_stats(since: datetime, until: datetime) -> dict:
    resp = requests.get(
        f"{FUNCTION_URL}/stats",
        params={"since": since.isoformat(), "until": until.isoformat()},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def top_categories(category_counts: dict) -> set:
    return set(sorted(category_counts, key=category_counts.get, reverse=True)[:MAX_CATEGORIES])


def display_name(category: str, keep: set) -> str:
    return category if category in keep else "autre"


def color_map_for(categories) -> dict:
    colors = {}
    palette = iter(CATEGORY_PALETTE)
    for cat in categories:
        colors[cat] = OTHER_COLOR if cat == "autre" else next(palette, OTHER_COLOR)
    return colors


st.title("Bluesky - posts iPhone")

try:
    min_date, max_date = load_bounds()
except requests.RequestException as exc:
    st.error(f"Impossible de contacter la fonction ({FUNCTION_URL}) : {exc}")
    st.stop()

if min_date is None:
    st.info("Pas encore de données. Le job de collecte n'a peut-être pas encore tourné.")
    st.stop()

if min_date == max_date:
    st.warning("Une seule date disponible pour le moment, la fenêtre ne peut pas être ajustée.")
    window = (min_date, max_date)
else:
    window = st.slider(
        "Période",
        min_value=min_date,
        max_value=max_date,
        value=(min_date, max_date),
    )

try:
    stats = load_stats(window[0], window[1])
except requests.RequestException as exc:
    st.error(f"Impossible de récupérer les statistiques ({FUNCTION_URL}) : {exc}")
    st.stop()

st.caption(f"{stats['count']} posts entre {window[0]:%d/%m %H:%M} et {window[1]:%d/%m %H:%M}")

if stats["count"] == 0:
    st.info("Aucun post sur la période sélectionnée.")
    st.stop()

keep = top_categories(stats["categories"])

category_counts = defaultdict(int)
for category, count in stats["categories"].items():
    category_counts[display_name(category, keep)] += count
category_order = sorted(category_counts, key=category_counts.get, reverse=True)
color_map = color_map_for(category_order)

col1, col2 = st.columns(2)

with col1:
    st.subheader("Types de posts sur la période")
    pie_df = pd.DataFrame(
        {"category": list(category_counts.keys()), "count": list(category_counts.values())}
    )
    fig_pie = px.pie(
        pie_df,
        names="category",
        values="count",
        color="category",
        color_discrete_map=color_map,
        category_orders={"category": category_order},
        hole=0.4,
    )
    fig_pie.update_traces(textposition="inside", textinfo="percent+label")
    st.plotly_chart(fig_pie, use_container_width=True)

with col2:
    st.subheader("Types de posts par longueur (nombre de mots)")
    bucket_counts = defaultdict(int)
    for row in stats["word_buckets"]:
        bucket_counts[(row["bucket"], display_name(row["category"], keep))] += row["count"]
    bar_df = pd.DataFrame(
        [
            {"word_bucket": bucket, "category": category, "count": count}
            for (bucket, category), count in bucket_counts.items()
        ]
    )
    fig_bar = px.bar(
        bar_df,
        x="word_bucket",
        y="count",
        color="category",
        color_discrete_map=color_map,
        category_orders={"word_bucket": WORD_BUCKET_ORDER, "category": category_order},
    )
    fig_bar.update_layout(
        barmode="stack",
        xaxis_title="Nombre de mots",
        yaxis_title="Nombre de posts",
        legend_title="Type de post",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

st.subheader("Emojis préférés par type de post")

emoji_counts = defaultdict(lambda: defaultdict(int))
for row in stats["top_emojis"]:
    emoji_counts[display_name(row["category"], keep)][row["emoji"]] += row["count"]

emoji_rows = []
for category, counts in emoji_counts.items():
    for emoji, count in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:5]:
        emoji_rows.append({"category": category, "emoji": emoji, "count": count})

if not emoji_rows:
    st.info("Aucun emoji détecté sur la période sélectionnée.")
else:
    emoji_df = pd.DataFrame(emoji_rows)
    # Magnitude within each post type, not identity across types, so this
    # uses a single sequential hue rather than the categorical palette.
    fig_emoji = px.bar(
        emoji_df,
        x="count",
        y="emoji",
        facet_col="category",
        facet_col_wrap=4,
        orientation="h",
        color_discrete_sequence=[CATEGORY_PALETTE[0]],
        category_orders={"category": category_order},
    )
    fig_emoji.update_yaxes(matches=None, categoryorder="total ascending")
    fig_emoji.for_each_annotation(lambda a: a.update(text=a.text.split("=")[-1]))
    n_rows = -(-len(category_order) // 4)  # ceil division
    fig_emoji.update_layout(showlegend=False, margin=dict(t=60), height=220 * n_rows + 60)
    st.plotly_chart(fig_emoji, use_container_width=True)
