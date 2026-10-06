# F2 Autograding Contract

`F2` retrofits the `F1` codebase with authentication, authorization, and compliance-minded
controls for the Kawa Network case.

## Milestone tag

- `f2` -- push this tag when F2 is ready to grade: `git tag f2 && git push origin f2`. Your work
  continues on the same repository and the same history as F1; there is no separate branch to
  create.

## Required root artifacts

- `DECISION_LOG.md`
- `docs/RBAC_MATRIX.md`

`docs/RBAC_MATRIX.md` documents your role model in prose, for a human grader. The automated
matrix checks do not parse it — they call the management command below.

## Required fixture command

Your project must provide a Django management command:

```bash
python manage.py seed_rbac_fixtures
```

Idempotent: running it twice must not error or duplicate data. It must create, using your own
models directly (not the HTTP API), exactly:

**Three users**, each already configured with the correct role in your system, however your
implementation represents that:

| Username | Password | Role | Notes |
|---|---|---|---|
| `field_agent_user` | `GraderPass123!` | `field_agent` | scoped to washing station `Nyaruguru` |
| `exporter_user` | `GraderPass123!` | `exporter_partner` | not scoped to a station |
| `auditor_user` | `GraderPass123!` | `compliance_auditor` | not scoped to a station |

**One farmer**, so the national-ID masking checks have a real value to mask:

- `full_name`: `Uwimana Béatrice`, `national_id`: `1198770123456789` (last four: `6789`),
  `member_number`: `KWA-F-SEED-01`

**Four plots**, matching the fixture table below exactly, all owned by the seed farmer.

**Two deliveries**: one against plot `KWA-SEED-K1` (`washing_station` `Nyaruguru`), one against
plot `KWA-SEED-M1` (`washing_station` `Kamonyi`), any valid weight, grade, and date. The hidden
checks read each delivery's `washing_station` field, not its plot, to check scoping — make sure
your delivery serializer includes it.

The hidden checks fetch `field_agent_user`, `exporter_user`, and `auditor_user` from your database
by username and authenticate as each directly. They never call your login views to test the
matrix — the staff-login and token endpoints below are tested separately, on their own, with a
generic credential that carries no role.

## Required authentication endpoints

Your project must expose these paths exactly:

- `POST /api/auth/staff-login/`
- `POST /api/auth/api-token/`

The hidden checks submit:

```json
{
  "username": "grader_user",
  "password": "GraderPass123!"
}
```

Accepted token response shapes:

- a JSON object containing `token`
- a JSON object containing `access`

## Protected API expectation

None of the three `F1` list endpoints may remain open to anonymous access.

`GET /api/deliveries/`, `GET /api/plots/`, and `GET /api/farmers/` must each return `401` or `403`
for an unauthenticated requester.

## Authentication class requirement

Your `DEFAULT_AUTHENTICATION_CLASSES` must include
`rest_framework.authentication.SessionAuthentication`, in addition to whatever token or JWT
authentication you build for API consumers. The hidden checks authenticate as a logged-in Django
session user to drive the access-matrix assertions below — a token-only configuration will return
`401`/`403` to every one of them and score zero on this section, regardless of whether your RBAC
logic is otherwise correct.

This does not stop you from also requiring a token for real API consumers such as the registry
integration; the two authentication classes coexist.

## Access matrix

Your implementation must enforce this table:

| Role | `GET /api/deliveries/` | `GET /api/plots/` | Farmer national ID | Audit log |
|---|---|---|---|---|
| `field_agent` | own washing station only | own station's plots, full coordinates | masked, last 4 digits | no access |
| `exporter_partner` | all stations | all plots, coarsened coordinates | not present | no access |
| `compliance_auditor` | metadata only, no commercial terms | all plots, full coordinates | not present | read |
| unauthenticated | `401` or `403` | `401` or `403` | n/a | n/a |

Read the `exporter_partner` and `compliance_auditor` rows together. The auditor receives *more*
precise location data than the commercial partner and *less* commercial data. Neither role is
simply "more access" than the other — this cannot be implemented as a permission ladder.

