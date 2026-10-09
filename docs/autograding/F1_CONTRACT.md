# F1 Autograding Contract

`F1` establishes the minimum API and repository contract for the first stage of the Kawa Network
case.

## Milestone tag

- `f1` -- push this tag when F1 is ready to grade: `git tag f1 && git push origin f1`

## Required root artifacts

- `ADR.md`
- `README.md`
- either `schema.yml` or `schema.yaml`

## Required endpoints

Your project must expose these paths exactly:

- `GET /api/status/`
- `POST /api/farmers/`
- `GET /api/farmers/`
- `POST /api/plots/`
- `GET /api/plots/`
- `POST /api/deliveries/`
- `GET /api/deliveries/`
- `GET /api/price-schedule/`

`GET /api/price-schedule/` is required even though caching it is optional. You choose either
pagination or caching as your assessed performance feature in Task 4, but the endpoint itself must
exist either way, because Formative 2 and the Summative both depend on it.

`GET /api/plots/` is required because Formative 2's access matrix governs plot coordinates on it.
If your design stores location only on the farmer, add a plot resource now — Formative 2 assumes
one exists.

`GET /api/farmers/` is required for the same reason: Formative 2's access matrix governs national
ID masking on it. Without a farmer list, that part of the matrix has nothing to check.

## Status response

`GET /api/status/` must return `200`. Any JSON body is acceptable as long as it is valid JSON.

## Farmer list contract

`GET /api/farmers/` must:

- return `200`
- return valid JSON
- show a pagination-minded list structure (a DRF-style envelope containing `results`, or a
  top-level JSON list)

## Farmer create contract

The hidden tests submit:

```json
{
  "full_name": "Uwimana Béatrice",
  "member_number": "KWA-F-0417",
  "cooperative": "Huye",
  "national_id": "1198770123456789",
  "phone": "+250780000000"
}
```

`POST /api/farmers/` must:

- return `201`
- return JSON containing an integer-like `id`

## Plot create contract

The hidden tests submit:

```json
{
  "farmer": 1,
  "plot_code": "KWA-P-0417-A",
  "sector": "Kigoma",
  "washing_station": "Nyaruguru",
  "latitude": "-2.540000",
  "longitude": "29.710000",
  "area_hectares": "0.42"
}
```

`POST /api/plots/` must:

- return `201`
- return JSON containing an integer-like `id`

Two fields matter beyond the create response. `sector` carries the administrative unit that
Formative 2's coordinate coarsening is keyed to. `washing_station` says which station the plot
delivers to, and Formative 2's access scoping depends on it. You may name either field
differently in your own model, provided `docs/RBAC_MATRIX.md` documents the mapping in Formative
2 — but both concepts must exist by the end of F1.

## Plot list contract

`GET /api/plots/` must:

- return `200`
- return valid JSON
- show a pagination-minded list structure (a DRF-style envelope containing `results`, or a
  top-level JSON list)

## Delivery create contract

The hidden tests submit:

```json
{
  "plot": 1,
  "washing_station": "Nyaruguru",
  "weight_kg": "38.5",
  "grade": "A",
  "delivered_on": "2026-03-14"
}
```

`POST /api/deliveries/` must:

- return `201`
- return JSON containing an integer-like `id`

A delivery must reference a plot, not a farmer directly. The provenance chain from an export lot
back to the land the coffee grew on depends on this.

## Delivery list contract

`GET /api/deliveries/` must:

- return `200`
- return valid JSON
- show a pagination-minded list structure

Accepted list structures:

- a DRF-style pagination envelope containing `results`
- a top-level JSON list

If you use a top-level list, your README must explicitly explain the pagination or performance
decision you chose instead.

## Price schedule contract

`GET /api/price-schedule/` must:

- return `200`
- return valid JSON

Whether the response is cached is your decision. If you cache it, your README must describe how
the cache is invalidated when the season's prices change.

## Async evidence contract

The hidden checks expect evidence that asynchronous work was designed intentionally, for the
deforestation-risk check queued when a plot is registered.

At least one of the following must be visible in the codebase:

- a Python file containing `shared_task`
- a Python file containing `.delay(`
- a Python file containing `.apply_async(`
- a project-level `celery.py`

Your README must also describe how the async worker is started in your implementation.

## Performance evidence contract

The hidden checks expect evidence of at least one performance-minded design choice.

Accepted evidence includes any of:

- paginated list responses
- explicit cache configuration or cache usage
- documented query optimization in code comments or README

The hidden checks only score the objective evidence. Your rationale belongs in `ADR.md`.
