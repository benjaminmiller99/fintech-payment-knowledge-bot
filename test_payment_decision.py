from datetime import datetime, timezone

from infrai_retrieval import KnowledgeMatch
from payment_knowledge_service import KnowledgeRequest, PaymentEvent, decide


class FixedRetriever:
    def retrieve(self, query: str, collection: str, top_k: int = 4) -> list[KnowledgeMatch]:
        return [KnowledgeMatch("Escalate flagged payments to an approver.", {"policy": "risk-17"})]


def test_high_risk_event_requires_review_and_exposes_no_action() -> None:
    request = KnowledgeRequest(
        question="Can the team release this payment?",
        event=PaymentEvent(
            event_id="evt_1042",
            payment_id="pay_772",
            event_type="payment_flagged",
            amount_minor=250000,
            currency="USD",
            risk_level="high",
            occurred_at=datetime(2026, 9, 6, 9, 30, tzinfo=timezone.utc),
        ),
    )

    result = decide(request, FixedRetriever(), "payments-policy")

    assert result.decision == "manual_review"
    assert result.allowed_actions == []
    assert result.notification.event_id == "evt_1042"
    assert result.sources == ["Escalate flagged payments to an approver."]
