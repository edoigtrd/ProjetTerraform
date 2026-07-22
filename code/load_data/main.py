import time
from datetime import datetime, timedelta, timezone
from atproto import Client
import dotenv
import os
import psycopg2
from peewee import Model, PostgresqlDatabase, CharField, DateTimeField, TextField, AutoField
from openai import OpenAI
import re
from playhouse.db_url import connect


dotenv.load_dotenv()

HANDLE = os.getenv("BSKY_APP_NAME")
APP_PASSWORD = os.getenv("BSKY_APP_PASSWORD")

TARGET_COUNT = 500
QUERY = "iphone"
SINCE = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()

CANDIDATE_LABELS = [
    "product news or rumor",
    "advertisement or deal",
    "complaint or criticism",
    "personal anecdote",
    "photography or creative content",
    "humor or shitpost",
    "competitor comparison",
    "technical bug or support",
    "neutral or informational",
    "unrelated to apple iphone"
]

client = OpenAI(
    base_url=os.getenv("OPENAI_API_ENDPOINT"),
    api_key=os.getenv("OPENAI_API_KEY")
)

class Post(Model):
    id = AutoField()
    author_handle = CharField()
    text = TextField()
    category = CharField()
    posted_at = DateTimeField()


def fetch_posts():
    client = Client()
    client.login(HANDLE, APP_PASSWORD)

    posts = []
    cursor = None

    while len(posts) < TARGET_COUNT:
        result = client.app.bsky.feed.search_posts(
            params={"q": QUERY, "since": SINCE, "limit": 100, "cursor": cursor}
        )
        if not result.posts:
            break

        posts.extend(result.posts)
        cursor = result.cursor
        if not cursor:
            break

        time.sleep(0.5)

    return posts[:TARGET_COUNT]


def classify_with_openai(text):
    labels_prompt = "\n".join(f"{i}: {label}" for i, label in enumerate(CANDIDATE_LABELS))

    response = client.chat.completions.create(
        model="groq/openai/gpt-oss-20b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that classifies text into categories. Only return the category number, nothing else. No markdown, no fences, no explanation, just the digit."},
            {"role": "user", "content": f"Categories:\n{labels_prompt}\n\nClassify this text into one of the categories above. Text: {text}"}
        ]
    )
    raw = response.choices[0].message.content.strip()

    match = re.search(r"\d+", raw)
    if not match:
        return "unknown"

    idx = int(match.group())
    if 0 <= idx < len(CANDIDATE_LABELS):
        return CANDIDATE_LABELS[idx]
    return "unknown"


if __name__ == "__main__":
    db = connect(os.getenv("DATABASE_URL"))
    db.bind([Post])
    db.create_tables([Post])
    for post in fetch_posts():
        category = classify_with_openai(post.text)
        Post.create(
            author_handle=post.author.handle,
            text=post.text,
            category=category,
            posted_at=datetime.fromisoformat(post.record.created_at)
        )
    
