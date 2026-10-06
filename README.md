# Kawa Network Assessment Shell

This repository is the starter shell for the `2793` Advanced Python assessment sequence. It is
intentionally **not** a runnable Django project on day one. You will accept this assignment once
through Classroom 50 and keep working on that same repository through F1, F2, and the Summative.

## What this repository provides

- repo hygiene and workflow structure
- the Kawa assessment continuity model
- documentation templates for assessed artifacts:
  - `ADR.md`
  - `DECISION_LOG.md`
  - `BUG_REPORT.md`
  - `docs/RBAC_MATRIX.md`
- a milestone-comment template for the Feedback pull request Classroom 50 opens automatically
- a lightweight CI workflow for repo hygiene only
- public autograding contracts that define the minimum objective checks for each stage

## What you must create yourself in F1

This is part of the learning design. In `F1`, you are expected to bootstrap the application
yourself, including:

- the Django project itself
- `manage.py`
- the project configuration package
- installed apps and URL routing
- Django REST Framework setup
- async worker wiring when you implement the risk-check flow
- your initial models, serializers, views, and endpoints

## What this repository does not provide

- a prebuilt Django project
- working starter endpoints
- ready-made app modules
- hidden grading tests
- pre-written assessed reasoning
- a solved async or deployment setup

## Repository model for the full module

You accept this assignment once, through Classroom 50, at the start of F1. After that:

- you keep the same repository through all three assessments
- `main` is your working branch (you may use others internally, but grading reads whatever `main`
  points at when you tag)
- you push a **milestone tag** when each stage is ready to grade, instead of opening a separate
  Pull Request per stage
- you submit your repository URL in Canvas each time -- it is the same URL at every stage

### Milestone model

| Assessment | Milestone tag | Trigger |
|---|---|---|
| F1 | `f1` | `git tag f1 && git push origin f1` |
| F2 | `f2` | `git tag f2 && git push origin f2` |
| Summative | `summative` | `git tag summative && git push origin summative` |

Pushing a milestone tag grades the commit it points at and publishes a Release. Ordinary pushes to
`main` do not trigger grading, so you can commit as often as you like and tag only when a stage is
actually ready.

### Repository naming

`advanced-python-programming-kawa-<github-username>`, assigned automatically when you accept the
assignment.

## Assessment journey

### F1: MVP - Delivery API, Async Risk Checks, and Performance Foundations

You will use this repo shell to build the first real application increment, including:

- bootstrapping the Django project and configuration
- farmer and plot registration
- delivery recording against a plot
- a station-facing delivery feed
- a price-schedule read endpoint
- validation and typed implementation
- one async risk-check flow
- one performance-minded feature such as pagination or caching
- `ADR.md`

### F2: Compliance Retrofit - Auth, RBAC, Location Privacy, and Auditability

You continue from the same repository and add:

- stronger authentication
- role-based access and coordinate-precision boundaries
- privacy and auditability controls
- a `seed_rbac_fixtures` management command (the [F2 Contract](docs/autograding/F2_CONTRACT.md)
  specifies exactly what it must create)
- updated docs
- `DECISION_LOG.md`
- `docs/RBAC_MATRIX.md`

### Summative: Release Hardening - Debug, Test, Deploy, and Defend

You continue from the same repository and harden it through:

- merging the `summative/seed` branch, which adds three staging scenario tests (this is a content
  branch you merge before tagging -- distinct from the `summative` milestone tag you push once
  hardening is done)
- targeted bug fixing against whichever scenarios fail for you
- stronger automated tests
- deployment/runtime configuration
- release-readiness documentation
- `BUG_REPORT.md`

## Local setup

### 1. Accept the assignment and clone your repository

```bash
gh student accept ALU-BSE advanced-python-programming kawa
git clone <your-repo-url>
cd advanced-python-programming-kawa-<github-username>
```

See the [Classroom 50 CLI Student Guide](https://github.com/foundation50/classroom50/wiki/CLI-Student-Guide)
if `gh student` isn't installed yet, or use the [web app](https://classroom50.org) instead.

### 2. Create and activate a virtual environment

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

Update values in `.env` as needed for your local setup.

### 5. Bootstrap your Django project and apps

You are expected to create the Django project and the initial application structure yourself
during `F1`.

### 6. Install and configure the project components you choose

At minimum, your implementation should introduce:

- a Django project package
- `manage.py`
- DRF-enabled API configuration
- at least the app boundaries needed for your chosen solution
- routing and settings that allow the system to run

### 7. Run the application and worker you build

Once your project exists, document your own run commands in the README.

## Environment variables

| Variable | Required | Purpose |
|---|---|---|
| `SECRET_KEY` | Yes | Django application secret |
| `DEBUG` | Yes | Local debug mode |
| `ALLOWED_HOSTS` | Yes | Comma-separated allowed hosts |
| `CELERY_BROKER_URL` | No | Queue broker connection for the async risk-check flow |
| `CELERY_RESULT_BACKEND` | No | Async task result backend |
| `REGISTRY_API_URL` | No | External deforestation risk registry, stubbed locally |
| `REGISTRY_API_TIMEOUT` | No | Timeout in seconds for registry calls |

## Minimum repo shape by the end of F1

By the end of `F1`, a grader should be able to see a repository that now contains:

- a Django project created by you
- application modules that support your API design
- environment setup instructions in the README
- `ADR.md`
- API code and documentation or schema evidence
- evidence of the async risk-check flow
- one performance-minded improvement

## Assessed artifact locations

Place these in the repository root when each stage requires them:

- `ADR.md`
- `DECISION_LOG.md`
- `BUG_REPORT.md`
- `docs/RBAC_MATRIX.md`

Use the templates in `docs/templates/` as starting points. Replace the prompts with your own
decisions and evidence.

## Autograding contract

Classroom 50's autograder checks only the minimum objective baseline for each stage. Read these
before you start work:

- [Runtime Contract](docs/autograding/RUN_CONTRACT.md)
- [F1 Contract](docs/autograding/F1_CONTRACT.md)
- [F2 Contract](docs/autograding/F2_CONTRACT.md)
- [Summative Contract](docs/autograding/SUMMATIVE_CONTRACT.md)

These contracts do not tell you how to design the project. They define the minimum public
interface the hidden checks rely on. The F2 contract also defines the four fixture plots used to
grade your role-based access and coordinate-coarsening implementation — read it before you build
the retrofit, not after.

## Submission workflow

For every stage:

1. Complete the work for that stage on `main`.
2. Push the stage's milestone tag: `git tag f1 && git push origin f1` (then `f2`, then
   `summative`).
3. Post a comment on the repository's Feedback pull request using the template in
   `.github/pull_request_template.md`.
4. Submit your repository URL in Canvas.

## AI-use disclosure expectations

Limited AI support is allowed only within course rules. If you use AI, disclose it clearly in your
Feedback PR comment and README annex:

- what tool you used
- what you asked it to help with
- what you changed before accepting the output
- what you can explain independently

Do not submit code or reasoning you cannot defend in the technical defense process.

## Integrity and continuity signals

This repo structure is also part of the authorship and integrity model. Over time, graders should
be able to see:

- commit history that grows across the trimester
- earlier artifacts still present and improved
- trade-off reasoning that evolves with the codebase
- one milestone comment per stage on the Feedback PR, each tied to a pushed tag