Wherever a plot appears nested inside another response (for example, inside a delivery), the same
rule applies to the nested copy.

### The four fixture plots

The hidden checks create these four plots exactly, two in sector `Kigoma` and two in `Mbazi`:

| Plot | `plot_code` | Sector | Washing station | Latitude | Longitude |
|---|---|---|---|---|---|
| K1 | `KWA-SEED-K1` | Kigoma | `Nyaruguru` | `-2.540000` | `29.710000` |
| K2 | `KWA-SEED-K2` | Kigoma | `Nyaruguru` | `-2.660000` | `29.790000` |
| M1 | `KWA-SEED-M1` | Mbazi | `Kamonyi` | `-2.510000` | `29.520000` |
| M2 | `KWA-SEED-M2` | Mbazi | `Kamonyi` | `-2.900000` | `29.900000` |

`field_agent_user` is scoped to `Nyaruguru`, so K1 and K2 are the agent's own plots and M1 and M2
belong to a different station. The `plot_code` values are exact and the hidden checks match plots
by them in your `GET /api/plots/` response — your plot create/list must echo `plot_code` back.

### Access matrix checks

| Role fixture | Request | Expected |
|---|---|---|
| `field_agent` at station A | `GET /api/deliveries/` | `200`, and no delivery whose `washing_station` is station B appears on any page |
| `field_agent` at station A | `GET /api/plots/` | `200`, and no plot whose `washing_station` is station B appears |
| `field_agent` | any plot response | coordinates at full stored precision |
| `field_agent` | any farmer response | national ID appears only as the last 4 digits, never in full |
| `exporter_partner` | `GET /api/deliveries/` | `200`, deliveries from both stations appear |
| `exporter_partner` | `GET /api/plots/` | K1 and K2 return **identical** coordinates to each other |
| `exporter_partner` | `GET /api/plots/` | M1 and M2 return **identical** coordinates to each other |
| `exporter_partner` | `GET /api/plots/` | the K1/K2 coordinate differs from the M1/M2 coordinate |
| `exporter_partner` | `GET /api/plots/` | no returned coordinate equals the plot's stored coordinate rounded to any precision from 0 to 6 decimal places |
| `exporter_partner` | any farmer or plot response | no national ID field appears at all |
| `compliance_auditor` | `GET /api/plots/` | `200`, all four plots, coordinates at full stored precision |
| `compliance_auditor` | any response | no national ID field appears at all |
| `field_agent` | `GET /api/farmers/` | `200`, the seed farmer's national ID appears with only its last 4 digits (`6789`) visible; the full 16-digit value never appears anywhere in the response |
| `exporter_partner` | `GET /api/farmers/` | `200`, the full national ID never appears; no field carrying even the last-4 masked form appears either |
| `compliance_auditor` | `GET /api/farmers/` | `200`, the full national ID never appears; no field carrying even the last-4 masked form appears either |
| unauthenticated | any of the three list endpoints | `401` or `403` |

### What "coarsened" means

Rounding decimal degrees will not satisfy the coarsening checks, and this is deliberate. The
fixture coordinates are chosen so that no rounding precision from 0 to 6 decimal places passes
every assertion above: at 0 decimal places all four plots collapse to the same value, and at 1 or
more decimal places the two plots within each sector separate from each other. Coarsening has to
be keyed to the administrative unit (`sector`), not to numeric precision.

If your sector reference point legitimately coincides with a rounding of one stored coordinate,
document it in `docs/RBAC_MATRIX.md` and raise it with your facilitator before submission.

## Continuity expectation

The retrofit must preserve the original project rather than restarting from scratch.

The hidden checks look for:

- a working `manage.py`
- the original `F1` API paths still present
- existing repository continuity: the same repository, same commit history, extended rather than replaced

## Privacy or auditability expectation

The hidden checks require at least one objective signal that privacy or auditability was added.

Accepted evidence includes:

- a Python file containing `audit`
- a Python file containing `AuditLog`
- a Python file containing `created_by`
- a Python file containing `updated_by`
- a Python file containing `request.user`

The hidden checks only confirm objective evidence exists. Your reasoning belongs in
`DECISION_LOG.md`.
