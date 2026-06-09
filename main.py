#!/usr/bin/env python3
"""
News Scraper with AI/NLP Semantic Filtering — Main Entry Point

Usage:
    python3 main.py                          # Scrape with config.yaml defaults
    python3 main.py --pages 5                # Override max pages
    python3 main.py --keywords "AI,climate"  # Override keywords
    python3 main.py --format csv             # Export format
    python3 main.py --url "https://..."      # Different target site

Demo mode (default):
    Scrapes Hacker News (paginated), applies semantic keyword filtering
    using sentence-transformers, and exports the result to CSV.

This demonstrates all three deliverables from the project:
    1. Archive scraper with pagination handling
    2. AI/NLP-powered keyword filtering
    3. Structured data export
"""

from __future__ import annotations

import argparse
import logging
import sys
import os

# Ensure we can import sibling modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import NewsScraper
from nlp_filter import SemanticFilter
from exporter import export as export_data


def load_config(config_path: str = "config.yaml") -> dict:
    """Load YAML configuration file."""
    import yaml
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print(f"Error: Config file '{config_path}' not found.")
        print("Run from the project directory containing config.yaml")
        sys.exit(1)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI-Powered News Scraper with Semantic Filtering",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 main.py                       # Demo: scrape + filter + export
  python3 main.py --pages 5             # Scrape 5 pages
  python3 main.py --format google_sheets
  python3 main.py --keywords "climate,regulation,policy"
  python3 main.py --url "https://example.com/news"
        """,
    )
    parser.add_argument("--config", default="config.yaml",
                        help="Path to YAML config (default: config.yaml)")
    parser.add_argument("--pages", type=int,
                        help="Override max pages to scrape")
    parser.add_argument("--keywords",
                        help="Comma-separated keyword list (overrides config)")
    parser.add_argument("--format", choices=["csv", "google_sheets"],
                        help="Export format (overrides config)")
    parser.add_argument("--url",
                        help="Override target site base URL")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable debug logging")
    return parser.parse_args()


def main():
    args = parse_args()

    # --- Logging ---
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(name)-12s | %(levelname)-5s | %(message)s",
        datefmt="%H:%M:%S",
    )
    # Quiet down noisy libs
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("transformers").setLevel(logging.WARNING)

    # --- Load config ---
    config = load_config(args.config)

    # Apply CLI overrides
    if args.pages:
        config.setdefault("scraping", {})["max_pages"] = args.pages
    if args.keywords:
        config["keywords"] = [kw.strip() for kw in args.keywords.split(",")]
    if args.format:
        config.setdefault("export", {})["format"] = args.format
    if args.url:
        config.setdefault("target_site", {})["base_url"] = args.url

    print("╔══════════════════════════════════════════════════╗")
    print("║   AI-Powered News Scraper — Semantic Filtering  ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print(f"  Target  : {config.get('target_site', {}).get('name', 'Custom')}")
    print(f"  Pages   : {config.get('scraping', {}).get('max_pages', 3)}")
    print(f"  Keywords: {', '.join(config.get('keywords', []))}")
    print(f"  Filter  : {config.get('filtering', {}).get('method', 'keyword')}")
    print(f"  Export  : {config.get('export', {}).get('format', 'csv')}")
    print()

    # --- Phase 1: Scrape ---
    print("▸ Phase 1: Crawling paginated archive ...")
    scraper = NewsScraper(config)
    articles = scraper.crawl()
    print(f"  ✓ {len(articles)} raw articles extracted")
    print()

    if not articles:
        print("✗ No articles found. Check the site selectors in config.yaml.")
        sys.exit(1)

    # --- Phase 2: Filter ---
    print("▸ Phase 2: Applying AI/NLP semantic keyword filter ...")
    filter_engine = SemanticFilter(config)
    filtered = filter_engine.filter(articles)
    print(f"  ✓ {len(filtered)} articles matched keywords")
    print()

    if not filtered:
        print("No articles matched the keyword criteria. Try lowering the threshold.")
        sys.exit(0)

    # --- Phase 3: Export ---
    print(f"▸ Phase 3: Exporting to {config.get('export', {}).get('format', 'csv').upper()} ...")
    result = export_data(filtered, config)
    print(f"  ✓ Exported: {result}")
    print()

    # --- Summary ---
    print("╔══════════════════════════════════════════════════╗")
    print("║                    RESULTS                      ║")
    print("╚══════════════════════════════════════════════════╝")
    print()
    print(f"  Articles scraped    : {len(articles)}")
    print(f"  After AI filtering  : {len(filtered)}")
    print(f"  Output file         : {result}")
    print()

    # Show top 10 filtered
    print("  Top matches:")
    for i, a in enumerate(filtered[:10], 1):
        score = getattr(a, "relevance_score", 0)
        cat = getattr(a, "category", "")
        hl = a.headline[:70] + ("..." if len(a.headline) > 70 else "")
        bar = "█" * max(1, int(score * 30))
        print(f"  {i:2d}. [{cat:20s}] {score:.2f} {bar}")
        print(f"      {hl}")
        print()

    print(f"  ... and {len(filtered) - 10} more articles in the export.")
    print()
    print("✓ Demo complete. Ready for production deployment.")


if __name__ == "__main__":
    main()
