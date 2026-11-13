"""Privacy layer: public company information vs private per-company data.

Public  = company profile claims derived from public sources (visible to everyone, with sources).
Private = a company's questions, notes and feedback (PrivateInteraction, UserFeedback).

Every read of private data goes through these functions and requires the acting company to be the
owner. Authentication itself is SIMULATED in the prototype (the user picks "acting as" in the
sidebar); the authorisation check below is real and is what a real identity provider would call.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from nexus.database.models import PrivateInteraction, UserFeedback


class PrivacyError(PermissionError):
    pass


def assert_owner(acting_company_id: int | None, target_company_id: int) -> None:
    if acting_company_id is None:
        raise PrivacyError("Access denied: no company context. Private data requires an identified company.")
    if int(acting_company_id) != int(target_company_id):
        raise PrivacyError("Access denied: private data is only visible to the company that owns it.")


def record_interaction(s: Session, acting_company_id: int | None, kind: str, text: str, outcome: str | None = None):
    if acting_company_id is None:
        return None  # anonymous visitors leave no private trail
    row = PrivateInteraction(company_id=acting_company_id, kind=kind, text=text[:4000], outcome=outcome)
    s.add(row)
    s.flush()
    return row


def get_private_interactions(s: Session, acting_company_id: int | None, target_company_id: int) -> list[PrivateInteraction]:
    assert_owner(acting_company_id, target_company_id)
    return list(s.scalars(select(PrivateInteraction).where(PrivateInteraction.company_id == target_company_id)
                          .order_by(PrivateInteraction.created_at.desc())))


def get_feedback(s: Session, acting_company_id: int | None, target_company_id: int) -> list[UserFeedback]:
    assert_owner(acting_company_id, target_company_id)
    return list(s.scalars(select(UserFeedback).where(UserFeedback.company_id == target_company_id)
                          .order_by(UserFeedback.created_at.desc())))


def add_feedback(s: Session, acting_company_id: int | None, hypothesis_key: str, rating: int, comment: str = ""):
    if acting_company_id is None:
        raise PrivacyError("Select the company you are acting as before leaving feedback.")
    if not 1 <= int(rating) <= 5:
        raise ValueError("rating must be 1..5")
    row = UserFeedback(company_id=acting_company_id, hypothesis_key=hypothesis_key, rating=int(rating),
                       comment=(comment or "")[:2000] or None)
    s.add(row)
    s.flush()
    return row


def aggregate_feedback(s: Session) -> dict:
    """Anonymous aggregate for the evaluation page: no company or comment is exposed."""
    ratings = list(s.scalars(select(UserFeedback.rating)))
    return {"n": len(ratings), "mean": round(sum(ratings) / len(ratings), 2) if ratings else None}
