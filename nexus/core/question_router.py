"""Ask EchoRadar question router: decides, with explicit rules, what kind of question was asked.

route() reads one question and returns a Route of one of these kinds:

  park           about Blue Science Park itself: contact, address, opening hours, staff, membership, what it is
  help           how to use EchoRadar, what a page shows, what a label means
  company        one or more named members (two or more: a comparison)
  apply          how to apply for funding
  count          "how many ..."
  opportunities  funding, events, test environments, research or news, optionally within a period
  partners       who could work on something
  search         subject words without a clear area: records and members closest to the wording
  off_topic      clearly unrelated (poems, weather, recipes)
  unknown        nothing recognised

Safety checks (prompt injection, private data, decisions that need staff) are not made here:
nexus.security.boundary_guard runs first and its refusals are final. The router only reads the
question; answers are assembled from stored records by nexus.core.answer_builder.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta
from difflib import get_close_matches

from nexus.core import taxonomy as tx

# ---- subject areas ------------------------------------------------------------------------------
TOPICS = {
    "funding": r"fund|financ|finansier|grants?\b|bidrag|vinnova|\bcalls?\b|utlysning|investor|pengar|\bmedel\b",
    "events": r"\bevents?\b|evenemang|händelse|conference|konferens|workshop|webinar|seminar|networking|nätverkande|"
              r"meetups?\b|träff|onsdagslunch|innovation day|mässa|happening",
    "testing": r"test ?beds?|testbädd|\btest(?:ing|a|er|s)?\b|testmiljö|\blabb?\b|\blaborator|\bpilot|validat|verifier|demonstrat",
    "knowledge": r"research|forskning|publications?|publikation|papers?\b|studie|stud(?:y|ies)|trends?\b|\bnews\b|nyhet|"
                 r"articles?\b|artikel",
    "partners": r"collaborat|partner|samarbet|supplier|leverantör|expertise|kompetens|who (?:can|could|has|have|does|do|makes?|works?|offers?)|"
                r"which (?:companies|members|firms|organisations|organizations)|vilka (?:företag|medlemmar|bolag)|"
                r"companies (?:that|who|working|doing|with)|members? (?:that|who|working|with)",
}
TOPIC_KINDS = {"funding": ["funding"], "events": ["event"], "testing": ["testbed"], "knowledge": ["research", "news"]}

# ---- Blue Science Park itself -------------------------------------------------------------------
_PARK = r"blue science park|bluesciencepark|\bbsp\b|science park|the park\b|parken|\byou\b|\byour\b|\bni\b|\ber\b"
PARK_TOPICS = {
    "contact": r"contact|kontakt|get in touch|reach (?:you|them|the park|blue science park)|e-?mail|e-?post|phone|telefon|"
               r"ring(?:a)? (?:er|dem)|who (?:do|should|can) i (?:talk|speak|ask)|vem (?:ska|kan) jag (?:prata|kontakta|fråga)",
    "location": r"where (?:is|are|can i find)|located|location of|address|adress|var ligger|var finns|directions|"
                r"how (?:do i|to) get (?:there|to)|hitta (?:hit|dit)|visit(?:ing)? (?:you|the park|blue science park)",
    "hours": r"opening hours|open(?:ing)? times|when (?:are|is) (?:you|it|the park|blue science park) open|öppettider|"
             r"när har ni öppet|är ni öppna",
    "staff": r"who works|\bstaff\b(?! (?:desk|view))|personalen\b|medarbetare|who runs|\bceo\b|\bvd\b",
    "membership": r"become a member|join (?:the park|blue science park|as a member)|membership|medlemskap|bli medlem|medlemsavgift",
    "about": r"what is (?:the )?(?:blue science park|bsp|the park)|vad är (?:blue science park|bsp)|"
             r"about (?:the )?(?:blue science park|bsp|the park)|om blue science park",
}
_PARK_NEEDS_MENTION = {"location", "staff"}  # "where is the test harbour" is not about the park

# ---- help with EchoRadar itself ----------------------------------------------------------------------
_HELP_PREFIX = (r"how (?:do|can|should) (?:i|we) (?:use|read|understand|find|open|get to)|how does|how do|what (?:is|are|does|do)|"
                r"what's|explain|where (?:do|can) i (?:find|see)|hur (?:använder|läser|hittar|fungerar)(?: jag)?|"
                r"vad (?:är|betyder|visar)|förklara")
HELP_SECTIONS = {
    "front": r"front page|latest page|this week page|förstasida",
    "radar": r"(?:opportunity )?radar",
    "dna": r"company (?:dna|profile)|\bdna\b|profile page|profilsida",
    "blueprint": r"(?:innovation )?blueprint",
    "graph": r"(?:connections? )?graph|connection map|nätverkskarta",
    "staff": r"staff (?:desk|view)",
    "overview": r"overview|översikt",
    "ask": r"ask (?:echoradar|echo radar|nexus)",
}
HELP_LABELS = {"FACT": r"facts?\b|fakta", "INFERENCE": r"inferences?\b|inferred|härled", "USER": r"user (?:label|additions?)|\buser\b",
               "HYPOTHESIS": r"hypothes[ie]s"}
_GENERAL_HELP = re.compile(r"^(?:help|hjälp|hi|hello|hej|hallå)[!?. ]*$|what can (?:you|echoradar|echo radar|nexus|i) (?:do|ask)|"
                           r"how does (?:echoradar|echo radar|nexus|this(?: app| site)?|it) work|what (?:is|does) (?:echoradar|echo radar|nexus)\b|vad kan (?:du|jag)|"
                           r"how (?:do|can) i use (?:echoradar|echo radar|nexus|this|the app)", re.I)

# ---- other question shapes ----------------------------------------------------------------------
_COUNT = re.compile(r"how many|hur många|number of|antal(?:et)?\b", re.I)
_APPLY = re.compile(r"how (?:do|can|should|would) (?:i|we|one) apply|how to apply|apply (?:for|to)|application (?:process|form|steps)|"
                    r"ansök|hur söker (?:jag|vi)|söka (?:bidrag|finansiering|medel|pengar|stöd)", re.I)
_OFF_TOPIC = re.compile(r"\bpoem|\bdikt|recipe|recept|\bjokes?\b|skämt|lyrics|weather|\bväder|homework|\bläxa|\bessay|uppsats|"
                        r"capital of|\bmovies?\b|football|fotboll|horoscope|horoskop|tell me a story|bitcoin|crypto|lottery|lotto",
                        re.I)
_CONTACT_WORDS = re.compile(PARK_TOPICS["contact"], re.I)

# ---- periods ------------------------------------------------------------------------------------
_MONTHS = {"january": 1, "februari": 2, "february": 2, "march": 3, "mars": 3, "april": 4, "may": 5, "maj": 5, "june": 6,
           "juni": 6, "july": 7, "juli": 7, "august": 8, "augusti": 8, "september": 9, "october": 10, "oktober": 10,
           "november": 11, "december": 12, "januari": 1}
_MONTH_RE = re.compile(r"(?:\b(?:in|i|during|under|for|för)\s+)?\b(" + "|".join(sorted(_MONTHS, key=len, reverse=True)) + r")\b", re.I)
_CLOSING = re.compile(r"clos|deadline|\bdue\b|sista ansökningsdag|stänger|går ut|last day|ends?\b", re.I)
_NEWEST = re.compile(r"latest|most recent|recent|newest|\bnew\b|senaste|\bnya\b|nyligen", re.I)
_SPAN = re.compile(r"(?:within|in the next|next|inom|kommande|närmaste|nästa)\s+(\d{1,3})\s+"
                   r"(days?|weeks?|months?|dagar|dag|veckor|vecka|månader|månad)", re.I)

# words that say what kind of question it is but not what it is about
_VOCAB = ("fund", "financ", "finansier", "grant", "bidrag", "vinnova", "call", "utlysning", "event", "evenemang", "conferen",
          "konferens", "workshop", "webinar", "semin", "network", "nätverk", "meetup", "träff", "happen", "test", "labb", "lab",
          "pilot", "research", "forskning", "publica", "publika", "paper", "studie", "stud", "trend", "news", "nyhet", "article",
          "artikel", "partner", "collaborat", "samarbet", "compan", "företag", "bolag", "member", "medlem", "organi", "firm",
          "open", "öppn", "clos", "deadline", "stäng", "soon", "snart", "upcoming", "kommande", "next", "nästa", "this",
          "denna", "week", "veck", "month", "månad", "year", "today", "idag", "tomorrow", "imorgon", "latest", "recent",
          "senaste", "newest", "apply", "ansök", "applica", "available", "eligib", "stored", "nexus", "echoradar", "echo", "blue", "science", "park",
          "help", "hjälp", "list", "show", "find", "give", "tell", "need", "want", "look", "search", "sök", "please", "about",
          "more", "info", "opportunit", "möjlighet", "help", "upcoming", "current", "aktuell", "work", "jobba", "arbet",
          "offer", "erbjud", "there", "any", "some", "all", "who", "which", "what", "where", "when", "how", "many",
          "number", "antal", "count", "does", "make", "vilk", "finns", "inom", "within", "days", "dagar", "doing", "has", "have",
          # places: where something is, not what it is about
          "karlskrona", "blekinge", "ronneby", "karlshamn", "sölvesborg", "olofström", "sweden", "sverige", "swedish",
          "region", "local", "nearby")
_STOP = set("""a an the and or of for to in on at by with from into as is are was were be been being am do does did can could
should would will shall may might must i we you he she it they me us my our your their this that these those there here
what which who whom whose when where why how than then so if not no yes any all some each every much many more most
other such only own same too very just also about over under again further once both few nor out up down off per via
och eller att det den de en ett är var som för på av med till från om hur vad vilka vilken vilket när där här jag vi
du ni han hon man sig oss er mig dig kan ska skulle vill har hade finns inte nu också bara mer mest alla något några
""".split())


@dataclass
class Window:
    """A period asked about. `start`/`end` bound future dates (events, deadlines); `period_start` bounds
    past dates (research, news) for periods such as 'this month'."""
    start: datetime
    end: datetime
    label: str
    period_start: datetime
    closing: bool = False  # "closing soon": filter funding by deadline, not by when it is open


@dataclass
class Route:
    kind: str = "unknown"
    topics: list[str] = field(default_factory=list)
    park: str | None = None
    companies: list[int] = field(default_factory=list)
    window: Window | None = None
    newest: bool = False
    count: bool = False
    caps: list[str] = field(default_factory=list)
    content: list[str] = field(default_factory=list)
    help: str | None = None  # a section id, a label name or "general"
    asks_contact: bool = False
    source: str = "rules"  # rules | gemini

    @property
    def kinds(self) -> list[str]:
        return [k for t in self.topics for k in TOPIC_KINDS.get(t, [])]

    @property
    def has_subject(self) -> bool:
        return bool(self.caps or self.content)

    def summary(self) -> dict:
        return {"type": self.kind, "source": self.source, "topics": self.topics, "park": self.park,
                "help": self.help, "period": self.window.label if self.window else None, "count": self.count}


def norm(text: str) -> str:
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = re.sub(r"[–—_/\\|]", " ", t)
    t = re.sub(r"[^\w\såäöéü&+-]", " ", t)
    return " ".join(t.split())


# ---- member names ------------------------------------------------------------------------------
_LEGAL = re.compile(r"\b(?:ab|aktiebolag|as|oy|gmbh|ltd|inc|corp|group|i sverige)\b")
_GENERIC_FIRST = {"blekinge", "region", "baltic", "ocean", "karlskrona", "marine", "hi", "dnv", "3d", "ge", "mj", "c", "compani"}
# well-known English names and abbreviations of Swedish public bodies in the directory, by slug
KNOWN_ALIASES = {"blekinge-tekniska-hogskola": ["BTH", "Blekinge Institute of Technology"],
                 "forsvarsmakten": ["Swedish Armed Forces"], "kustbevakningen": ["Swedish Coast Guard", "Coast Guard"],
                 "energimyndigheten": ["Swedish Energy Agency"], "forsakringskassan": ["Swedish Social Insurance Agency"],
                 "lansstyrelsen-blekinge": ["County Administrative Board of Blekinge"],
                 "karlskrona-kommun": ["Karlskrona Municipality"]}
_BOUND_L, _BOUND_R = r"(?<![\wåäö])", r"(?![\wåäö])"


def _variant_pattern(variant: str, camel: bool = False) -> str:
    tokens = variant.split()
    out = re.escape(tokens[0])
    for tok in tokens[1:]:
        sep = r"\s*" if camel else (r"[\s-]?" if len(tok) <= 2 or tok.isdigit() else r"[\s-]+")
        out += sep + re.escape(tok)
    return _BOUND_L + out + _BOUND_R


@dataclass
class CompanyIndex:
    names: dict[int, str]
    patterns: list[tuple[re.Pattern, int]]
    single: dict[str, int]  # one-word names, for small typos ("embededart")

    @classmethod
    def build(cls, companies: list[tuple[int, str, list[str]]]) -> "CompanyIndex":
        names = {cid: name for cid, name, _ in companies}
        firsts: dict[str, list[int]] = {}
        for cid, name, _ in companies:
            first = norm(name).split()[0] if norm(name) else ""
            firsts.setdefault(first, []).append(cid)
        patterns, single = [], {}
        for cid, name, aliases in companies:
            base = norm(name)
            variants = {base, _LEGAL.sub("", base).strip(), norm(name.split("–")[0]), norm(name.split(" - ")[0])}
            variants |= {norm(a) for a in aliases or [] if a and not str(a).lower().startswith("http")}
            first = base.split()[0] if base else ""
            if len(base.split()) > 1 and len(first) >= 5 and first not in _GENERIC_FIRST and len(firsts.get(first, [])) == 1:
                variants.add(first)  # "Kingspan" for "Kingspan BAGA"
            for v in {v for v in variants if len(v) >= 2}:
                patterns.append((re.compile(_variant_pattern(v), re.I), cid, len(v)))
            camel = re.sub(r"(?<=[a-zåäö])(?=[A-ZÅÄÖ])", " ", name.split("–")[0].strip())
            if camel != name.split("–")[0].strip() and " " not in name.split("–")[0].strip():
                patterns.append((re.compile(_variant_pattern(norm(camel), camel=True), re.I), cid, len(base)))
            if " " not in base and len(base) >= 6:
                single[base] = cid
        patterns.sort(key=lambda p: -p[2])
        return cls(names, [(p, cid) for p, cid, _ in patterns], single)

    def find(self, text: str) -> list[int]:
        t = norm(text)
        taken: list[tuple[int, int]] = []
        found: list[tuple[int, int]] = []
        for pat, cid in self.patterns:  # longest names first; a span is used once
            for m in pat.finditer(t):
                if any(m.start() < b and a < m.end() for a, b in taken):
                    continue
                taken.append((m.start(), m.end()))
                found.append((m.start(), cid))
        if not found:  # one small typo in a one-word name ("embededart"), but never an ordinary word ("sensor")
            for tok in re.findall(r"[\wåäö]{6,}", t):
                if tok in self.single or tok in _STOP or tok.startswith(_VOCAB) or tx.detect_capabilities(tok):
                    continue
                hit = get_close_matches(tok, list(self.single), n=1, cutoff=0.85)
                # a word that is the start of a name ("sensor" / "Sensora") is a word, not a typo
                if hit and abs(len(hit[0]) - len(tok)) <= 1 and hit[0][0] == tok[0] and not hit[0].startswith(tok):
                    found.append((t.find(tok), self.single[hit[0]]))
        out: list[int] = []
        for _, cid in sorted(found):
            if cid not in out:
                out.append(cid)
        return out

    def strip(self, text: str) -> str:
        """The question without the company names (so names are not read as subject words)."""
        t = norm(text)
        for pat, _ in self.patterns:
            t = pat.sub(" ", t)
        return t


# ---- periods ------------------------------------------------------------------------------------
def _month_start(d: datetime) -> datetime:
    return d.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def _add_months(d: datetime, n: int) -> datetime:
    y, m = divmod(d.month - 1 + n, 12)
    return d.replace(year=d.year + y, month=m + 1, day=1)


def parse_window(text: str, now: datetime) -> Window | None:
    t = (text or "").lower()
    day = now.replace(hour=0, minute=0, second=0, microsecond=0)
    closing = bool(_CLOSING.search(t))
    monday = day - timedelta(days=day.weekday())

    def w(start, end, label, period_start=None):
        return Window(start, end, label, period_start or start, closing)

    if re.search(r"\btoday\b|\bidag\b|\bi dag\b", t):
        return w(now, day + timedelta(days=1), "today", day)
    if re.search(r"tomorrow|imorgon|i morgon", t):
        return w(day + timedelta(days=1), day + timedelta(days=2), "tomorrow")
    if re.search(r"this week|denna vecka|den här veckan|i veckan", t):
        return w(now, monday + timedelta(days=7), "this week", monday)
    if re.search(r"next week|nästa vecka|kommande vecka", t):
        return w(monday + timedelta(days=7), monday + timedelta(days=14), "next week")
    if re.search(r"this month|denna månad|den här månaden|i månaden", t):
        return w(now, _add_months(_month_start(day), 1), "this month", _month_start(day))
    if re.search(r"next month|nästa månad|kommande månad", t):
        start = _add_months(_month_start(day), 1)
        return w(start, _add_months(start, 1), f"{start:%B %Y}")
    m = _SPAN.search(t)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = n * (30 if unit.startswith(("month", "mån")) else 7 if unit.startswith(("week", "veck")) else 1)
        return w(now, day + timedelta(days=days + 1), f"the next {n} {unit}", day - timedelta(days=days))
    if re.search(r"this year|i år\b|detta år", t):
        return w(now, day.replace(month=1, day=1, year=day.year + 1), f"the rest of {day.year}", day.replace(month=1, day=1))
    if re.search(r"next year|nästa år", t):
        start = day.replace(month=1, day=1, year=day.year + 1)
        return w(start, start.replace(year=start.year + 1), str(start.year))
    for m in _MONTH_RE.finditer(t):
        name = m.group(1).lower()
        if name == "may" and not re.match(r"(?:in|i|during|under|for|för)\s", m.group(0)):
            continue  # "may I ..." is not the month
        month = _MONTHS[name]
        year = day.year if month >= day.month else day.year + 1
        start = datetime(year, month, 1)
        return w(max(start, now), _add_months(start, 1), f"{start:%B %Y}", start)
    if re.search(r"\bsoon\b|\bsnart\b|coming up|upcoming|kommande|närmaste tiden|shortly", t):
        return w(now, day + timedelta(days=31), "the next 30 days", day - timedelta(days=30))
    return None


# ---- the router ---------------------------------------------------------------------------------
def content_words(text: str) -> list[str]:
    """Subject words: what is left once question words, area words and period words are removed."""
    out = []
    for tok in re.findall(r"[\wåäö]+", text.lower()):
        if len(tok) < 3 or tok in _STOP or tok.isdigit() or tok in _MONTHS or tok.startswith(_VOCAB):
            continue
        out.append(tok)
    return out


def _help_target(t: str) -> str | None:
    if _GENERAL_HELP.search(t):
        return "general"
    for key, pat in HELP_SECTIONS.items():
        if re.search(rf"(?:{_HELP_PREFIX})\s*(?:the |a |an |my |this |your )?(?:{pat})\b", t, re.I):
            return key
    for key, pat in HELP_LABELS.items():
        if re.search(rf"(?:{_HELP_PREFIX})\s*(?:the |a |an )?(?:label )?(?:{pat})", t, re.I):
            return key
    return None


def route(text: str, index: CompanyIndex | None, now: datetime) -> Route:
    t = " ".join((text or "").split())
    low = t.lower()
    companies = index.find(t) if index else []
    rest = index.strip(t) if index else norm(t)
    topics = [k for k, pat in TOPICS.items() if re.search(pat, low, re.I)]
    caps = [c for c, _ in tx.detect_capabilities(rest)]
    r = Route(topics=topics, companies=companies, window=parse_window(low, now), newest=bool(_NEWEST.search(low)),
              count=bool(_COUNT.search(low)), caps=caps, content=content_words(rest),
              asks_contact=bool(_CONTACT_WORDS.search(low)))
    if not r.topics and not caps and _OFF_TOPIC.search(low):  # "a poem about Njord X" is still a poem
        return replace(r, kind="off_topic")
    h = _help_target(low)
    if h and not companies:
        return replace(r, kind="help", help=h)
    if companies:
        return replace(r, kind="company")
    park_mentioned = bool(re.search(_PARK, low, re.I))
    for key, pat in PARK_TOPICS.items():
        # "where can you find funding" is about funding, not about the park's address
        # ("who works at" reads like a partner question, so that topic does not count here)
        if re.search(pat, low, re.I) and (key not in _PARK_NEEDS_MENTION
                                          or (park_mentioned and not set(r.topics) - {"partners"})):
            return replace(r, kind="park", park=key)
    if _APPLY.search(low):
        return replace(r, kind="apply", topics=sorted(set(r.topics) | {"funding"}))
    if r.count:
        return replace(r, kind="count")
    if any(k in TOPIC_KINDS for k in r.topics):
        return replace(r, kind="opportunities")
    if "partners" in r.topics:
        return replace(r, kind="partners")
    if r.has_subject:
        return replace(r, kind="search")
    return r


def merge_follow_up(current: Route, previous: Route) -> Route:
    """A short follow-up ("and events?", "what about next month") keeps the subject of the previous question."""
    merged = replace(current,
                     companies=current.companies or previous.companies,
                     caps=current.caps or previous.caps,
                     content=current.content or previous.content,
                     topics=current.topics or previous.topics,
                     window=current.window or (previous.window if not current.topics else None))
    if merged.kind == "unknown":
        merged = replace(merged, kind=previous.kind if previous.kind not in ("help", "park", "off_topic", "unknown") else "search")
    if merged.kind in ("search", "unknown") and any(k in TOPIC_KINDS for k in merged.topics):
        merged = replace(merged, kind="opportunities")
    return merged
