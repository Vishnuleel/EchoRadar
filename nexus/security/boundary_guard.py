"""Service boundaries enforced in code (not in an LLM prompt).

classify_request() decides, with explicit rules, whether a request is

  in_scope             - answered from stored, source-linked records
  needs_clarification  - connection to the service purpose is unclear: ask one focused question
  out_of_scope         - explain the remit and redirect
  escalation           - needs a human decision, a formal eligibility ruling, a commitment or
                         professional advice: refer to Blue Science Park staff
  prompt_injection     - attempt to change the role or rules, or to adopt another role
  privacy_violation    - attempt to reach another company's non-public data

Role persistence: every turn is classified on its own text. A previous in-scope turn only helps
a short follow-up ("and funding?") to be understood; it can never unlock a blocked category.

scan_untrusted() detects instruction-like text inside retrieved web content. Such text is data:
it is dropped from extraction and logged, never obeyed.

Second line of defence: private data is only readable through nexus.security.privacy, which
checks ownership regardless of what any request says.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

SCOPE_DESCRIPTION = (
    "I support innovation, business development and collaboration in the Blue Science Park ecosystem: "
    "technology, research and regional developments, events, test environments, funding opportunities, "
    "potential partners, and refining your company profile."
)
STAFF_CONTACT = ("Blue Science Park staff can help with this: https://www.bluesciencepark.se/kontakt/ "
                 "(info@bluesciencepark.se, as published on that page).")
DISCLAIMER = ("Information and suggested next steps only. This is not professional advice, a formal eligibility "
              "decision or a commitment by Blue Science Park.")

_INJECTION = [
    r"ignore (?:all |any |the |your )?(?:previous|prior|above|earlier)?\s*(?:rules|instructions|prompts?|guidelines|boundaries)",
    r"disregard (?:all |any |the |your )?(?:previous|prior|above)?\s*(?:rules|instructions|guidelines)",
    r"forget (?:all |your |the )?(?:previous |prior )?(?:rules|instructions)",
    r"(?:reveal|show|print|repeat|display|leak)\b.{0,40}\b(?:system prompt|system instructions?|hidden instructions?|developer message|your instructions|your rules)",
    r"you are now\b", r"act as (?:an? |my )?", r"\bjailbreak\b", r"\bdan mode\b", r"role-?play", r"pretend (?:to be|that you|you are)",
    r"from now on you", r"take on the role", r"adopt (?:a |another |the )?(?:new |different )?(?:role|persona)",
    r"override (?:your |the |all )?(?:rules|safety|boundaries|restrictions|instructions)",
    r"new instructions?:", r"system\s*:\s", r"bypass (?:the |your |all )?(?:rules|restrictions|filters|boundaries)",
    r"ignorera (?:alla )?(?:tidigare )?(?:regler|instruktioner)", r"do anything now", r"developer mode",
    r"stop being (?:a |an )?", r"you (?:have|are under) no (?:rules|restrictions)", r"låtsas (?:att du är|vara)",
]
_PRIVACY = [
    r"(?:another|other|different|competitor'?s?|someone else'?s|their|its)\s+(?:company'?s?\s+|compan(?:y|ies)'?\s+)?(?:private|internal|confidential|non-public|saved)",
    r"private (?:profile|notes?|data|interactions?|feedback|queries|information)\b.{0,40}\b(?:of|for|from|belonging to)\b",
    r"internal (?:interactions?|notes?|documents?|data|strategy|plans?)",
    r"(?:confidential|secret|unpublished|non-public)\s+(?:strategy|plans?|data|information|roadmap|pricing|customers?|profile)",
    r"what (?:did|has|have) .{1,60} (?:ask|asked|search|searched|queried|rate|rated|saved?)",
    r"(?:queries|questions|feedback|notes|saved (?:items|opportunities)) (?:from|by|of) (?:other|another)",
    r"what .{1,60}\b(?:asked|searched|queried|rated|saved)\b(?! for)", r"(?:chat|search|query) (?:history|log)s? (?:of|for|from)\b",
    r"andra företags? (?:privata|interna)",
]
_ESCALATION = [
    r"\bam i eligible\b", r"\bare we eligible\b", r"(?:confirm|guarantee|decide|approve)\b.{0,40}\b(?:eligib|funding|grant|application|membership)",
    r"will (?:we|i|our company) (?:get|receive|be granted|win)", r"\blegal advice\b", r"\btax advice\b", r"juridisk rådgivning",
    r"(?:sign|draft|review) (?:a |the |our )?(?:contract|nda|agreement)", r"can (?:you|blue science park) (?:commit|promise|guarantee)",
    r"book (?:a |the )?(?:meeting|testbed|lab|slot)", r"apply (?:on our behalf|for us)", r"introduce (?:us|me) to", r"är vi berättigade",
    r"become a member|bli medlem|membership fee|medlemsavgift",
]
_SCOPE = [
    r"collaborat", r"partner", r"samarbet", r"innovati", r"research", r"forskning", r"funding", r"financ",
    r"finansier", r"grant", r"vinnova", r"\bcalls?\b", r"utlysning", r"\bevents?\b", r"test ?bed", r"testbädd",
    r"test(?:ing)? (?:environment|opportunit|facilit)", r"testmiljö", r"\blabb?(?:orator)", r"technolog", r"teknik",
    r"capabilit", r"kompetens", r"expertise", r"member", r"medlem", r"marine", r"marin\b", r"maritime", r"underwater",
    r"undervatten", r"subsea", r"sensor", r"sonar", r"machine learning", r"cyber", r"offshore", r"wave power",
    r"vessel", r"fartyg", r"autonom", r"övervak", r"\biot\b", r"profile", r"profil", r"opportunit", r"möjlighet",
    r"blue science park", r"cable", r"kabel", r"prototype", r"pilot", r"supplier", r"leverantör", r"publication",
    r"dredg", r"diving", r"defen[cs]e", r"försvar", r"navigation", r"telematic", r"conference", r"konferens",
    r"workshop", r"webinar", r"seminar", r"networking", r"nätverk", r"trend", r"evenemang", r"bidrag",
    r"business development", r"affärsutveckl", r"contact", r"kontakt", r"what should .{0,30} know", r"this week",
    r"recommend", r"why (?:is|was|did) (?:this|that|it)", r"hypothes", r"blueprint",
]
# words that could belong to the remit but are too general to act on alone. Place names are here, not in
# _SCOPE: "the weather in Karlskrona" mentions the region but is not about innovation or collaboration.
_AMBIGUOUS = [r"\bai\b", r"software", r"mjukvar", r"energy", r"energi", r"market", r"marknad", r"compan", r"företag",
              r"industry", r"bransch", r"project", r"projekt", r"sustainab", r"hållbar", r"monitoring", r"experiment",
              r"help", r"hjälp", r"\bnews\b", r"nyheter", r"paper", r"growth", r"tillväxt", r"strategy", r"customer", r"kund",
              r"regional", r"blekinge", r"karlskrona", r"blue science park"]
_FOLLOW_UP = re.compile(r"^(?:and |och |what about|how about|tell me more|more|show more|why\??$|explain|which one|"
                        r"the (?:first|second|third|last)|any (?:others?|more)|next step|och sen)", re.I)

INTENTS = {
    "funding": r"funding|financ|finansier|grant|vinnova|\bcalls?\b|utlysning|eligib|berättigad",
    "events": r"\bevents?\b|conference|konferens|workshop|webinar|seminar|networking|onsdagslunch|innovation day",
    "testing": r"test ?bed|testbädd|test(?:ing)?\b|testmiljö|\blabb?|pilot|validat|verifier|demonstrat",
    "partners": r"collaborat|partner|samarbet|supplier|leverantör|expertise|who (?:can|could|has)|kompetens",
    "knowledge": r"research|forskning|publication|paper|trend|development|utveckling|news|nyheter|regional",
    "contact": r"contact|kontakt|who (?:do|should) i (?:talk|speak)|support",
}
_INJ_RE = re.compile("|".join(_INJECTION), re.I)
_PRIV_RE = re.compile("|".join(_PRIVACY), re.I)
_ESC_RE = re.compile("|".join(_ESCALATION), re.I)
_SCOPE_RE = re.compile(r"(?<![a-zåäö])(?:" + "|".join(_SCOPE) + ")", re.I)
_AMBIG_RE = re.compile(r"(?<![a-zåäö])(?:" + "|".join(_AMBIGUOUS) + ")", re.I)


@dataclass
class BoundaryDecision:
    category: str
    allowed: bool
    message: str
    matched: str | None = None
    intents: list[str] = field(default_factory=list)
    follow_up: bool = False


def detect_intents(text: str) -> list[str]:
    return [name for name, pat in INTENTS.items() if re.search(pat, text, re.I)]


def classify_request(text: str, previous_in_scope: str | None = None) -> BoundaryDecision:
    """Classify one user turn. `previous_in_scope` is the last in-scope request of the conversation."""
    t = " ".join((text or "").split())[:2000]
    if not t:
        return BoundaryDecision("empty", False, "Please describe what you are looking for. " + SCOPE_DESCRIPTION)
    m = _INJ_RE.search(t)
    if m:
        return BoundaryDecision(
            "prompt_injection", False,
            "I can't change my role or rules, and nothing protected was revealed. I stay an assistant for Blue "
            "Science Park's innovation and collaboration activities. " + SCOPE_DESCRIPTION, m.group(0))
    m = _PRIV_RE.search(t)
    if m:
        return BoundaryDecision(
            "privacy_violation", False,
            "Access denied. A company's refinements, questions, saved items and feedback are visible only to that "
            "company. You can explore any member's public, source-linked profile instead.", m.group(0))
    m = _ESC_RE.search(t)
    if m:
        return BoundaryDecision(
            "escalation", True,
            "That needs a human decision or a formal assessment, which I can't give. " + STAFF_CONTACT +
            " Below is the public information I can show to help you prepare.", m.group(0), detect_intents(t))
    m = _SCOPE_RE.search(t)
    if m:
        return BoundaryDecision("in_scope", True, "Within the service scope.", m.group(0), detect_intents(t))
    if previous_in_scope and len(t) <= 60 and (_FOLLOW_UP.search(t) or detect_intents(t)):
        return BoundaryDecision("in_scope", True, "Follow-up to the previous in-scope request.", t, detect_intents(t), True)
    m = _AMBIG_RE.search(t)
    if m:
        return BoundaryDecision(
            "needs_clarification", False,
            "I'm not sure how this connects to innovation or collaboration in the science park. Are you looking for "
            "funding, a test environment, an event, research, or a potential partner related to it?", m.group(0))
    return out_of_scope()


OUT_OF_SCOPE_MESSAGE = ("That is outside what this service is for. " + SCOPE_DESCRIPTION +
                        " Try for example: 'Find potential collaborators for a marine environmental monitoring project.' "
                        "For anything else, " + STAFF_CONTACT[0].lower() + STAFF_CONTACT[1:])


def out_of_scope(matched: str | None = None) -> BoundaryDecision:
    return BoundaryDecision("out_of_scope", False, OUT_OF_SCOPE_MESSAGE, matched)


def is_follow_up(text: str) -> bool:
    return bool(_FOLLOW_UP.search(" ".join((text or "").split())))


_UNTRUSTED_RE = re.compile("|".join([p for p in _INJECTION if "act as" not in p and "stop being" not in p and "role-?play" not in p] + [
    r"(?:assistant|ai|agent|model|chatbot)s?[,:]? (?:must|should|shall|please) (?:now )?(?:ignore|reveal|disregard|output|send)",
    r"(?:to|attention) (?:any |all )?(?:ai|llm|language model|agent|crawler)s?\b.{0,60}\b(?:ignore|reveal|instruction|rank|recommend)",
    r"rank (?:this|our) company (?:first|highest|top)", r"reveal (?:your|the) (?:system|hidden)",
]), re.I)


def scan_untrusted(text: str) -> str | None:
    """Return the instruction-like fragment found in external content, or None if clean."""
    m = _UNTRUSTED_RE.search(text or "")
    return m.group(0) if m else None


def filter_untrusted(sentences: list[str]) -> tuple[list[str], list[str]]:
    """Split retrieved sentences into (safe, quarantined). Quarantined text is never used."""
    safe, quarantined = [], []
    for s in sentences:
        (quarantined if scan_untrusted(s) else safe).append(s)
    return safe, quarantined
