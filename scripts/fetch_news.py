"""
News pipeline (1x daily).

Flow:
1. Load existing news.json as cache (drop entries older than NEWS_MAX_AGE_DAYS)
2. Discovery call: ask Claude with web_search restricted to NEWS_SOURCES domains
   to return JSON list of {url, headline, date, source} candidates.
3. For each candidate URL not already in cache:
   - fetch article HTML with requests/BeautifulSoup (cheap, no API tokens)
   - send extracted text to Claude for a 200-400 word German summary in markdown
4. Merge cache + new items, sort by date desc, keep top NEWS_TARGET_COUNT.
5. Write data/news.json.
"""

import json
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from anthropic import Anthropic

# Path setup so we can import config from this script's directory
sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    MODEL_RESEARCH, MODEL_SUMMARY, SUMMARY_SLEEP_SECONDS,
    NEWS_SOURCES, NEWS_TARGET_COUNT,
    NEWS_SUMMARY_WORDS, NEWS_MAX_AGE_DAYS,
    DATA_DIR, NEWS_FILE,
)

DATA_PATH = Path(DATA_DIR) / NEWS_FILE


# === IO ===
def load_cache():
    if DATA_PATH.exists():
        try:
            return json.loads(DATA_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {"generated_at": "", "items": []}


def save(items):
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    out = {
        "generated_at": datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds"),
        "items": items,
    }
    DATA_PATH.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


# === LLM-Discovery ===
def discover_candidates(client):
    """Use web_search to find candidate articles. Returns list of dicts."""
    domains = [s["domain"] for s in NEWS_SOURCES]
    sources_text = ", ".join(s["name"] for s in NEWS_SOURCES)
    today_iso = datetime.now().strftime("%Y-%m-%d")
    today_de = datetime.now().strftime("%d.%m.%Y")

    prompt = f"""Heute ist der {today_de}. Recherchiere die wichtigsten aktuellen Nachrichten aus Deutschland zum Thema Legal AI / KI in der Justiz / KI im Anwaltsberuf.

Suche AUSSCHLIESSLICH auf diesen deutschen Quellen: {sources_text}

Themenfokus:
- EU AI Act (Stand der Umsetzung, Bußgelder, Compliance)
- Urheberrecht und KI (LAION, GEMA, OpenAI, generative KI)
- DSGVO und KI (Workday, Schadensersatz, Bewerbungs-KI)
- Justiz-KI (OLGA, Frauke, FraPOL)
- Halluzinationen in der Anwaltspraxis
- Berufsrecht Anwält:innen (BRAO, Verschwiegenheit, § 203 StGB)
- AI-Act-Umsetzungsgesetze im Bundestag

Finde die {NEWS_TARGET_COUNT} relevantesten Artikel der letzten 1-10 Tage.

WICHTIG: Antworte AUSSCHLIESSLICH mit einem JSON-Array, ohne Code-Fence, ohne Einleitung. Format:

[
  {{"url": "https://...", "headline": "Kurze prägnante Headline", "date": "YYYY-MM-DD", "source": "LTO"}},
  ...
]

Wenn das Datum unbekannt ist, nutze {today_iso}."""

    response = client.messages.create(
        model=MODEL_RESEARCH,
        max_tokens=4000,
        tools=[{
            "type": "web_search_20250305",
            "name": "web_search",
            "max_uses": 8,
            "allowed_domains": domains,
        }],
        messages=[{"role": "user", "content": prompt}],
    )

    text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", None) == "text").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*\n?", "", text)
        text = re.sub(r"\n?```\s*$", "", text)
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        text = text[start:end + 1]
    return json.loads(text)


# === Article fetching (cheap, no API tokens) ===
def fetch_article_text(url):
    headers = {
        "User-Agent": ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"),
        "Accept-Language": "de-DE,de;q=0.9,en;q=0.5",
    }
    r = requests.get(url, headers=headers, timeout=30)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "iframe"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body
    text = main.get_text("\n", strip=True) if main else ""
    # Collapse multiple newlines
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text[:5000]


