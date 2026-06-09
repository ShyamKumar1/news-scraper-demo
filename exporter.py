#!/usr/bin/env python3
"""
Data Exporter — writes filtered article results to CSV or Google Sheets.

Architecture:
- Abstracted behind a single export() interface
- CSV writer works offline, zero setup required
- Google Sheets writer connects via service account (OAuth) when credentials exist
- Both writers follow the same schema, so switching between them is a config change
"""

from __future__ import annotations

import csv
import logging
import os
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


def export(articles: list, config: dict) -> str:
    """
    Export articles to the configured output format.

    Args:
        articles: List of Article dataclass instances
        config: Full configuration dict (export section used)

    Returns:
        Path or URL string describing where the data was written.
    """
    export_cfg = config.get("export", {})
    fmt = export_cfg.get("format", "csv")
    fields = export_cfg.get("fields", [])
    filename = export_cfg.get("filename", "demo_output.csv")

    if fmt == "google_sheets":
        return _export_gsheets(articles, fields, config)
    else:
        return _export_csv(articles, fields, filename)


def _export_csv(articles: list, fields: list[str], filename: str) -> str:
    """Write articles to a CSV file with the specified field order."""
    filepath = os.path.join(os.path.dirname(__file__) or ".", filename)
    os.makedirs(os.path.dirname(filepath) or ".", exist_ok=True)

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for article in articles:
            row = {field: getattr(article, field, "") for field in fields}
            writer.writerow(row)

    count = len(articles)
    logger.info("CSV export complete: %d rows → %s", count, filepath)
    return filepath


def _export_gsheets(articles: list, fields: list[str], config: dict) -> str:
    """
    Write articles to a Google Sheet.

    Requires a service account JSON key at the path specified in
    GOOGLE_APPLICATION_CREDENTIALS env var, or in config under
    export.google_sheets_credentials.

    Falls back to CSV export if credentials are missing.
    """
    creds_path = (
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        or config.get("export", {}).get("google_sheets_credentials")
    )

    if not creds_path or not os.path.exists(creds_path):
        logger.warning(
            "Google Sheets credentials not found at '%s'. "
            "Falling back to CSV export.",
            creds_path,
        )
        return _export_csv(articles, fields, "gsheets_fallback.csv")

    try:
        import gspread
        from google.oauth2.service_account import Credentials

        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(creds_path, scopes=scope)
        client = gspread.authorize(creds)

        sheet_name = f"News Scraper Export {datetime.now().strftime('%Y-%m-%d %H:%M')}"
        sheet = client.create(sheet_name)

        # Build header + data rows
        rows = [[getattr(a, f, "") for f in fields] for a in articles]
        sheet.append_row(fields)
        if rows:
            sheet.append_rows(rows)

        url = f"https://docs.google.com/spreadsheets/d/{sheet.id}"
        logger.info("Google Sheets export complete: %d rows → %s", len(articles), url)
        return url

    except Exception as exc:
        logger.error("Google Sheets export failed: %s", exc)
        logger.info("Falling back to CSV export.")
        return _export_csv(articles, fields, "gsheets_fallback.csv")
