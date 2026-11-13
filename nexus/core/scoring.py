"""Evidence-aware ranking:  S = 0.35*C + 0.25*O + 0.20*R + 0.20*E   (all components 0..100).

Missing components are NOT imputed. A component that could not be computed (for example no
research records are stored) contributes 0 points, is listed in `missing`, and lowers `coverage`,
which is always shown next to the score. The score expresses strength of fit and evidence. It is
not a probability of commercial success.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from nexus.utils.config import get_settings
from nexus.utils.validators import age_days, clamp

COMPONENTS = ("complementarity", "opportunity", "research", "evidence")
LABELS = {"complementarity": "Capability complementarity", "opportunity": "Opportunity relevance",
          "research": "Research relevance", "evidence": "Evidence quality"}


@dataclass
class ScoreBreakdown:
    complementarity: float | None
    opportunity: float | None
    research: float | None
    evidence: float | None
    weights: dict = field(default_factory=dict)
    final: float = 0.0
    coverage: float = 0.0
    missing: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def default_weights() -> dict[str, float]:
    st = get_settings()
    return {"complementarity": st.w_complementarity, "opportunity": st.w_opportunity,
            "research": st.w_research, "evidence": st.w_evidence}


def combine(complementarity, opportunity, research, evidence, weights: dict | None = None) -> ScoreBreakdown:
    weights = weights or default_weights()
    if abs(sum(weights.values()) - 1.0) > 1e-6:
        raise ValueError("weights must sum to 1")
    values = {"complementarity": complementarity, "opportunity": opportunity, "research": research,
              "evidence": evidence}
    missing = [k for k, v in values.items() if v is None]
    clean = {k: (None if v is None else round(clamp(v), 1)) for k, v in values.items()}
    final = sum(weights[k] * (clean[k] or 0.0) for k in COMPONENTS)
    return ScoreBreakdown(**clean, weights=weights, final=round(final, 1),
                          coverage=round((len(COMPONENTS) - len(missing)) / len(COMPONENTS), 2), missing=missing)


def top_k_relevance(values: list[float], shares=(0.6, 0.25, 0.15)) -> float:
    """Aggregate the best matches; fewer matches than len(shares) simply earn fewer points."""
    best = sorted(values, reverse=True)[: len(shares)]
    return float(sum(s * v for s, v in zip(shares, best)))


def claim_quality(classification: str, n_sources: int, has_url: bool, retrieved_at: datetime | None,
                  now: datetime | None = None, stale_after_days: int | None = None) -> float:
    """Quality 0..1 of one capability claim, driven by how it is evidenced."""
    stale_after_days = stale_after_days or get_settings().stale_after_days
    if classification == "FACT" and has_url:
        base = 1.0 if n_sources >= 2 else 0.8
    elif classification == "USER":
        base = 0.45  # stated by the user, not independently verified
    elif classification == "INFERENCE":
        base = 0.3
    else:
        base = 0.0  # a "fact" without a source is unsupported
    age = age_days(retrieved_at, now)
    if classification == "FACT" and (age is None or age > stale_after_days):
        base *= 0.6  # stale or undated source
    return base