# === LLM Summarize ===
def summarize(client, candidate, article_text):
    word_min, word_max = NEWS_SUMMARY_WORDS
    prompt = f"""Lies den folgenden Artikel von {candidate['source']} und fasse ihn für deutsche Anwält:innen zusammen.

Artikel-Headline: {candidate['headline']}

Artikel-Text:
\"\"\"
{article_text}
\"\"\"

Anforderungen:
- {word_min}–{word_max} Wörter
- Sachlich, ohne Hype, ohne Panikmache, ohne Werbung
- Du-Form (Anwält:innen direkt ansprechen)
- 2–3 Markdown-Zwischenüberschriften (z.B. ## Hintergrund, ## Was es bedeutet, ## Praxis-Hinweis — passend wählen)
- Konkrete juristische Verortung (Norm-Zitate, Aktenzeichen wenn vorhanden)
- KEINE Quelle oder Link am Ende — die App zeigt das separat
- KEINE Einleitung wie „Hier ist die Zusammenfassung:" — beginne direkt mit der ersten ##-Überschrift

Antworte AUSSCHLIESSLICH mit dem Markdown-Text."""

    response = client.messages.create(
        model=MODEL_SUMMARY,
        max_tokens=1500,
        messages=[{"role": "user", "content": prompt}],
    )
    text = "".join(getattr(b, "text", "") for b in response.content if getattr(b, "type", None) == "text")
    return text.strip()


# === Date helper ===
def _parse_date(s):
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return datetime(1970, 1, 1).date()


# === Main ===
def main():
    client = Anthropic()
    cache = load_cache()
    cached_by_url = {item["source_url"]: item for item in cache.get("items", []) if "source_url" in item}

    # Drop entries older than NEWS_MAX_AGE_DAYS
    cutoff = (datetime.now() - timedelta(days=NEWS_MAX_AGE_DAYS)).date()
    cached_by_url = {
        url: it for url, it in cached_by_url.items()
        if _parse_date(it.get("date")) >= cutoff
    }
    print(f"Cache: {len(cached_by_url)} valid items (within {NEWS_MAX_AGE_DAYS}d)")

    print("Discovering candidates via web_search...")
    try:
        candidates = discover_candidates(client)
    except Exception as e:
        print(f"  ERROR during discovery: {e}")
        # Keep cache as-is
        save(list(cached_by_url.values())[:NEWS_TARGET_COUNT])
        return

    print(f"Found {len(candidates)} candidate(s)")

    items = []
    fresh_count = 0
    for cand in candidates[:NEWS_TARGET_COUNT * 2]:
        if len(items) >= NEWS_TARGET_COUNT:
            break
        url = (cand.get("url") or "").strip()
        if not url or not url.startswith("http"):
            continue
        if url in cached_by_url:
            print(f"  ✓ cached: {cand.get('headline', '')[:65]}")
            items.append(cached_by_url[url])
            continue
        # Fresh item — throttle to respect rate limits
        if fresh_count > 0:
            print(f"    ⏱  sleeping {SUMMARY_SLEEP_SECONDS}s (rate-limit cushion)")
            time.sleep(SUMMARY_SLEEP_SECONDS)
        print(f"  → fetching: {cand.get('headline', '')[:65]}")
        try:
            text = fetch_article_text(url)
            if len(text) < 200:
                print(f"    skipping (article text too short: {len(text)} chars)")
                continue
            summary = summarize(client, cand, text)
            items.append({
                "id": f"news-{cand['date']}-{len(items) + 1:02d}",
                "date": cand["date"],
                "source": cand["source"],
                "source_url": url,
                "headline": cand["headline"],
                "summary_md": summary,
            })
            fresh_count += 1
        except requests.RequestException as e:
            print(f"    fetch error: {e}")
        except Exception as e:
            print(f"    error: {e}")

    items.sort(key=lambda x: x.get("date", ""), reverse=True)
    items = items[:NEWS_TARGET_COUNT]

    save(items)
    print(f"\nWrote {len(items)} items → {DATA_PATH}")


if __name__ == "__main__":
    main()
