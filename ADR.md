# ADR-001: Record deliveries immediately; verify provenance asynchronously

**Status:** Accepted (F1) · **Deciders:** MVP developer · **Date:** Week 3

## Context

Emmanuel records ~400 deliveries a day at one station, on a phone over 2G, with farmers queued at the scale. The external risk registry takes 2-40 seconds per call and is down for hours at a time. Patrick needs traceable data reaching buyers; Jeanne needs every farmer paid correctly the same day.

If registering a plot or recording a delivery waited on the registry, Emmanuel's screen would freeze for up to 40 seconds, or fail outright during an outage.

## Decision

**The registry never sits in the request path.** Registering a plot writes it with `risk_status = pending`, returns `201` at once, and queues a Celery task (Redis broker). The task calls the registry, writes one `RiskCheckAttempt` row per call, and sets the plot to `clear` or `flagged`. Failures retry with exponential backoff (1, 2, 4, 8 minutes); after 5 failed attempts the plot becomes `check_failed`. Every delivery stores a snapshot of the plot's risk status at the moment it was recorded (`plot_risk_status`), exposed as `provenance_verified`.

Queueing itself is best-effort: if Redis is down, the plot is still saved and stays `pending`. `manage.py requeue_pending_checks` or `POST /api/plots/<id>/recheck/` picks it up later.

## What happens to a plot whose check never succeeds

Decision: **it keeps delivering, and its deliveries are visibly unverified.**

| Plot status | Can deliveries be recorded? | Marked `provenance_verified`? |
|---|---|---|
| `pending` | Yes | No |
| `check_failed` (registry unreachable) | Yes | No |
| `clear` | Yes | Yes |
| `flagged` (recently cleared land) | **No** - `409 plot_flagged` | n/a |

Reasoning: an outage of someone else's service must not stop a farmer being weighed or paid (Emmanuel, Jeanne). But "unknown" is not "safe", so an unverified delivery is stored honestly rather than dressed up as verified, and Patrick's buyer-facing traceability data can filter on `provenance_verified`. A registry *answer* of "flagged" is different from no answer, so that one blocks.

Consequences I accept: a plot later found `flagged` may already have unverified deliveries on record. They are not deleted (the weighing happened and the farmer was paid); they are the review list. `check_failed` plots need a human or a scheduled job to call `recheck` once the registry is back. What to do about the coffee already bought is a compliance-policy question for F2, not an API one.

## What it improves

- **Latency:** plot registration measured at ~0.1 s with a 3-4 s registry call happening in the background.
- **Availability:** registry outages degrade verification, not recording.
- **Auditability:** every registry attempt is stored (`GET /api/plots/<id>/risk-attempts/`), and each delivery keeps the risk status it was recorded under.

## What it makes harder

- Two moving parts to run (Redis + worker) instead of one process.
- Eventual consistency: a plot's status changes after the response, so clients must not assume `pending` is final.
- Data quality now has a third state. Anything downstream (payments, exports) must decide what "unverified" means; the field is there, the policy is not.
- Duplicate or concurrent checks are possible in theory; the task is idempotent (a decided plot is never re-checked), which makes that harmless.

## Who benefits most, and which NFRs

**Emmanuel benefits most**: nothing he does waits on the registry. Jeanne benefits second (payment is never blocked by an outage). Patrick is served partially: traceability data flows immediately but carries an honest verified/unverified flag rather than a guarantee.

Helps: **performance (latency), availability, resilience**. Stresses: **data integrity / traceability** and **operability** (a queue and a worker to monitor).

## Performance feature (Task 4)

I chose the **cursor-paginated delivery feed** (`GET /api/deliveries/`), not a cached price schedule. It solves Emmanuel's problem first because his is the one that hurts: the feed is read constantly at harvest peak on 2G, and it grows by ~400 rows a day. The price schedule is a handful of rows that change once a season; it is already cheap, so caching it would add invalidation risk for no user-visible gain. `GET /api/price-schedule/` exists and is uncached.

Feed design choices: cursor pagination (no `COUNT(*)`, no skipped or repeated rows while new deliveries land mid-scroll), 25 rows per page by default with `page_size` up to 100, a compact row (7 short fields), and one SQL query per page via `select_related`, asserted in a test.

## Alternatives considered

- **Block on the registry:** simplest, fails the case (40 s freezes, outages stop the station).
- **Block deliveries until a plot is `clear`:** best for traceability, but Emmanuel could not weigh a farmer whose plot was registered ten minutes ago; rejected.
- **Threads or in-process background work instead of Celery:** no extra service, but tasks are lost on restart and there is no retry or back-off. Not survivable for later stages.
- **Offset pagination:** simpler, but slower on deep pages and unstable while rows are inserted.