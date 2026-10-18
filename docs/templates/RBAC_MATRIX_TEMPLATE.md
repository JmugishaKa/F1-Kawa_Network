# RBAC Matrix Template

Use this as the starting point for `docs/RBAC_MATRIX.md` in `F2`. It documents your role model in
prose for a human grader. The automated matrix checks do not parse this file — they call your
`seed_rbac_fixtures` management command directly, per the
[F2 Contract](autograding/F2_CONTRACT.md).

## The access matrix

| Role | `GET /api/deliveries/` | `GET /api/plots/` | Farmer national ID | Audit log |
|---|---|---|---|---|
| `field_agent` | own washing station only | own station's plots, full coordinates | masked, last 4 digits | no access |
| `exporter_partner` | all stations | all plots, coarsened coordinates | not present | no access |
| `compliance_auditor` | metadata only, no commercial terms | all plots, full coordinates | not present | read |
| unauthenticated | `401` or `403` | `401` or `403` | n/a | n/a |

This table is the specification. It does not say where enforcement lives, what "coarsened" means
in your implementation, or how an audit log records access to a coordinate without storing the
coordinate. Those are your decisions — explain them in `DECISION_LOG.md`.

## How your role model works

Explain how a role is represented in your system (a field on the user, a separate profile model,
group membership, whatever you chose) and how `seed_rbac_fixtures` assigns each of the three
seeded users to their role. This section is read by a human grader and in your technical defense —
it is not read by the automated checks.

## Where coarsening and masking happen

State which layer (queryset, serializer, permission class, or a combination) applies the
coordinate coarsening and the national-ID masking, and why you chose that layer over the
alternatives.
