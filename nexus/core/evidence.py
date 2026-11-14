"""Evidence checks shared by every extractor (rule-based today, an optional language model later).

Two questions are asked of every source-stated claim before it is stored:

1. Is the quote really there?  `validate_quote` requires a known source id and a short, contiguous
   excerpt that occurs in that source's text (whitespace and quote marks normalised, nothing else).
   This proves the excerpt exists. It does NOT prove the excerpt means what the claim says.
2. Does the sentence state a *current* activity of *this* company?  `statement_status` rejects
   negated ("we do not offer X"), historical ("we previously built X") and third-party ("our customer
   X does Y") statements, and navigation or footer text that slipped through page cleaning.

Both checks are deliberately conservative: a rejected true statement costs a missing claim, which the
profile shows as a gap; an accepted false one would be presented as a fact.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from nexus.security.boundary_guard import scan_untrusted

MIN_QUOTE, MAX_QUOTE = 12, 400

# "utan" is left out: in "inte X utan Y" it means "but" and starts a new clause (see _CLAUSE)
_NEGATION = re.compile(r"(?<![\wåäö])(inte|ej|aldrig|ingen|inget|inga|varken|not|no|never|neither|nor|without|"
                       r"don't|doesn't|didn't|cannot|can't|no longer|inte längre)(?![\wåäö])", re.I)
_HISTORICAL = re.compile(r"(?<![\wåäö])(tidigare|förr|förut|fram till (19|20)\d\d|till och med (19|20)\d\d|"
                         r"avvecklade|avvecklat|lade ner|lagt ner|sålde av|upphörde|"
                         r"previously|formerly|used to|historically|in the past|until (19|20)\d\d|"
                         r"discontinued|no longer|inte längre|was acquired|divested|phased out)(?![\wåäö])", re.I)
_THIRD_PARTY = re.compile(r"(?<![\wåäö])(vår kund|våra kunder|kunden|kunderna|vår partner|våra partners|"
                          r"vår leverantör|våra leverantörer|underleverantör|"
                          r"our customer|our customers|our client|our clients|the customer|our partner|our partners|"
                          r"our supplier|our suppliers|a customer|one customer)(?![\wåäö])", re.I)
# pronouns only: a verb ("offers") says nothing about WHO offers
_FIRST_PERSON = re.compile(r"(?<![\wåäö])(vi|vår|våra|vårt|oss|we|our|us)(?![\wåäö])", re.I)
_NAV = re.compile(r"(\s[|›»•·]\s.*){2,}|^(hem|home|meny|menu|kontakt|contact|sök|search)\b", re.I)
# "and not" / "och inte" are not boundaries: the negation must stay in the clause it negates
_CLAUSE = re.compile(r"[,;:]|\s[–-]\s|\s(men|utan|but|whereas|medan)\s", re.I)


# A narrative about an earlier period: an old year together with past tense ("in 1989 the unit was ...").
_PAST_NARRATIVE = re.compile(r"\b(19\d\d|200\d)\b.*(?<![\wåäö])(was|were|became|had|var|blev|hade)(?![\wåäö])|"
                             r"(?<![\wåäö])(was|were|became|had|var|blev|hade)(?![\wåäö]).*\b(19\d\d|200\d)\b|"
                             r"(?<![\wåäö])(predecessor|föregångare)(?![\wåäö])", re.I)


_SINCE = re.compile(r"(?<![\wåäö])(since|sedan|sen)(?![\wåäö])", re.I)


def mask_name(sentence: str, company_name: str) -> str:
    """Hide the company's own name before capability matching, so "EmbeddedArt" is not read as
    "embedded systems". The original sentence is still what gets stored as evidence."""
    variants = {company_name.strip(), company_name.replace(" ", "")} - {""}
    pattern = r"(?<![\wåäö])(" + "|".join(sorted(map(re.escape, variants), key=len, reverse=True)) + r")[\wåäö]*"
    return re.sub(pattern, "NN", sentence, flags=re.I)


def _norm(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "")
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return " ".join(text.split())


def _clause_with(sentence: str, term: str | None) -> str:
    """The clause of `sentence` that contains `term` (the whole sentence when no term is given)."""
    if not term:
        return sentence
    i = sentence.lower().find(term.lower())
    if i < 0:
        return sentence
    cuts = [0] + [m.end() for m in _CLAUSE.finditer(sentence)] + [len(sentence)]
    start = max(c for c in cuts if c <= i)
    end = min(c for c in cuts if c > i)
    return sentence[start:end]


def statement_status(sentence: str, term: str | None = None) -> str:
    """'current', or why the sentence must not create a current capability for this company:
    'negated' | 'historical' | 'third_party' | 'navigation'."""
    s = _norm(sentence)
    if _NAV.search(s):
        return "navigation"
    clause = _clause_with(s, term)
    # "since the company was founded in 1989 we have ..." is a track record that continues, not history
    narrative = _PAST_NARRATIVE.search(s) and not _SINCE.search(s)
    if _HISTORICAL.search(clause) or (term is None and _HISTORICAL.search(s)) or narrative:
        return "historical"
    if _NEGATION.search(clause):
        return "negated"
    if _THIRD_PARTY.search(clause):
        # "our customers use our sensors" still describes our sensors; "our customer builds ROVs" does not
        rest = _THIRD_PARTY.sub(" ", clause)
        if not _FIRST_PERSON.search(rest):
            return "third_party"
    return "current"


@dataclass
class Source:
    id: str
    url: str
    text: str
    retrieved_at: object = None


@dataclass
class QuoteCheck:
    ok: bool
    reason: str = ""


def validate_quote(source_id: str | None, quote: str | None, sources: dict[str, Source]) -> QuoteCheck:
    """A claim's quote must be a short, contiguous excerpt of the source it cites."""
    if not source_id or source_id not in sources:
        return QuoteCheck(False, f"unknown source id: {source_id!r}")
    q = _norm(quote)
    if len(q) < MIN_QUOTE:
        return QuoteCheck(False, "quote missing or too short")
    if len(q) > MAX_QUOTE:
        return QuoteCheck(False, f"quote longer than {MAX_QUOTE} characters")
    if q not in _norm(sources[source_id].text):
        return QuoteCheck(False, "quote does not occur in the cited source")
    injected = scan_untrusted(q)
    if injected:
        return QuoteCheck(False, f"quote contains instruction-like text: {injected!r}")
    return QuoteCheck(True)


def validate_source_claim(source_id: str | None, quote: str | None, sources: dict[str, Source],
                          term: str | None = None) -> QuoteCheck:
    """Quote check plus the current-statement check, for claims presented as source-stated facts."""
    check = validate_quote(source_id, quote, sources)
    if not check.ok:
        return check
    status = statement_status(quote, term)
    return QuoteCheck(status == "current", "" if status == "current" else f"statement is {status.replace('_', ' ')}")
