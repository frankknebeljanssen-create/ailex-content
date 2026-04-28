"""
Highlights pipeline (Mon/Wed/Fri).

Single-call architecture: web_search across the open web, Claude returns JSON
list with headline + 50-100w teaser + URL.

Resilient against tier-1 rate limits via retry-with-wait on RateLimitError.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from anthropic import Anthropic

sys.path.insert(0, str(Path(__file__).resolve().parent))
from config import (
    MODEL_RESEARCH, HIGHLIGHTS_TARGET_COUNT, HIGHLIGHTS_TEASER_WORDS,
    DATA_DIR, HIGHLIGHTS_FILE,
)

DATA_PATH = Path(DATA_DIR) / HIGHLIGHTS_FILE

RATELIMIT_WAIT_SECONDS = 60
RATELIMIT_MAX_RETRIES = 5


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


def call_with_retry(fn, label="api"):
    last_err = None
    for attempt in range(1, RATELIMIT_MAX_RETRIES + 1):
        try:
            return fn()
        except anthropic.RateLimitError as e:
            last_err = e
            print(f"    ⏳ rate limit on {label}, waiting {RATELIMIT_WAIT_SECONDS}s (attempt {attempt}/{RATELIMIT_MAX_RETRIES})")
            time.sleep(RATELIMIT_WAIT_SECONDS)
    raise last_err


def discover_and_summarize(client, cached_urls):
    word_min, word_max = HIGHLIGHTS_TEASER_WORDS
    today_de = datetime.now().strftime("%d.%m.%Y")
    avoid = "\n".join(f"- {u}" for u in cached_urls) if cached_urls else "(keine)"

    prompt = f"""Heute ist der {today_de}. Recherchiere die {HIGHLIGHTS_TARGET_COUNT} brandheißesten Diskussionsthemen aus Deutschland zum Thema Legal AI / KI in der Justiz / KI im Anwaltsberuf.

Anders als reine Tagesnachrichten geht es hier um Themen, die strukturell heiß diskutiert werden — einzelne wegweisende Urteile, Gesetzesvorhaben, Branchen-Trends, andauernde Konflikte oder Kontroversen. Beispiele dafür wären (NICHT als Vorlage, nur zur Orientierung):
- AI-Act-Compliance-Welle Richtung 2.8.2026
- Urheberrecht & KI-Training (LAION/BGH-Termin, GEMA vs. OpenAI)
- biometrische Erkennung im öffentlichen Raum
- Halluzinations-Urteile gegen Anwält:innen
- Embedded Agentic AI in Großkanzleien
- DSGVO-Schadensersatz nach BAG-Workday-Urteil

Recherchiere offen im Web. Bevorzuge deutsche Fachmedien (LTO, Beck-aktuell, Heise, Netzpolitik, Anwaltsblatt, Bundestag, EUR-Lex, BGH-Pressemitteilungen).

Vermeide Duplikate zu diesen bereits gepflegten Themen:
{avoid}

Nutze zuerst das web_search Tool zur Recherche.
Rufe DANACH das Tool `submit_highlights` mit deinen {HIGHLIGHTS_TARGET_COUNT} Funden auf.

Anforderungen pro Item:
- headline: Kurze prägnante Überschrift, 4-8 Wörter
- teaser: {word_min}–{word_max} Wörter Anriss in Du-Form, sachlich, mit konkreten Bezügen wo möglich (Datum, Norm, Aktenzeichen)
- url: Link zur weiterführenden Quelle

Du-Form, sachlich, ohne Hype, ohne Panikmache."""

    submit_tool = {
        "name": "submit_highlights",
        "description": "Reicht die Liste der recherchierten Schlaglichter ein.",
        "input_schema": {
            "type": "object",
            "properties": {
                "highlights": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "headline": {"type": "string"},
                            "teaser":   {"type": "string"},
                            "url":      {"type": "string"},
                        },
                        "required": ["headline", "teaser", "url"],
                    },
                }
            },
            "required": ["highlights"],
        },
    }

    def call():
        return client.messages.create(
            model=MODEL_RESEARCH,
            max_tokens=6000,
            tools=[
                {
                    "type": "web_search_20250305",
                    "name": "web_search",
                    "max_uses": 12,
                },
                submit_tool,
            ],
            messages=[{"role": "user", "content": prompt}],
        )
    response = call_with_retry(call, label="highlights research")

    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "submit_highlights":
            return block.input.get("highlights", [])

    print("  WARNING: Claude returned no submit_highlights tool call")
    return []


def main():
    client = Anthropic()
    cache = load_cache()
    cached_by_url = {it["url"]: it for it in cache.get("items", []) if it.get("url")}
    print(f"Cache: {len(cached_by_url)} items")

    print("Researching highlights via web_search...")
    try:
        results = discover_and_summarize(client, list(cached_by_url.keys()))
    except Exception as e:
        print(f"  ERROR: {e}")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    items = []
    for i, r in enumerate(results[:HIGHLIGHTS_TARGET_COUNT]):
        url = (r.get("url") or "").strip()
        if url in cached_by_url:
            print(f"  ✓ cached: {r.get('headline', '')[:60]}")
            items.append(cached_by_url[url])
            continue
        print(f"  + fresh: {r.get('headline', '')[:60]}")
        items.append({
            "id": f"hl-{today}-{i + 1:02d}",
            "headline": r.get("headline", ""),
            "teaser": r.get("teaser", ""),
            "url": url,
        })

    save(items)
    print(f"\nWrote {len(items)} items → {DATA_PATH}")


if __name__ == "__main__":
    main()
