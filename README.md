# News Scraper with AI/NLP Semantic Filtering

**A production-ready web scraping system** that crawls paginated news archives, applies AI-powered semantic keyword filtering, and exports structured results to CSV or Google Sheets.

## Live Dashboard

Run the interactive web UI:

```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 8080
# Open http://localhost:8080
```

The dashboard loads pre-scraped demo data on startup. Adjust keywords, threshold, and target URL, then click **Run** to execute a live scrape with semantic filtering.

## Quick Start (CLI)

```bash
pip install -r requirements.txt
python3 main.py
```

## Architecture

```
main.py          → CLI entry point (argparse, orchestration)
scraper.py       → Paginated archive crawling + article extraction
nlp_filter.py    → sentence-transformers semantic keyword matching
exporter.py      → CSV / Google Sheets data export
config.yaml      → All configuration (target sites, keywords, thresholds)
```

## Features

### 1. Paginated Archive Scraper
- Crawls multi-page news archives by following "next page" links
- Configurable per-site via CSS selectors in `config.yaml`
- Rate-limited requests with configurable delays
- Per-article error isolation (one failure doesn't stop the batch)
- Automatic article body extraction for summary generation

### 2. AI/NLP Semantic Keyword Filtering
- Uses **sentence-transformers** (all-MiniLM-L6-v2) to embed both keywords and articles
- Matches by **cosine similarity** — catches articles using different words for the same topic
- Configurable similarity threshold (default: 0.45)
- Graceful fallback to substring matching if model fails to load
- Each matched article receives a **relevance score** + assigned **category**

### 3. Structured Data Export
- **CSV export**: Works immediately, zero setup
- **Google Sheets export**: Available with service account credentials
- Export fields: headline, URL, publication_date, source, summary, category, relevance_score

## Configuration

All configuration is in `config.yaml`:

```yaml
target_site:
  name: "Hacker News"
  base_url: "https://news.ycombinator.com/"
  article_container: "tr.athing"
  title_selector: "span.titleline > a"
  next_page_selector: "a.morelink"

keywords:
  - "artificial intelligence"
  - "machine learning"
  - "python"

filtering:
  method: "semantic"
  similarity_threshold: 0.45
  model_name: "all-MiniLM-L6-v2"
```

To target a different news archive, swap the CSS selectors and base URL.

## CLI Usage

```bash
python3 main.py                          # Run with defaults
python3 main.py --pages 5                # Scrape 5 pages
python3 main.py --keywords "AI,climate"  # Custom keywords
python3 main.py --format csv             # Export to CSV
python3 main.py --url "https://..."      # Different target
python3 main.py --verbose                # Debug logging
```

## Demo Output

Running the tool against Hacker News with keywords like "artificial intelligence," "python," "security," and "startup" produces:

- Raw scrape: ~90 articles across 3 pages
- After AI filtering: ~20-40 relevant matches
- Export: CSV with headline, URL, category, and relevance score

## Production Deployment

For production use against client's target sites:

1. Update `config.yaml` with the client's site selectors
2. Tune `similarity_threshold` per keyword list
3. Set up Google Sheets service account
4. Wrap in Docker or cron for scheduled runs
5. (Optional) Add `streamlit` dashboard for keyword management
