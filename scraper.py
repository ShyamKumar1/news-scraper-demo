#!/usr/bin/env python3
"""
News Scraper Engine — handles paginated archive crawling and article extraction.

Features:
- Navigates multi-page archives via "next page" selectors
- Extracts article headlines, URLs, metadata, and body text
- Configurable rate limiting and user-agent rotation
- Graceful error handling per-article (one failure doesn't kill the batch)
"""

from __future__ import annotations

import time
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class Article:
    headline: str
    url: str
    publication_date: str = ""
    source: str = ""
    summary: str = ""
    category: str = ""
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return asdict(self)


class NewsScraper:
    """
    Generic paginated news archive scraper.

    Configure via a dict matching the config.yaml schema. Minimal example:
        scraper = NewsScraper({
            "target_site": {
                "name": "My News Site",
                "base_url": "https://example.com/news",
                "article_container": "div.article",
                "title_selector": "h2 > a",
                "next_page_selector": "a.next",
            },
            "scraping": {"max_pages": 3, "delay_between_requests": 1.0},
        })
    """

    def __init__(self, config: dict):
        site = config.get("target_site", {})
        scrape_cfg = config.get("scraping", {})

        self.site_name = site.get("name", "Unknown")
        self.base_url = site.get("base_url", "")
        self.article_container = site.get("article_container", "")
        self.title_selector = site.get("title_selector", "")
        self.subtitle_selector = site.get("subtitle_selector", "")
        self.next_page_selector = site.get("next_page_selector", "")
        self.url_prefix = site.get("url_prefix", "")

        self.max_pages = scrape_cfg.get("max_pages", 3)
        self.delay = scrape_cfg.get("delay_between_requests", 1.0)
        self.user_agent = scrape_cfg.get(
            "user_agent",
            "Mozilla/5.0 (compatible; NewsScraper/1.0)",
        )

        self.session = requests.Session()
        self.session.headers.update({"User-Agent": self.user_agent})

    def _resolve_url(self, href: str) -> str:
        """Resolve relative URLs against the base."""
        if href.startswith("http://") or href.startswith("https://"):
            return href
        return self.url_prefix.rstrip("/") + "/" + href.lstrip("/")

    def _extract_articles_from_page(self, html: str, source_pages: list[str]) -> list[Article]:
        """
        Parse a single page HTML and extract all articles.

        Override this method in a subclass for site-specific parsing.
        Returns a list of Article dataclass instances.
        """
        soup = BeautifulSoup(html, "lxml")
        articles: list[Article] = []

        rows = soup.select(self.article_container)
        logger.debug("Found %d article rows on page", len(rows))

        for row in rows:
            try:
                # --- Extract title + URL ---
                title_el = row.select_one(self.title_selector) if self.title_selector else None
                if not title_el:
                    continue
                headline = title_el.get_text(strip=True)
                href = title_el.get("href", "")
                url = self._resolve_url(href)

                # --- Extract subtitle metadata (points, author, time) ---
                subtitle_text = ""
                if self.subtitle_selector:
                    subtitle_row = row.find_next_sibling("tr")
                    if subtitle_row:
                        sub_el = subtitle_row.select_one(self.subtitle_selector)
                        if sub_el:
                            subtitle_text = sub_el.get_text(" ", strip=True)

                # Use subtitle as summary for embedding context
                summary = subtitle_text[:300] if subtitle_text else ""

                articles.append(Article(
                    headline=headline,
                    url=url,
                    publication_date="",
                    source=self.site_name,
                    summary=summary,
                ))
            except Exception as exc:
                logger.warning("Skipping article due to error: %s", exc)
                continue

        return articles

    def _extract_summary(self, url: str) -> str:
        """Fetch article page and extract first meaningful paragraph as summary."""
        try:
            resp = self.session.get(url, timeout=10)
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            # Try common content containers
            for sel in ["article p", ".content p", ".article-body p", "main p", "p"]:
                paragraphs = soup.select(sel)
                for p in paragraphs:
                    text = p.get_text(strip=True)
                    if len(text) > 80:
                        return text[:250] + ("..." if len(text) > 250 else "")
            return ""
        except Exception:
            return ""

    def crawl(self) -> list[Article]:
        """Crawl the paginated archive and return all discovered articles."""
        all_articles: list[Article] = []
        current_url = self.base_url
        page_num = 0

        while current_url and page_num < self.max_pages:
            page_num += 1
            logger.info("Fetching page %d: %s", page_num, current_url)

            try:
                resp = self.session.get(current_url, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as exc:
                logger.error("Failed to fetch page %d: %s", page_num, exc)
                break

            articles = self._extract_articles_from_page(resp.text, [current_url])
            logger.info("Extracted %d articles from page %d", len(articles), page_num)
            all_articles.extend(articles)

            # --- Find next page link ---
            soup = BeautifulSoup(resp.text, "lxml")
            next_el = soup.select_one(self.next_page_selector) if self.next_page_selector else None
            current_url = self._resolve_url(next_el.get("href", "")) if next_el else None

            if current_url and page_num < self.max_pages:
                time.sleep(self.delay)

        logger.info(
            "Crawl complete: %d articles across %d page(s)",
            len(all_articles),
            page_num,
        )
        return all_articles


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
    import yaml
    with open("config.yaml") as f:
        cfg = yaml.safe_load(f)
    scraper = NewsScraper(cfg)
    arts = scraper.crawl()
    print(f"\nScraped {len(arts)} articles:")
    for a in arts[:5]:
        print(f"  - {a.headline}")
