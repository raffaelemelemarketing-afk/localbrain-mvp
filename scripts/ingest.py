import os, json, asyncio
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from app.db import SessionLocal
from app.models import Item
from app.sources.crawlers import fetch_rss, fetch_html_list
from app.ranking import classify_and_score
from bs4 import BeautifulSoup

load_dotenv()

CITY_DEFAULT = os.getenv("CITY", "Fiumicino")

def strip_html(text: str) -> str:
    if not text:
        return ""
    return BeautifulSoup(text, "html.parser").get_text(separator=" ", strip=True)

async def ingest():
    db: Session = SessionLocal()
    # RSS
    with open("app/sources/rss_list.json","r") as f:
        rss_list = json.load(f)
    for feed in rss_list:
        url = feed["url"]
        city = feed.get("city", CITY_DEFAULT)
        try:
            items = await fetch_rss(url)
            for it in items:
                title = strip_html(it.get("title","")).strip()
                url = it.get("url","").strip()
                summary = strip_html(it.get("summary","")).strip()
                location = strip_html(it.get("location","")).strip()
                if location and location.lower() not in summary.lower():
                    summary = f"{summary} — {location}" if summary else location
                if not title or not url:
                    continue
                # Check duplicate
                exists = db.query(Item).filter(Item.url == url).first()
                if exists:
                    continue
                cls = classify_and_score(title, summary)
                row = Item(
                    source=feed["name"],
                    title=title,
                    url=url,
                    summary=summary[:1900],
                    category=cls["category"],
                    city=city,
                    published_at=datetime.utcnow(),
                    score=cls["score"]
                )
                db.add(row)
            db.commit()
            print(f"[OK] RSS: {feed['name']}")
        except Exception as e:
            print(f"[ERR] RSS {feed['name']}: {e}")

    # HTML rules
    with open("app/sources/html_rules.json","r") as f:
        html_rules = json.load(f)
    for rule in html_rules:
        try:
            items = await fetch_html_list(rule["url"], rule)
            for it in items:
                title = strip_html(it.get("title","")).strip()
                url = it.get("url","").strip()
                summary = strip_html(it.get("summary","")).strip()
                location = strip_html(it.get("location","")).strip()
                if location and location.lower() not in summary.lower():
                    summary = f"{summary} — {location}" if summary else location
                if not title or not url:
                    continue
                exists = db.query(Item).filter(Item.url == url).first()
                if exists:
                    continue
                cls = classify_and_score(title, summary)
                row = Item(
                    source=rule["name"],
                    title=title,
                    url=url,
                    summary=summary[:1900],
                    category=cls["category"],
                    city=rule.get("city", CITY_DEFAULT),
                    published_at=datetime.utcnow(),
                    score=cls["score"]
                )
                db.add(row)
            db.commit()
            print(f"[OK] HTML: {rule['name']}")
        except Exception as e:
            print(f"[ERR] HTML {rule['name']}: {e}")

if __name__ == "__main__":
    asyncio.run(ingest())
