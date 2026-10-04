# Kawa Network RBAC Matrix (for F2)


## Notes

- **Coarsened coordinates** (exporter_partner) means: every plot in the same
  administrative sector returns the same point (that sector's centroid,
  computed from its own plots - check this in `Sector.centroid()` and
  `DECISION_LOG.md`), and plots in different sectors return different
  points.

- **"Commercial terms"** (I excluded it from the compliance_auditor delivery view)
  means `weight_kg`, `grade`, and `client_ref` - anything that determines or
  traces payment. 

- **Nested copies.** a plot or farmer appears nested inside another
  response, the same role-based rule applies to the nested copy - enforced
  because serializers call the shared `core/rbac.py` helpers rather than
  each hand-rolling their own check.

- This table governs `GET /api/plots/` and `GET /api/deliveries/` (list and
  retrieve) plus farmer national ID visibility wherever it's serialized.
  
  Write actions (registering a farmer/plot/delivery) and the F1 risk-check
  workflow are intentionally out of this matrix's scope for F2 - see
  `DECISION_LOG.md`.

## Seeded accounts (`python manage.py seed_rbac_fixtures`)

All three share this password: `GraderPass123!`

| Username | Role | Scoped to |
|---|---|---|
| `field_agent_user` | `field_agent` | the seeded washing station |
| `exporter_user` | `exporter_partner` | n/a (sees all) |
| `auditor_user` | `compliance_auditor` | n/a (sees all) |