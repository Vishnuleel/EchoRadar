"""Embedding service with a persistent cache and a deterministic offline fallback.

Backends
* "st"   - sentence-transformers multilingual MiniLM (Swedish + English in one space)
* "hash" - character n-gram hashing TF vectors (scikit-learn). No download, deterministic.
* "auto" - try "st", fall back to "hash" and say so (the UI shows the active backend).

Vectors are L2-normalised, so cosine similarity is a dot product. They are stored in the
embedding_cache table keyed by (sha256(text), backend) and reused across runs.
"""
from __future__ import annotations

import hashlib

import numpy as np

from nexus.utils.config import get_settings
from nexus.utils.logging import get_logger

log = get_logger(__name__)
_INSTANCE = None


class Embedder:
    def __init__(self, backend: str | None = None):
        st = get_settings()
        want = backend or st.embeddings
        self._model = None
        self.fallback_reason: str | None = None
        if want in ("auto", "st"):
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(st.embedding_model, cache_folder=str(st.model_dir),
                                                  local_files_only=st.offline)
                self.backend = st.embedding_model
            except Exception as exc:  # model missing / no network
                if want == "st":
                    raise
                self.fallback_reason = f"{type(exc).__name__}: {str(exc)[:160]}"
                log.warning("Sentence-transformers unavailable, using hashing fallback: %s", self.fallback_reason)
        if self._model is None:
            from sklearn.feature_extraction.text import HashingVectorizer

            self._hv = HashingVectorizer(analyzer="char_wb", ngram_range=(3, 5), n_features=1024,
                                         alternate_sign=False, norm="l2", lowercase=True)
            self.backend = "hash-char-ngram-1024"
        self._mem: dict[str, np.ndarray] = {}

    @property
    def is_semantic(self) -> bool:
        return self._model is not None

    def _compute(self, texts: list[str]) -> np.ndarray:
        if self._model is not None:
            return np.asarray(self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False,
                                                 batch_size=32), dtype=np.float32)
        return self._hv.transform(texts).toarray().astype(np.float32)

    def encode(self, texts: list[str], session=None) -> np.ndarray:
        """Encode texts, reusing the in-memory and (if a session is given) database cache."""
        texts = [(t or "").strip()[:2000] or "-" for t in texts]
        keys = [hashlib.sha256(t.encode("utf-8")).hexdigest() for t in texts]
        missing = [k for k in dict.fromkeys(keys) if k not in self._mem]
        if missing and session is not None:
            from sqlalchemy import select

            from nexus.database.models import EmbeddingCache

            for i in range(0, len(missing), 500):
                rows = session.execute(select(EmbeddingCache.text_hash, EmbeddingCache.vector).where(
                    EmbeddingCache.backend == self.backend, EmbeddingCache.text_hash.in_(missing[i:i + 500])))
                for h, blob in rows:
                    self._mem[h] = np.frombuffer(blob, dtype=np.float32)
            missing = [k for k in missing if k not in self._mem]
        if missing:
            by_key = dict(zip(keys, texts))
            vecs = self._compute([by_key[k] for k in missing])
            for k, v in zip(missing, vecs):
                self._mem[k] = v
            if session is not None:
                from nexus.database.models import EmbeddingCache

                session.add_all([EmbeddingCache(text_hash=k, backend=self.backend, vector=self._mem[k].tobytes())
                                 for k in missing])
                session.flush()
        return np.vstack([self._mem[k] for k in keys]) if keys else np.zeros((0, 1), dtype=np.float32)


def get_embedder() -> Embedder:
    global _INSTANCE
    if _INSTANCE is None:
        _INSTANCE = Embedder()
    return _INSTANCE


def reset_embedder() -> None:
    global _INSTANCE
    _INSTANCE = None


def cosine_matrix(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine similarity for (already normalised or not) row vectors."""
    a = a / np.clip(np.linalg.norm(a, axis=1, keepdims=True), 1e-9, None)
    b = b / np.clip(np.linalg.norm(b, axis=1, keepdims=True), 1e-9, None)
    return a @ b.T
