#!/usr/bin/env python3
"""
AI/NLP Semantic Keyword Filter — uses sentence-transformers embeddings
to match articles by meaning, not just exact string matches.

Key design:
- Pre-computes keyword embeddings once at init
- Each article headline+summary is embedded and compared via cosine similarity
- Assigns each article the best-matching keyword as its "category"
- Falls back to simple substring matching when no model is available
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SemanticFilter:
    """
    Semantic keyword filter using sentence-transformers.

    Usage:
        filter_engine = SemanticFilter(config)
        results = filter_engine.filter(articles)
        # articles are annotated with category + relevance_score in-place

    On models that support it, the embedding cache keeps repeated calls fast.
    """

    def __init__(self, config: dict):
        filter_cfg = config.get("filtering", {})
        self.method = filter_cfg.get("method", "semantic")
        self.threshold = filter_cfg.get("similarity_threshold", 0.45)
        self.model_name = filter_cfg.get("model_name", "all-MiniLM-L6-v2")
        self.keywords = config.get("keywords", [])
        self._model = None
        self._keyword_embeddings = None

    def _load_model(self):
        """Lazy-load the sentence-transformers model (first call warms up)."""
        if self._model is not None:
            return
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading model '%s' ...", self.model_name)
            self._model = SentenceTransformer(self.model_name)
            logger.info("Model loaded. Encoding %d keywords ...", len(self.keywords))
            self._keyword_embeddings = self._model.encode(self.keywords, normalize_embeddings=True)
            logger.info("Keyword embeddings ready.")
        except Exception as exc:
            logger.warning("Failed to load sentence-transformers: %s", exc)
            logger.warning("Falling back to keyword substring matching.")
            self.method = "keyword"

    def filter(self, articles: list) -> list:
        """
        Filter and annotate articles based on keyword matching.

        Args:
            articles: List of Article-like objects (must have .headline, .summary)

        Returns:
            Filtered list (articles below threshold removed).
            Matching articles get .category and .relevance_score set.
        """
        if not articles:
            return []

        if self.method == "semantic":
            return self._semantic_filter(articles)
        else:
            return self._keyword_filter(articles)

    def _keyword_filter(self, articles: list) -> list:
        """Simple case-insensitive substring matching fallback."""
        results = []
        for article in articles:
            text = (article.headline + " " + article.summary).lower()
            best_score = 0.0
            best_keyword = ""
            for kw in self.keywords:
                if kw.lower() in text:
                    score = len(kw) / max(len(text), 1) * 100  # rough relevance
                    if score > best_score:
                        best_score = score
                        best_keyword = kw
            if best_score > 0:
                article.category = best_keyword
                article.relevance_score = round(best_score / 100, 4)
                results.append(article)
        return results

    def _semantic_filter(self, articles: list) -> list:
        """Semantic similarity matching using sentence embeddings."""
        self._load_model()
        if self._model is None:
            return self._keyword_filter(articles)

        texts = []
        for a in articles:
            text = a.headline
            if a.summary:
                text += ". " + a.summary[:500]
            texts.append(text)

        try:
            article_embeddings = self._model.encode(texts, normalize_embeddings=True)
        except Exception as exc:
            logger.error("Embedding failed: %s", exc)
            return self._keyword_filter(articles)

        import numpy as np

        results = []
        for i, article in enumerate(articles):
            art_emb = article_embeddings[i]
            # Cosine similarity with all keyword embeddings
            similarities = np.dot(self._keyword_embeddings, art_emb)
            best_idx = int(np.argmax(similarities))
            best_score = float(similarities[best_idx])

            if best_score >= self.threshold:
                article.category = self.keywords[best_idx]
                article.relevance_score = round(best_score, 4)
                results.append(article)

        logger.info(
            "Semantic filter: %d/%d articles passed (threshold=%.2f)",
            len(results),
            len(articles),
            self.threshold,
        )
        return results
