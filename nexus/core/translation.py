"""English display text for Swedish public sources: machine translation, stored, labelled, never evidence.

* The original text stays the evidence; the translation is a separate, labelled display aid.
* Translations are cached by sha256 of the exact original, so a changed source is translated again.
* A translation whose numbers or dates differ from the original is kept but flagged (`numbers_ok`).
* Runs locally (Helsinki-NLP/opus-mt-sv-en via transformers), once at ingest time. The app reads the
  stored result and never needs the model at run time; without a stored translation it shows the
  original and says that no translation is available.
"""
from __future__ import annotations

import hashlib
import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.database.models import Translation
from nexus.utils.logging import get_logger

log = get_logger(__name__)
MODEL_ID = "Helsinki-NLP/opus-mt-sv-en"
ENGINE = f"{MODEL_ID} (machine translation)"

_SV_WORDS = re.compile(r"(?<![\wåäö])(och|för|att|med|som|är|inom|av|vi|det|en|ett|till|på|samt|erbjuder|"
                       r"utvecklar|företag|tjänster|inom|hos|vår|våra|kan|ska)(?![\wåäö])", re.I)
_EN_WORDS = re.compile(r"(?<![\w])(the|and|of|for|with|to|in|is|are|we|our|on|by|from|this)(?![\w])", re.I)
_NUMBER = re.compile(r"\d[\d\s.,:/-]*\d|\d")
_SENT = re.compile(r"(?<=[.!?])\s+(?=[A-ZÅÄÖ0-9\"“])")


def key(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()


def is_swedish(text: str | None) -> bool:
    """Cheap language check: Swedish letters or function words clearly outnumber English ones."""
    if not text or len(text.strip()) < 3:
        return False
    sv, en = len(_SV_WORDS.findall(text)), len(_EN_WORDS.findall(text))
    return (sv > en) or (bool(re.search(r"[åäöÅÄÖ]", text)) and en == 0)


def _digits(text: str) -> list[str]:
    return sorted(re.sub(r"\D", "", m) for m in _NUMBER.findall(text or "") if re.sub(r"\D", "", m))


def numbers_preserved(original: str, translated: str) -> bool:
    """Every number and date in the original appears in the translation (formatting may differ)."""
    return _digits(original) == _digits(translated)


class LocalTranslator:
    """Swedish -> English with a local MarianMT model (downloaded once into data/models)."""

    def __init__(self, cache_dir=None, local_only: bool | None = None):
        from transformers import MarianMTModel, MarianTokenizer

        from nexus.utils.config import get_settings

        st = get_settings()
        kw = {"cache_dir": str(cache_dir or st.model_dir), "local_files_only": st.offline if local_only is None else local_only}
        self.tok = MarianTokenizer.from_pretrained(MODEL_ID, **kw)
        self.model = MarianMTModel.from_pretrained(MODEL_ID, **kw)

    def translate(self, texts: list[str], batch: int = 16) -> list[str]:
        out = []
        for text in texts:  # sentence by sentence: the model is trained on sentences and has a length limit
            parts = [p for p in _SENT.split(" ".join(text.split())) if p]
            done = []
            for i in range(0, len(parts), batch):
                enc = self.tok(parts[i:i + batch], return_tensors="pt", padding=True, truncation=True, max_length=400)
                gen = self.model.generate(**enc, max_new_tokens=400)
                done += [self.tok.decode(g, skip_special_tokens=True) for g in gen]
            out.append(" ".join(done))
        return out


def translate_missing(s: Session, texts, translator=None) -> dict:
    """Translate the Swedish texts that have no stored translation yet. Returns counts."""
    wanted = {}
    for t in texts:
        t = (t or "").strip()
        if t and is_swedish(t):
            wanted.setdefault(key(t), t)
    have = set(s.scalars(select(Translation.text_hash).where(Translation.text_hash.in_(list(wanted)), Translation.target == "en"))) \
        if wanted else set()
    todo = {k: v for k, v in wanted.items() if k not in have}
    if not todo:
        return {"swedish": len(wanted), "translated": 0, "already": len(have), "numbers_flagged": 0}
    translator = translator or LocalTranslator()
    items = list(todo.items())
    flagged = 0
    for i in range(0, len(items), 32):
        chunk = items[i:i + 32]
        for (h, original), english in zip(chunk, translator.translate([o for _, o in chunk])):
            ok = numbers_preserved(original, english)
            flagged += not ok
            s.add(Translation(text_hash=h, target="en", source_lang="sv", original=original, translated=english,
                              engine=ENGINE, numbers_ok=ok))
        s.flush()
    return {"swedish": len(wanted), "translated": len(todo), "already": len(have), "numbers_flagged": flagged}


def lookup(s: Session) -> dict[str, dict]:
    """All stored English translations by original-text hash (small table; read once and cached by the API)."""
    return {t.text_hash: {"text": t.translated, "engine": t.engine, "numbers_ok": t.numbers_ok}
            for t in s.scalars(select(Translation).where(Translation.target == "en"))}


def english(table: dict, text: str | None) -> dict | None:
    """Display record for one source text: None when the text is not Swedish (shown as is).
    {"available": False} when it is Swedish but no translation is stored: the UI says so honestly."""
    if not text or not is_swedish(text):
        return None
    t = table.get(key(text.strip()))
    if t is None:
        return {"text": None, "engine": None, "numbers_ok": None, "available": False}
    return {**t, "available": True}


def with_english(item: dict, table: dict, fields=("title", "excerpt")) -> dict:
    """Copy of a display item with `<field>_en` added for each Swedish field."""
    out = dict(item)
    for f in fields:
        en = english(table, item.get(f))
        if en is not None:
            out[f"{f}_en"] = en
    if item.get("terms"):
        out["terms_en"] = [english(table, v) for _, v in item["terms"]]
    return out


def public_source_texts(s: Session) -> list[str]:
    """Every public Swedish-capable text the interface displays (never private refinements)."""
    from nexus.core import radar
    from nexus.database.models import Company, Event, FundingOpportunity, NewsUpdate, Testbed
    from nexus.utils.validators import utcnow

    texts: list[str] = []
    for c in s.scalars(select(Company)):
        texts += [c.description, c.industry]
    now = utcnow()
    for kind, model in (("funding", FundingOpportunity), ("testbed", Testbed), ("event", Event), ("news", NewsUpdate)):
        for row in s.scalars(select(model)):
            d = radar.describe(kind, row, now)
            if d is not None:
                texts += [d["title"], d["excerpt"]] + [v for _, v in d["terms"]]
    return [t for t in texts if t]
