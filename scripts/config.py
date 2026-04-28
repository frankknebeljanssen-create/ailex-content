"""
Configuration: sources, model, run parameters.
Adjust here, not in the fetch scripts.
"""

# Models — both Sonnet 4.6 for now.
# Sonnet has higher rate limits than Opus and is ~5x cheaper. Quality is more
# than sufficient for both research/discovery and per-article summarization.
# If you want to upgrade research to Opus later, change MODEL_RESEARCH only.
MODEL_RESEARCH = "claude-sonnet-4-6"
MODEL_SUMMARY  = "claude-sonnet-4-6"

# Throttle between successive summarize calls (seconds).
# Generous setting — speed doesn't matter on GitHub Actions, quality does.
# 15s is plenty even for the worst-case rate-limit windows.
SUMMARY_SLEEP_SECONDS = 15

# === NEWS PIPELINE ===
# Cron: 1x daily at 07:00 Berlin (see .github/workflows/news.yml)
# Cache: items already in news.json (matched by source_url) are kept verbatim;
#        only new articles incur API cost.
#
# Curated German Legal-AI sources. Bot uses web_search restricted to these
# domains, then fetches articles directly via requests for summary.
NEWS_SOURCES = [
    {"name": "LTO",            "domain": "lto.de"},
    {"name": "Beck-aktuell",   "domain": "rsw.beck.de"},
    {"name": "NJW-aktuell",    "domain": "beck-aktuell.de"},
    {"name": "Anwaltsblatt",   "domain": "anwaltsblatt.de"},
    {"name": "RA-Online",      "domain": "ra-online.de"},
    {"name": "Heise",          "domain": "heise.de"},
    {"name": "Golem",          "domain": "golem.de"},
    {"name": "Netzpolitik",    "domain": "netzpolitik.org"},
    {"name": "MMR (Beck)",     "domain": "beck-online.beck.de"},
    {"name": "K&R",            "domain": "kommunikation-recht.de"},
]

NEWS_TARGET_COUNT = 8
NEWS_SUMMARY_WORDS = (200, 400)
NEWS_MAX_AGE_DAYS = 14

# === HIGHLIGHTS PIPELINE ===
# Cron: Mon/Wed/Fri at 06:00 Berlin (see .github/workflows/highlights.yml)
HIGHLIGHTS_TARGET_COUNT = 6
HIGHLIGHTS_TEASER_WORDS = (50, 100)
HIGHLIGHTS_MAX_AGE_DAYS = 21

# === OUTPUT ===
DATA_DIR = "data"
NEWS_FILE = "news.json"
HIGHLIGHTS_FILE = "highlights.json"
