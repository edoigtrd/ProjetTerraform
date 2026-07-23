"""Scaleway Serverless Function backing the Streamlit dashboard.

`http_event.py` (next to this file) gives you method/path/route/body parsing
that works across Scaleway's HTTP event shapes. This function is the only
thing allowed to talk to the database. It also owns all the aggregation
(category counts, word-count buckets, emoji counts) so the dashboard only
ever pulls small, pre-aggregated JSON instead of raw rows.
"""

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime

from http_event import match_route, get_method, get_query_params
from peewee import Model, AutoField, CharField, TextField, DateTimeField, fn
from playhouse.db_url import connect


class Post(Model):
    id = AutoField()
    author_handle = CharField()
    text = TextField()
    category = CharField()
    posted_at = DateTimeField()


WORD_BUCKETS = [
    (0, 10, "0-10"),
    (10, 20, "10-20"),
    (20, 30, "20-30"),
    (30, 50, "30-50"),
    (50, 75, "50-75"),
    (75, 100, "75-100"),
    (100, None, "100+"),
]

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"
    "\U00002600-\U000027BF"
    "\U0001F1E6-\U0001F1FF"
    "\U00002B00-\U00002BFF"
    "]"
)

# Kept generous (more than the ~5 the dashboard displays) so folding
# low-volume categories together client-side doesn't lose their top emojis.
TOP_EMOJIS_PER_CATEGORY = 8


def word_bucket(word_count: int) -> str:
    for lo, hi, label in WORD_BUCKETS:
        if word_count >= lo and (hi is None or word_count < hi):
            return label
    return WORD_BUCKETS[-1][2]


def with_db(fn_):
    def wrapper(*args, **kwargs):
        db = connect(os.environ["DATABASE_URL"])
        db.bind([Post])
        try:
            return fn_(*args, **kwargs)
        finally:
            db.close()

    return wrapper


def parse_dt(value):
    return datetime.fromisoformat(value) if value else None


@with_db
def get_bounds() -> dict:
    lo, hi = Post.select(fn.MIN(Post.posted_at), fn.MAX(Post.posted_at)).scalar(as_tuple=True)
    return {
        "min": lo.isoformat() if lo else None,
        "max": hi.isoformat() if hi else None,
    }


@with_db
def get_stats(since, until) -> dict:
    query = Post.select(Post.category, Post.text)
    if since:
        query = query.where(Post.posted_at >= since)
    if until:
        query = query.where(Post.posted_at <= until)

    category_counts = Counter()
    bucket_counts = Counter()
    emoji_counts = defaultdict(Counter)

    for post in query:
        category_counts[post.category] += 1
        bucket_counts[(word_bucket(len(post.text.split())), post.category)] += 1
        for emoji in EMOJI_PATTERN.findall(post.text):
            emoji_counts[post.category][emoji] += 1

    top_emojis = [
        {"category": category, "emoji": emoji, "count": count}
        for category, counts in emoji_counts.items()
        for emoji, count in counts.most_common(TOP_EMOJIS_PER_CATEGORY)
    ]

    return {
        "count": sum(category_counts.values()),
        "categories": dict(category_counts),
        "word_buckets": [
            {"bucket": bucket, "category": category, "count": count}
            for (bucket, category), count in bucket_counts.items()
        ],
        "top_emojis": top_emojis,
    }


def handle(evt, ctx):
    method = get_method(evt)
    path = match_route(evt)

    match (method, path):
        case ("GET", "/"):
            return {"statusCode": 200, "body": "Hello, world!"}
        case ("GET", "/stats/bounds"):
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(get_bounds()),
            }
        case ("GET", "/stats"):
            params = get_query_params(evt)
            since = parse_dt(params.get("since"))
            until = parse_dt(params.get("until"))
            return {
                "statusCode": 200,
                "headers": {"Content-Type": "application/json"},
                "body": json.dumps(get_stats(since, until)),
            }
        case _:
            return {"statusCode": 404, "body": f"{method} {path}"}
