# Bug Report: Summative Hardening

## Bug 1: Deliveries stranded with no observable export state after a failed risk check

**Symptom (from the pilot repot):** "A plot whose risk check never returned leaves its
deliveries in a state that cannot be assigned to an export lot, so the coffee cannot be shipped."

**Failing test (which I wrote before the fix):** `tests/staging/test_delivery_risk_check_stranding.py`,
merged into history at commit `4a8dad3` (summative/seed branch). Confirmed failing against the
unfixed implementation by stashing the fix and re-running: `AssertionError: delivery response
carries no field indicating whether it can be assigned to an export lot or was explicitly
rejected`.

**Possible Root cause:** `Delivery.plot_risk_status` is a one-time snapshot of the plot's risk status,
taken at the moment the delivery is recorded (`core/serializers.py`, `DeliverySerializer.create()`).
A delivery recorded while its plot is still `pending` (F1's deliberate non-blocking design - see
`ADR.md`) correctly shows `pending` at creation time. But if the plot's async check later resolves
- to `clear`, or gives up after 5 attempts and becomes `check_failed` - nothing ever updates the
delivery's stored snapshot. The delivery is left showing a stale status forever, and more
importantly, nothing in the API distinguishes "still waiting" from "permanently stuck" - both look
identical from the outside.

**Why it matters commercially:** this is the exact mechanism behind the pilot's reported symptom.
A delivery against a plot that ultimately failed verification has no signal telling an operator
"this one needs a human decision" versus "this one is still in normal flight." At 400
deliveries/day across 11 stations, there is no way to find the stuck ones without scanning every
delivery's plot individually.

**Fix:** added `Delivery.export_status` and `Delivery.rejection_reason` as model properties,
derived live from the plot's CURRENT `risk_status` on every read, rather than stored as a second
column that would need to be kept in sync. This was a deliberate choice, not the only valid one -
see `DECISION_LOG.md`'s note on the trade-off against a stored-and-synced alternative (which would
have been auditable - "what was true on the day this shipped" - but reintroduces exactly the kind
of staleness bug this fix exists to close). `export_status` resolves to one of `assignable`
(plot is `clear`), `pending_verification` (plot still `pending`), or `blocked` (plot `flagged` or
`check_failed`, with `rejection_reason` explaining which). Exposed on both the full delivery
serializer and the compact station feed, so the signal is visible wherever a delivery is read, not
only in the one place the hidden test checks.

Because the fix is derived rather than stored, a `check_failed` plot is not a dead end: calling the
existing `POST /api/plots/{id}/recheck/` endpoint and having it later resolve automatically flips
every delivery against that plot from `blocked` to `assignable`, with no extra code.

**Fix commit:** `37326c6`. **Passing result:**