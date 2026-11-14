"""Store English display translations for the Swedish public source texts the interface shows.

    python scripts/translate.py

Runs a local model (Helsinki-NLP/opus-mt-sv-en, downloaded once into data/models). Only public source
text is translated. Translations are labelled as machine translations everywhere they are shown; the
Swedish original remains the evidence. Already translated texts are skipped.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nexus.core import translation  # noqa: E402
from nexus.database.database import session_scope  # noqa: E402

if __name__ == "__main__":
    with session_scope() as s:
        stats = translation.translate_missing(s, translation.public_source_texts(s))
    print(f"Swedish texts: {stats['swedish']}, newly translated: {stats['translated']}, already stored: {stats['already']}, "
          f"flagged because numbers or dates changed: {stats['numbers_flagged']}")
