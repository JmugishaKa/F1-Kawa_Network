# Kawa Network RBAC Matrix (F2)

This is my own copy of the access matrix from the assignment, written out so
a human can check it without reading code. It doesn't actually drive
anything - the real enforcement is in `core/rbac.py`'s `ROLE_RULES`. If this
table and that file ever disagree, trust the code, not this file - that
would mean I forgot to update one of them.

| Role | `GET /api/deliveries/` | `GET /api/plots/` | Farmer national ID | Audit log |
|---|---|---|---|---|
| `field_agent` | own washing station only | own station's plots, full coordinates | masked, last 4 digits | no access |
| `exporter_partner` | all stations | all plots, coarsened coordinates (sector-level) | not present (field omitted) | no access |
| `compliance_auditor` | metadata only - no `weight_kg`, `grade`, `client_ref` | all plots, full coordinates | not present | read |
| unauthenticated | 401/403 | 401/403 | n/a | n/a |

## A few things worth explaining

- **"Coarsened" coordinates** means every plot in the same sector returns the
  exact same point - the sector's centroid, calculated from its own plots
  (see `Sector.centroid()` in models.py). Plots in different sectors return
  different points. I deliberately did NOT just round the lat/lng - I go
  into why in `DECISION_LOG.md`, but short version: rounding doesn't
  actually respect sector boundaries, and the brief specifically rules it
  out for that reason.
- **"Commercial terms"** - the stuff hidden from compliance_auditor - I took
  to mean `weight_kg`, `grade`, and `client_ref`, since those are what
  actually determine or trace a payment. Everything else about a delivery
  (which plot, which station, timestamps, whether it's provenance-verified)
  is metadata, not commercial, so the auditor still sees that.
- **Nested copies.** If a plot or farmer ever shows up nested inside another
  response, the same rule applies to that nested copy too. This falls out
  naturally from how I built it - every serializer calls the same shared
  functions in `core/rbac.py` instead of each one doing its own role check,
  so there's nowhere for the rule to accidentally not apply.
- This matrix only governs reading data (`GET` on plots/deliveries, and
  farmer national ID wherever it shows up). I left who's ALLOWED TO CREATE a
  farmer/plot/delivery out of scope for this retrofit - the brief's matrix
  doesn't say anything about that, so I didn't invent a restriction that
  wasn't asked for. Noted as a deliberate choice in `DECISION_LOG.md`.

## Accounts from `python manage.py seed_rbac_fixtures`

All three use the same password: `GraderPass123!`

| Username | Role | Scoped to |
|---|---|---|
| `field_agent_user` | `field_agent` | the seeded washing station |
| `exporter_user` | `exporter_partner` | n/a (sees everything) |
| `auditor_user` | `compliance_auditor` | n/a (sees everything) |