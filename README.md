# Kawa Network API (F1 MVP)

Django REST Framework API for coffee provenance: farmers, plots (sector + washing station), deliveries, an async risk check against an external registry, and a paginated station feed. Design rationale: [ADR.md](ADR.md).

## Local setup

Python 3.12, and a Redis server (Docker: `docker run -p 6379:6379 redis`; or WSL; or skip Redis and use eager mode, see below).

```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash on Windows. macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # optional; defaults work
python manage.py migrate
python manage.py seed_demo           # one sector, one station, 2026 price schedule
python manage.py createsuperuser     # optional, for /admin/
python manage.py runserver
```

## Starting the async worker

In a second terminal (venv active), with Redis running:

```bash
celery -A kawa_network worker -l info --pool=solo   # --pool=solo is required on Windows
```

Without a worker the API still works: plots simply stay `pending`. Start a worker later and run `python manage.py requeue_pending_checks` to process them.

**No Redis available?** Set `CELERY_TASK_ALWAYS_EAGER=True` in `.env`. Tasks then run inline on the request — this blocks the request (defeats the point of async in production) but is fine for a quick local demo without installing Redis.

## Environment variables

See `.env.example`. All optional.

| Variable | Default | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | dev key | Set in any real deployment |
| `DJANGO_DEBUG` | `True` | |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` / `/1` | |
| `CELERY_TASK_ALWAYS_EAGER` | `False` | Inline tasks (blocking) |
| `RISK_REGISTRY_MOCK` | `True` | Use the built-in simulator |
| `RISK_REGISTRY_URL` | empty | Real registry endpoint when mock is off |
| `RISK_REGISTRY_MOCK_DELAY_MIN` / `_MAX` | `1` / `4` | Simulated latency in seconds (real one is 2-40) |
| `RISK_REGISTRY_MOCK_FAILURE_RATE` / `_FLAG_RATE` | `0.3` / `0.1` | Share of simulated outages / flagged plots |
| `RISK_MAX_ATTEMPTS` | `5` | Attempts before `check_failed` |
| `RISK_RETRY_BASE_SECONDS` | `60` | Backoff: base * 2^(attempt-1) |

## Endpoints

| Method & path | Purpose |
|---|---|
| `POST /api/sectors/`, `GET /api/sectors/` | Administrative sectors |
| `POST /api/stations/`, `GET /api/stations/?sector=` | Washing stations |
| `POST /api/farmers/`, `GET /api/farmers/`, `GET /api/farmers/{id}/` | Farmers |
| `POST /api/plots/` | Register a plot (queues the risk check, returns immediately) |
| `GET /api/plots/?farmer=&sector=&washing_station=&risk_status=` | Plot listing |
| `GET /api/plots/{id}/risk-attempts/` | Every registry attempt for a plot |
| `POST /api/plots/{id}/recheck/` | Re-queue a `pending` / `check_failed` plot |
| `POST /api/deliveries/` | Record a delivery |
| `GET /api/deliveries/?washing_station=&plot=&delivered_at__gte=&page_size=` | **Station feed**, newest first, cursor-paginated |
| `GET /api/price-schedule/` | Current season prices per grade |
| `GET /api/docs/` · `GET /api/schema/` | Swagger UI · OpenAPI |

Errors always look like `{"error": {"code": "...", "message": "...", "fields": {...}}}`. Codes: `validation_error` (400), `plot_flagged` (409), `already_decided` (409), `not_found` (404).

## Example requests

```bash
H='Content-Type: application/json'
curl -X POST localhost:8000/api/farmers/ -H "$H" -d '{"full_name":"Jean Claude","phone":"0788123456"}'
curl -X POST localhost:8000/api/plots/ -H "$H" -d '{"farmer":1,"name":"Hillside","sector":1,"washing_station":1,"area_hectares":"0.75","latitude":"-2.7","longitude":"29.5"}'
curl -X POST localhost:8000/api/deliveries/ -H "$H" -d '{"plot":1,"weight_kg":"42.5","grade":"A","client_ref":"phone1-000123"}'
curl "localhost:8000/api/deliveries/?washing_station=1&page_size=25"
curl localhost:8000/api/price-schedule/
```

`client_ref` is optional. Send a unique one per delivery from the phone: if a request times out and is retried, the second call returns the original delivery (`200`) instead of recording it twice (`201`).

## Delivery rules

Deliveries are accepted for `pending`, `check_failed` and `clear` plots (unverified ones carry `provenance_verified: false`). A `flagged` plot returns `409 plot_flagged`. Full reasoning in the ADR.

## Tests

```bash
python manage.py test
```

25 tests cover: validation, the non-blocking registration path, retry/backoff and give-up behaviour, delivery provenance rules, idempotent retries via `client_ref`, cursor pagination and its query count, and the price schedule.

## Performance choice

Cursor-paginated delivery feed (see ADR). No cache is used, so there is no invalidation to document; `GET /api/price-schedule/` reads straight from the database.

## Regenerating the OpenAPI schema

```bash
python manage.py spectacular --file docs/openapi.yml --validate
```

## Known limits

No authentication yet (Formative 2 scopes access by sector and station). SQLite is used for the MVP; move to Postgres before real load.

Honestly the two-process setup (Redis + a separate worker) was the part I went
back and forth on most while building this. It's more to run locally than I'd
like, but a single-process version wouldn't actually survive the outages the
brief describes, so I kept it.