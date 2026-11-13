"""Evaluation: NEXUS complementarity ranking vs the similarity-only baseline, plus coverage,
freshness and ranking-differentiation metrics. Everything is computed from stored data at call
time; nothing here is a hard-coded result."""
from __future__ import annotations

import itertools
import json
from datetime import datetime

import numpy as np
from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.core import matching_engine as me
from nexus.database import repository as repo
from nexus.database.models import CollaborationHypothesis, Company, Event, Evidence, NewsUpdate, FundingOpportunity, Recommendation, ResearchPublication, Testbed
from nexus.utils.config import DATA_DIR, get_settings
from nexus.utils.validators import age_days, is_valid_url, utcnow

LABELS_PATH = DATA_DIR / "eval" / "labelled_pairs.json"


def load_labels(path=LABELS_PATH) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def precision_at_k(labels_in_rank_order: list[int], k: int) -> float:
    top = labels_in_rank_order[:k]
    return sum(1 for x in top if x >= 1) / len(top) if top else 0.0


def recall_at_k(labels_in_rank_order: list[int], k: int) -> float:
    total = sum(1 for x in labels_in_rank_order if x >= 1)
    return sum(1 for x in labels_in_rank_order[:k] if x >= 1) / total if total else 0.0


def ndcg_at_k(labels_in_rank_order: list[int], k: int) -> float:
    def dcg(xs):
        return sum((2 ** x - 1) / np.log2(i + 2) for i, x in enumerate(xs[:k]))
    ideal = dcg(sorted(labels_in_rank_order, reverse=True))
    return float(dcg(labels_in_rank_order) / ideal) if ideal else 0.0


def spearman(a: list[float], b: list[float]) -> float:
    def ranks(x):
        order = np.argsort(x)
        r = np.empty(len(x))
        r[order] = np.arange(len(x))
        x = np.asarray(x)
        for v in np.unique(x):  # average ranks for ties
            r[x == v] = r[x == v].mean()
        return r
    ra, rb = ranks(a), ranks(b)
    if ra.std() == 0 or rb.std() == 0:
        return 0.0
    return float(np.corrcoef(ra, rb)[0, 1])


def rank_metrics(scores: list[float], labels: list[int]) -> dict:
    order = sorted(range(len(scores)), key=lambda i: (-scores[i], i))
    ranked = [labels[i] for i in order]
    return {"precision@5": round(precision_at_k(ranked, 5), 2), "precision@10": round(precision_at_k(ranked, 10), 2),
            "recall@10": round(recall_at_k(ranked, 10), 2), "ndcg@10": round(ndcg_at_k(ranked, 10), 2),
            "mean_label_top5": round(float(np.mean(ranked[:5])), 2) if ranked else 0.0,
            "spearman": round(spearman(scores, labels), 2)}


def compare_with_baseline(profiles: list[me.CompanyProfile], slug_to_id: dict[str, int], labels: dict | None = None) -> dict:
    """Score every labelled pair with both methods and compute ranking metrics."""
    labels = labels or load_labels()
    by_id = {p.id: p for p in profiles}
    idx = {p.id: i for i, p in enumerate(profiles)}
    sim = me.similarity_matrix(profiles)
    rows, skipped = [], []
    for pair in labels["pairs"]:
        a, b = slug_to_id.get(pair["a"]), slug_to_id.get(pair["b"])
        if a is None or b is None or a not in by_id or b not in by_id:
            skipped.append(f"{pair['a']} / {pair['b']}")
            continue
        comp = me.complementarity_score(me.pair_links(by_id[a], by_id[b]))
        rows.append({"a": by_id[a].name, "b": by_id[b].name, "label": pair["label"], "rationale": pair["rationale"],
                     "nexus_complementarity": comp, "baseline_similarity": round(float(sim[idx[a], idx[b]]), 3)})
    y = [r["label"] for r in rows]
    return {"n_pairs": len(rows), "n_relevant": sum(1 for v in y if v >= 1), "skipped": skipped, "rows": rows,
            "nexus": rank_metrics([r["nexus_complementarity"] for r in rows], y) if rows else {},
            "baseline": rank_metrics([r["baseline_similarity"] for r in rows], y) if rows else {},
            "labelled_by": labels.get("labelled_by"), "caveat": labels.get("caveat")}


def evidence_coverage(s: Session) -> dict:
    claims = repo.all_claims(s)
    facts = [c for c in claims if c.classification == "FACT"]
    ok = [c for c in facts if c.evidence and is_valid_url(c.evidence.source_url) and c.evidence.evidence_text]
    hyps = list(s.scalars(select(CollaborationHypothesis)))
    full = [h for h in hyps if h.verification.get("checks", {}).get("claims_used")
            and h.verification["checks"]["claims_with_source"] == h.verification["checks"]["claims_used"]]
    with_r = [h for h in hyps if h.research_ids]
    with_f = [h for h in hyps if h.funding_ids]
    return {"fact_claims": len(facts), "fact_claims_with_url_and_excerpt": len(ok),
            "profile_coverage": round(len(ok) / len(facts), 3) if facts else None,
            "inferences": sum(1 for c in claims if c.classification == "INFERENCE"),
            "user_claims": sum(1 for c in claims if c.classification == "USER"),
            "hypotheses": len(hyps), "hypotheses_fully_sourced": len(full),
            "recommendation_coverage": round(len(full) / len(hyps), 3) if hyps else None,
            "hypotheses_with_research": len(with_r), "hypotheses_with_open_funding": len(with_f)}


def freshness(s: Session, now: datetime | None = None) -> dict:
    now = now or utcnow()
    limit = get_settings().stale_after_days
    out = {}
    for name, col in (("company evidence", Evidence.retrieved_at), ("research (OpenAlex)", ResearchPublication.retrieved_at),
                      ("funding (Vinnova)", FundingOpportunity.retrieved_at), ("test environments", Testbed.retrieved_at),
                      ("events", Event.retrieved_at), ("news", NewsUpdate.retrieved_at)):
        ages = [age_days(t, now) for t in s.scalars(select(col)) if t is not None]
        out[name] = {"records": len(ages), "newest_days": round(min(ages), 1) if ages else None,
                     "oldest_days": round(max(ages), 1) if ages else None,
                     "stale": sum(1 for a in ages if a > limit), "stale_limit_days": limit}
    return out


def ranking_differentiation(s: Session, top_k: int = 5) -> dict:
    """How different are the personalised top-k lists? Lower overlap = more personalised."""
    lists: dict[int, set] = {}
    for rec in s.scalars(select(Recommendation).where(Recommendation.rank <= top_k)):
        lists.setdefault(rec.company_id, set()).add(rec.target_id)
    ids = list(lists)
    overlaps = [len(lists[a] & lists[b]) / len(lists[a] | lists[b]) for a, b in itertools.combinations(ids, 2)]
    tops = {rec.company_id: rec.target_id for rec in s.scalars(select(Recommendation).where(Recommendation.rank == 1))}
    return {"companies_with_recommendations": len(ids), "companies_total": s.query(Company).count(),
            "mean_jaccard_overlap_top_k": round(float(np.mean(overlaps)), 3) if overlaps else None,
            "identical_list_pairs": sum(1 for o in overlaps if o == 1.0), "pairs_compared": len(overlaps),
            "distinct_top1": len(set(tops.values())), "top_k": top_k}
