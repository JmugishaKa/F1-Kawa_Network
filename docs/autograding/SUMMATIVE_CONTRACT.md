# Summative Autograding Contract

The Summative stage hardens the existing Kawa Network codebase for rollout readiness.

## Milestone tag

- `summative` -- push this tag when the Summative is ready to grade:
  `git tag summative && git push origin summative`.

## Required root artifacts

- `BUG_REPORT.md`
- `Dockerfile`
- `DEPLOYMENT.md`

## Required command behavior

The repository must support:

```bash
pip install -r requirements.txt
python manage.py migrate --noinput
python -m pytest -q
```

## Staging scenarios

At the start of Week 7 you merge `summative/seed`, which adds `tests/staging/`. It contains three
scenario tests driving your API the way the pilot at Nyaruguru drove it. Each probes a fault that
Formative 1 or Formative 2 permits but does not require you to close:

1. **Coordinate precision under pagination** — walks every page of `GET /api/plots/` as
   `exporter_partner` and asserts coarsened coordinates hold on every page, not just the first.
2. **Stale price schedule** — reads `GET /api/price-schedule/`, updates the underlying schedule,
   and asserts the new value is served within the invalidation window your own README documents.
3. **Delivery stranded on a failed risk check** — registers a plot with the external registry
   forced to fail, records a delivery against it, and asserts the delivery reaches a state that
   can be assigned to an export lot, or is explicitly rejected with a reason.

Run the staging tests yourself before submitting. Whichever fail are yours to diagnose in
`BUG_REPORT.md`, with a failing test written before the fix. If all three pass, that is a real
result: `BUG_REPORT.md` must then explain which decision in F1 or F2 prevented each scenario, and
you must find and document at least one defect of your own.

## Regression expectation

The hidden checks rerun key `F1` and `F2` objective checks, including every access-matrix and
coarsening assertion. The Summative must not break previously working core behavior unless the
release notes justify a change and preserve equivalent functionality.

## Student test suite expectation

`python -m pytest -q` must execute successfully.

This requirement is about your own maintained test suite, not the hidden tests.

## Deployment and readiness evidence

The hidden checks expect:

- a `Dockerfile`
- a `DEPLOYMENT.md` with explicit run or release guidance
- environment handling documented in the repository

The hidden checks may also look for readiness signals such as:

- `gunicorn`
- `uvicorn`
- `collectstatic`
- `ALLOWED_HOSTS`
- `DEBUG`

The deployment reasoning itself is graded manually.
