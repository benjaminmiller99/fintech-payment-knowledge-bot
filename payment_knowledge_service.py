"""Typed HTTP service for payment-event knowledge decisions."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from enum import Enum
from typing import Protocol

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from infrai_retrieval import InfraiError, InfraiRetrieval, KnowledgeMatch


class RiskLevel(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"


class PaymentEvent(BaseModel):
    event_id: str = Field(min_length=1)
    payment_id: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    amount_minor: int = Field(ge=0)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    risk_level: RiskLevel
    occurred_at: datetime


class KnowledgeRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)
    event: PaymentEvent


class AuditNotification(BaseModel):
    event_id: str
    decision: str
    reason: str
    recorded_at: datetime


class KnowledgeResponse(BaseModel):
    decision: str
    answer: str
    sources: list[str]
    allowed_actions: list[str]
    notification: AuditNotification


class Retriever(Protocol):
    def retrieve(self, query: str, collection: str, top_k: int = 4) -> list[KnowledgeMatch]:
        """Return ranked policy passages for a domain question."""


def decide(request: KnowledgeRequest, retriever: Retriever, collection: str) -> KnowledgeResponse:
    matches = retriever.retrieve(request.question, collection, top_k=3)
    source_text = [match.text for match in matches]
    if request.event.risk_level is RiskLevel.high:
        decision = "manual_review"
        actions: list[str] = []
        reason = "High-risk payment events require a human approver."
        answer = "Relevant policy context was retrieved; a human approver must decide the next action."
    elif request.event.risk_level is RiskLevel.medium:
        decision = "review_recommended"
        actions = ["open_case", "notify_risk_team"]
        reason = "The event may proceed only through review-oriented actions."
        answer = source_text[0] if source_text else "No matching internal policy passage was found."
    else:
        decision = "knowledge_answer"
        actions = ["acknowledge", "open_case"]
        reason = "The event is low risk, so the retrieved guidance can be returned directly."
        answer = source_text[0] if source_text else "No matching internal policy passage was found."

    notification = AuditNotification(
        event_id=request.event.event_id,
        decision=decision,
        reason=reason,
        recorded_at=datetime.now(timezone.utc),
    )
    return KnowledgeResponse(
        decision=decision,
        answer=answer,
        sources=source_text,
        allowed_actions=actions,
        notification=notification,
    )


app = FastAPI(title="Fintech Payment Knowledge Service")


@app.post("/knowledge/answer", response_model=KnowledgeResponse)
def answer_payment_question(request: KnowledgeRequest) -> KnowledgeResponse:
    retrieval = InfraiRetrieval()
    try:
        return decide(request, retrieval, os.environ["INFRAI_COLLECTION"])
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(status_code=client_status, detail=exc.details) from exc
    finally:
        retrieval.close()
