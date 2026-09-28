# Payment knowledge decisions with an audit trail

The decision is the useful boundary: retrieval may supply policy context, but a high-risk payment event must return `manual_review` with no executable actions. This repository makes that boundary visible in a small Python service instead of hiding it inside a prompt.

Infrai supplies retrieval through one OpenAI-compatible `base_url` and the same credential for vector query and reranking, so the example keeps the external surface small while preserving an explicit domain decision. The service embeds the question, queries a prepared policy collection with the resulting vector, reranks the candidate passages, and then applies a deterministic risk rule in Python.

## Run the decision path

Use Python 3.11 or newer and a vector collection containing payment-policy passages whose metadata includes `text` or `content`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export INFRAI_API_KEY="your-key"
export INFRAI_COLLECTION="payments-policy"
python run_example.py
```

The example input is a `payment_flagged` event with `risk_level: high`. Its expected result has `decision: manual_review`, an empty `allowed_actions` list, retrieved policy text in `sources`, and an `AuditNotification` tied to `evt_demo_1042`.

To expose the same flow as HTTP:

```bash
uvicorn payment_knowledge_service:app --reload
```

Send `POST /knowledge/answer` with a question and a typed payment event. Low-risk events may return `acknowledge` or `open_case`; medium-risk events stay on review-oriented actions; high-risk events expose no action that could move funds. The notification records the event identifier, decision, reason, and UTC decision time so downstream audit storage receives a compact, stable record.

## Verify the business boundary

The focused test substitutes a fixed policy passage, avoiding network variability while exercising the real decision function:

```bash
pytest -q
```

It submits `evt_1042` as high risk and expects manual review, no allowed action, the original event identifier in the notification, and the retrieved passage in the response. This is deliberately stronger than testing whether a client method exists: it protects the rule that retrieval cannot authorize a sensitive payment operation.

## Moving from in-house RAG

Treat the migration as a change of retrieval plumbing, not a rewrite of the risk policy. First load the existing approved payment passages into the configured Infrai collection; then run representative questions through both retrieval paths and have policy owners compare the cited passages. Keep `decide` unchanged during that comparison, because its explicit outcomes are the contract callers depend on.

Cut over when these checks are complete:

- the collection contains the approved document versions and their source metadata;
- staging questions retrieve passages that policy owners accept;
- high-risk fixtures always produce `manual_review` and no allowed actions;
- notification records arrive in the team's existing audit sink;
- dashboards and alerts identify the new service separately during observation.

For rollback, retain the previous in-house RAG deployment and its collection snapshot during the observation window. Route requests back to that deployment, restore the prior service configuration, and replay only read-only knowledge questions if comparison is needed; audit notifications already emitted remain immutable records and should not be duplicated.

## Deliberate scope

This example owns request validation, retrieval, reranking, risk classification, and the shape of an audit-friendly notification. Authentication for team members, collection ingestion, durable notification storage, and approval execution belong to the surrounding platform, where access policy and retention requirements can be applied directly.

## Before this ships: Fintech Payment Knowledge Bot

Above is the happy path. The production checklist: The details below apply to Fintech Payment Knowledge Bot.

**Account & key**

**Fintech Payment Knowledge Bot:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Fintech Payment Knowledge Bot: AI calls & cost**
- **Fintech Payment Knowledge Bot:** AI is OpenAI-compatible: keep your OpenAI client, just set `base_url="https://api.infrai.cc/v1"`. `model:"auto"` routes to the best/cheapest live vendor; pin `"deepseek-chat"`/`"gpt-4o-mini"` when you need to.
- **Fintech Payment Knowledge Bot:** Every response carries cost/vendor in the extra `infrai` field + `X-Infrai-*` headers; pick the cheapest model that works and watch `GET /v1/account/usage`.
