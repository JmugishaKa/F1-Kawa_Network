# Kawa Network API (F1/F2)

Django REST Framework API for coffee provenance: farmers, plots, deliveries, asynchronous deforestation-risk checks, a cursor-paginated station feed, and F2 authentication and role-based access control.

The grading requirements are documented in the [F1 contract](docs/autograding/F1_CONTRACT.md) and [F2 contract](docs/autograding/F2_CONTRACT.md). See [ADR.md](ADR.md) for the F1 design rationale, [DECISION_LOG.md](DECISION_LOG.md) for F2 decisions, and the [RBAC matrix](docs/RBAC_MATRIX.md) for role access.

## Local setup

Use Python 3.12 and a Redis server (for example, `docker run -p 6379:6379 redis`). The API can also run without Redis for local development; see the eager-mode note below.

```bash
python -m venv .venv
source .venv/Scripts/activate        # Git Bash on Windows
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env                 # optional; defaults work locally
python manage.py migrate
python manage.py seed_demo           # one sector, one station, 2026 price schedule
python manage.py createsuperuser     # optional, for /admin/
python manage.py runserver
```

## Starting the async worker

In a second terminal, with the virtual environment active and Redis running:

```bash
celery -A kawa_network worker -l info --pool=solo   # --pool=solo is required on Windows
```

Without a worker, the API remains available and new plots stay `pending`. Start a worker and run `python manage.py requeue_pending_checks` to process pending checks.

**No Redis available?** Set `CELERY_TASK_ALWAYS_EAGER=True` in `.env`. Tasks then run inline and block the request; this is suitable for a local demo, not production.

## Environment variables

See `.env.example`. These settings are optional for local development.

| Variable | Default | Meaning |
|---|---|---|
| `DJANGO_SECRET_KEY` | Development key | Set a secure value in deployment |
| `DJANGO_DEBUG` | `True` | Django debug mode |
| `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` | `redis://localhost:6379/0` / `/1` | Celery broker and result backend |
| `CELERY_TASK_ALWAYS_EAGER` | `False` | Run tasks inline (blocking) |
| `RISK_REGISTRY_MOCK` | `True` | Use the built-in registry simulator |
| `RISK_REGISTRY_URL` | Empty | Real registry endpoint when mock mode is off |
| `RISK_REGISTRY_MOCK_DELAY_MIN` / `_MAX` | `1` / `4` | Simulated latency in seconds |
| `RISK_REGISTRY_MOCK_FAILURE_RATE` / `_FLAG_RATE` | `0.3` / `0.1` | Simulated outage and flagged-plot rates |
| `RISK_MAX_ATTEMPTS` | `5` | Attempts before status becomes `check_failed` |
| `RISK_RETRY_BASE_SECONDS` | `60` | Exponential retry-backoff base |

## API endpoints

| Method and path | Purpose |
|---|---|
| `GET /api/status/` | Service status |
| `POST /api/sectors/`, `GET /api/sectors/` | Administrative sectors |
| `POST /api/stations/`, `GET /api/stations/?sector=` | Washing stations |
| `POST /api/farmers/`, `GET /api/farmers/`, `GET /api/farmers/{id}/` | Farmers |
| `POST /api/plots/` | Register a plot and queue its risk check |
| `GET /api/plots/?farmer=&sector=&washing_station=&risk_status=` | Role-scoped plot listing |
| `GET /api/plots/{id}/risk-attempts/` | Registry attempts for a plot |
| `POST /api/plots/{id}/recheck/` | Re-queue a `pending` or `check_failed` plot |
| `POST /api/deliveries/` | Record a delivery |
| `GET /api/deliveries/?washing_station=&plot=&delivered_at__gte=&page_size=` | Role-scoped, cursor-paginated station feed |
| `GET /api/price-schedule/` | Active season prices per grade |
| `GET /api/docs/`, `GET /api/schema/` | Swagger UI and OpenAPI schema |
| `POST /api/auth/login/`, `POST /api/auth/staff-login/` | Create a session |
| `POST /api/auth/token/`, `POST /api/auth/api-token/` | Obtain JWT access and refresh tokens |
| `POST /api/auth/token/refresh/` | Refresh a JWT access token |
| `POST /api/auth/logout/`, `GET /api/auth/me/` | End a session or inspect the current user |
| `GET /api/access-log/` | Compliance-auditor access log |

The F2-protected plot, delivery, and farmer lists require authentication. Role-based data scoping and field visibility are described in the [RBAC matrix](docs/RBAC_MATRIX.md). Both session and JWT authentication are enabled. For JWT requests, provide the issued access token in the Authorization header.

## Example requests

These examples use Bash-compatible `curl`. Sector and station IDs must already exist; create them with the relevant endpoints or run `python manage.py seed_demo`.

```bash
H='Content-Type: application/json'
curl -X POST localhost:8000/api/farmers/ -H "$H" -d '{"full_name":"Jean Claude","member_number":"KWA-F-0417","cooperative":"Huye","national_id":"1198770123456789","phone":"+250780000000"}'
curl -X POST localhost:8000/api/plots/ -H "$H" -d '{"farmer":1,"name":"Hillside","plot_code":"KWA-P-0417-A","sector":1,"washing_station":1,"area_hectares":"0.75","latitude":"-2.7","longitude":"29.5"}'
curl -X POST localhost:8000/api/deliveries/ -H "$H" -d '{"plot":1,"weight_kg":"42.5","grade":"A","delivered_on":"2026-03-14","client_ref":"phone1-000123"}'
curl "localhost:8000/api/deliveries/?washing_station=1&page_size=25"
curl localhost:8000/api/price-schedule/
```

`client_ref` is optional. Use a unique reference per delivery so a retry after a network timeout returns the original record instead of creating a duplicate. A delivery's washing station is copied from its plot.

## Delivery and provenance rules

Deliveries may be recorded for `pending`, `check_failed`, and `clear` plots. Deliveries for unverified plots are stored with `provenance_verified: false`; a `flagged` plot returns `409 plot_flagged`. The design trade-offs are described in [ADR.md](ADR.md).

## Performance choice

The delivery feed uses cursor pagination, with 25 rows per page by default and `page_size` capped at 100. It avoids count queries and is designed to keep the station feed efficient as deliveries accumulate. The price schedule is read directly from the database and is not cached.

## F2 fixture data

Run `python manage.py seed_rbac_fixtures` to create the grader's role accounts and sample farmer, plots, and deliveries. The command is idempotent; fixture values and expected access are specified in the [F2 contract](docs/autograding/F2_CONTRACT.md).

## Tests

```bash
python manage.py test
```

The test suite covers API validation and behavior, asynchronous risk-check retries, delivery provenance and idempotency, cursor pagination and query efficiency, and F2 authentication, role scoping, and audit logging.

## OpenAPI schema

The root-level `schema.yml` is the F1 grading artifact. To regenerate the expanded schema under `docs/`:

```bash
python manage.py spectacular --file docs/openapi.yml --validate
```

## Current limits

SQLite is used for the MVP; move to PostgreSQL before production load. JWTs cannot be revoked before expiry. Exporter coordinate coarsening currently calculates sector centroids per plot request; profile and optimize this path before scaling.
