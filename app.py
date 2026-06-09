#!/usr/bin/env python3
"""
News Scraper Dashboard — FastAPI web UI

Run with:
    uvicorn app:app --host 0.0.0.0 --port 8080 --reload
"""

from __future__ import annotations

import os
import sys
import json
import csv
import io
import logging
import tempfile
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Form, Query, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# Ensure project root is on path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from scraper import NewsScraper, Article
from nlp_filter import SemanticFilter

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(title="News Scraper Dashboard", version="1.0.0")

# --- Load default config ---
import yaml
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config.yaml")
with open(CONFIG_PATH) as f:
    DEFAULT_CONFIG = yaml.safe_load(f)


# Serve static files (optional)
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)


def run_scraper_pipeline(
    target_url: str = "",
    keywords_str: str = "",
    max_pages: int = 2,
    threshold: float = 0.20,
) -> dict:
    """Run the full scraper + filter + export pipeline and return results."""
    config = __import__("copy").deepcopy(DEFAULT_CONFIG)

    # Apply overrides
    if target_url:
        config["target_site"]["base_url"] = target_url
    if keywords_str:
        config["keywords"] = [kw.strip() for kw in keywords_str.split(",") if kw.strip()]
    config["scraping"]["max_pages"] = max_pages
    config["filtering"]["similarity_threshold"] = threshold
    config["export"]["filename"] = "dashboard_output.csv"

    # Phase 1: Scrape
    scraper = NewsScraper(config)
    articles = scraper.crawl()

    # Phase 2: Filter
    filter_engine = SemanticFilter(config)
    filtered = filter_engine.filter(articles)

    # Phase 3: Format for JSON response
    result_list = []
    for a in filtered:
        result_list.append({
            "headline": a.headline,
            "url": a.url,
            "source": a.source or config["target_site"]["name"],
            "summary": a.summary[:200] if a.summary else "",
            "category": a.category,
            "relevance_score": round(a.relevance_score, 4),
        })

    # Save CSV for download
    csv_path = os.path.join(os.path.dirname(__file__), "dashboard_output.csv")
    fields = ["headline", "url", "source", "summary", "category", "relevance_score"]
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(result_list)

    return {
        "total_scraped": len(articles),
        "total_filtered": len(result_list),
        "results": result_list,
        "keywords": config["keywords"],
        "csv_path": csv_path,
    }


# ==================== ROUTES ====================

@app.get("/", response_class=HTMLResponse)
async def dashboard():
    """Serve the dashboard HTML."""
    html_path = os.path.join(os.path.dirname(__file__), "templates", "index.html")
    if not os.path.exists(html_path):
        return HTMLResponse("<h1>Dashboard template not found</h1>", status_code=500)
    with open(html_path) as f:
        return HTMLResponse(f.read())


@app.post("/api/scrape")
async def api_scrape(
    target_url: str = Form(""),
    keywords: str = Form(""),
    max_pages: int = Form(2),
    threshold: float = Form(0.20),
):
    """Run the scraper pipeline and return JSON results."""
    try:
        result = run_scraper_pipeline(
            target_url=target_url,
            keywords_str=keywords,
            max_pages=max_pages,
            threshold=threshold,
        )
        return {"success": True, "data": result}
    except Exception as exc:
        logger.exception("Scrape failed")
        return {"success": False, "error": str(exc)}


@app.get("/api/export")
async def api_export():
    """Download the last scrape results as CSV."""
    csv_path = os.path.join(os.path.dirname(__file__), "dashboard_output.csv")
    if not os.path.exists(csv_path):
        raise HTTPException(status_code=404, detail="No results yet. Run a scrape first.")

    with open(csv_path) as f:
        content = f.read()

    return StreamingResponse(
        io.StringIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=news_scraper_results.csv"},
    )


@app.get("/api/demo")
async def api_demo_data():
    """Return pre-scraped demo data for instant UI populating."""
    csv_path = os.path.join(os.path.dirname(__file__), "demo_output.csv")
    if not os.path.exists(csv_path):
        return {"success": False, "error": "Demo data not found"}

    results = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            results.append({
                "headline": row.get("headline", ""),
                "url": row.get("url", ""),
                "source": row.get("source", ""),
                "summary": row.get("summary", "")[:200],
                "category": row.get("category", ""),
                "relevance_score": float(row.get("relevance_score", 0) or 0),
            })

    return {
        "success": True,
        "data": {
            "total_scraped": 60,
            "total_filtered": len(results),
            "results": results,
            "keywords": DEFAULT_CONFIG.get("keywords", []),
        },
    }


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8080, reload=True)
