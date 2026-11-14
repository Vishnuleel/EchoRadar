"""English display text: stored apart from the evidence, keyed by the exact original, honest when missing.
No model is downloaded in these tests; a fake translator stands in for it."""
from nexus.core import translation as tr
from nexus.database.models import Translation


class FakeTranslator:
    def __init__(self, mapping):
        self.mapping, self.calls = mapping, 0

    def translate(self, texts):
        self.calls += 1
        return [self.mapping[t] for t in texts]


SV = "Utlysningen stänger 2026-12-02 och 520 000 kr kan sökas per projekt."
EN = "The call closes 2026-12-02 and 520 000 SEK can be applied for per project."


def test_language_check():
    assert tr.is_swedish(SV) and tr.is_swedish("Erbjuder tjänster inom konstruktion och projektledning")
    assert not tr.is_swedish("We develop sonar systems for the offshore industry.")
    assert not tr.is_swedish("IoT") and not tr.is_swedish("")


def test_numbers_and_dates_must_survive():
    assert tr.numbers_preserved(SV, EN)
    assert not tr.numbers_preserved(SV, "The call closes in December and 520 000 SEK can be applied for.")


def test_translations_are_stored_once_and_keyed_by_the_exact_original(session):
    fake = FakeTranslator({SV: EN, "Vi bygger båtar.": "We build boats in 1999."})
    stats = tr.translate_missing(session, [SV, "We build boats.", SV, "Vi bygger båtar."], fake)
    assert stats == {"swedish": 2, "translated": 2, "already": 0, "numbers_flagged": 1}  # 1999 appeared from nowhere
    assert tr.translate_missing(session, [SV], fake)["translated"] == 0 and fake.calls == 1  # cached, not redone
    table = tr.lookup(session)
    assert tr.english(table, SV) == {"text": EN, "engine": tr.ENGINE, "numbers_ok": True, "available": True}
    assert tr.english(table, "Vi bygger båtar.")["numbers_ok"] is False
    assert tr.english(table, "We build boats.") is None  # English source: shown as is
    changed = tr.english(table, SV.replace("520 000", "600 000"))  # the source changed: no stale reuse
    assert changed == {"text": None, "engine": None, "numbers_ok": None, "available": False}
    row = session.get(Translation, (tr.key(SV), "en"))
    assert row.original == SV and row.translated == EN  # the evidence text is untouched next to it


def test_items_get_english_fields_next_to_the_original():
    table = {tr.key(SV): {"text": EN, "engine": tr.ENGINE, "numbers_ok": True}}
    item = tr.with_english({"title": SV, "excerpt": "English excerpt here.", "terms": [("Funding", SV)]}, table)
    assert item["title"] == SV and item["title_en"]["text"] == EN and "excerpt_en" not in item
    assert item["terms_en"][0]["text"] == EN
