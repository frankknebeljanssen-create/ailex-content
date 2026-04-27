# AiLex Content Pipeline

Automatisierte Recherche und Aufbereitung von Legal-AI-News (Deutschland) für die AiLex PWA.

## Was das Repo macht

Zwei GitHub-Action-Cronjobs scannen kuratierte deutsche Quellen und schreiben zwei JSON-Dateien:

- **`data/news.json`** — 8 tagesaktuelle News, je 200–400 Wörter aufbereitet, mit Original-Link.
  **Cron: 1× täglich, 07:00 Berlin**.
- **`data/highlights.json`** — 6 brandheiße Diskussionsthemen, je 50–100 Wörter Anriss.
  **Cron: Mo/Mi/Fr 06:00 Berlin**.

Die AiLex-App fetched diese JSONs direkt von `raw.githubusercontent.com` — keine eigene Server-Infrastruktur nötig.

## Cache-Strategie

Beide Skripte deduplizieren über die Original-URL:

- News: Artikel, die bereits in `news.json` stehen, werden **nicht** erneut zusammengefasst (Kostenersparnis).
  Neu sind nur Artikel, deren `source_url` noch nicht im File steht.
- Highlights: gleiche Logik, deduplizieren über `url` oder `headline`-Hash.

Damit kostet ein Run nur dann nennenswert API-Tokens, wenn tatsächlich neue Artikel gefunden wurden.

## Lokaler Test

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python scripts/fetch_news.py
python scripts/fetch_highlights.py
```

## Quellen

Konfiguriert in `scripts/config.py`. Aktuell:
LTO, Beck-aktuell, Anwaltsblatt, Heise, Golem, Netzpolitik, MMR, K&R.

## Schema

`news.json`:
```json
{
  "generated_at": "2026-04-27T07:00:00+02:00",
  "items": [
    {
      "id": "news-2026-04-27-01",
      "date": "2026-04-27",
      "source": "LTO",
      "source_url": "https://lto.de/...",
      "headline": "...",
      "summary_md": "## Hintergrund\n\n...\n\n## Was es bedeutet\n\n..."
    }
  ]
}
```

`highlights.json`:
```json
{
  "generated_at": "2026-04-27T06:00:00+02:00",
  "items": [
    {
      "id": "hl-2026-04-27-01",
      "headline": "AI Act Compliance-Welle",
      "teaser": "Am 2. August 2026 treten...",
      "url": "https://..."
    }
  ]
}
```
