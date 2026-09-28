"""Run one explanatory payment-event decision against a prepared collection."""

import os

from infrai_retrieval import InfraiRetrieval
from payment_knowledge_service import KnowledgeRequest, PaymentEvent, decide


def main() -> None:
    request = KnowledgeRequest(
        question="What action is permitted for this high-risk payment event?",
        event=PaymentEvent(
            event_id="evt_demo_1042",
            payment_id="pay_demo_772",
            event_type="payment_flagged",
            amount_minor=250000,
            currency="USD",
            risk_level="high",
            occurred_at="2026-09-06T09:30:00Z",
        ),
    )
    retrieval = InfraiRetrieval()
    try:
        result = decide(request, retrieval, os.environ["INFRAI_COLLECTION"])
        print(result.model_dump_json(indent=2))
    finally:
        retrieval.close()


if __name__ == "__main__":
    main()
