"""
Configuration: sources, model, run parameters.
Adjust here, not in the fetch scripts.
"""

# Anthropic model used for both pipelines
MODEL = "claude-opus-4-7"

# === NEWS PIPELINE ===
# Cron: 1x daily at 07:00 Berlin (see .github/workflows/news.yml)
# Cache: items already in news.json (matched by source_url) are kept verbatim;
#        only new articles incur API cost.
#
# Curated German Legal-AI sources. Bot uses web_search restricted to these
# domains, then web_fetch on the most relevant articles.
NEWS_SOURCES = [
    {"name": "LTO",            "domain": "lto.de"},
    {"name": "Beck-aktuell",   "domain": "rsw.beck.de"},
    {"name": "Anwaltsblatt",   "domain": "anwaltsblatt.de"},
    {"name": "Heise",          "domain": "heise.de"},
    {"name": "Golem",          "domain": "golem.de"},
    {"name": "Netzpolitik",    "domain": "netzpolitik.org"},
    {"name": "MMR (Beck)",     "domain": "beck-online.beck.de"},
    {"name": "K&R",            "domain": "kommunikation-recht.de"},
]

NEWS_TARGET_COUNT = 8           # how many items to keep in news.json
NEWS_SUMMARY_WORDS = (200, 400) # target word range for summary_md
NEWS_MAX_AGE_DAYS = 14          # drop items older than this from cache

# === HIGHLIGHTS PIPELINE ===
# Cron: Mon/Wed/Fri at 06:00 Berlin (see .github/workflows/highlights.yml)
# Cache: same dedup logic as news, matched by url.
#
# Hot discussion topics — broader than news, longer-running themes.
# Bot does open web research, no domain restriction here.
HIGHLIGHTS_TARGET_COUNT = 6
HIGHLIGHTS_TEASER_WORDS = (50, 100)
HIGHLIGHTS_MAX_AGE_DAYS = 21    # drop items older than this from cache

# === OUTPUT ===
DATA_DIR = "data"
NEWS_FILE = "news.json"
HIGHLIGHTS_FILE = "highlights.json"
