# Control_1C_version

REST API for tracking 1C configurations, telling a client that an update is needed, booking a date, and reporting the result to the head of support.

Specialists can use the Russian web console («Верконт»), `/docs`, or the curl / smoke flow below.

## Morning check

With the API already running:

```bash
curl -sS http://127.0.0.1:8000/health
curl -sS http://127.0.0.1:8000/health/ready
python scripts/smoke.py
```

`GET /health` is liveness: the process is up and Postgres answers `SELECT 1`. A database outage returns **503** and `"database": "down"`.

`GET /health/ready` checks that the four roles exist and that the demo accounts were seeded (`demo_seeded: true`).

`python scripts/smoke.py` signs in as every role and walks the functional requirements: clients and configurations, a version check, a notification, a booked update, a status change, and the head-of-department reports. It creates its own client (so it can be repeated) and also reads the seeded demo rows. `BASE_URL` overrides the default `http://127.0.0.1:8000`.

The same checks as curl, after seed:

```bash
API=http://127.0.0.1:8000
curl -sS "$API/health"
curl -sS "$API/health/ready"

login() {
  curl -sS -X POST "$API/api/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$1\",\"password\":\"$2\"}"
}
token() { login "$1" "$2" | python3 -c 'import json,sys; print(json.load(sys.stdin)["access_token"])'; }

ADMIN=$(token admin@example.com admin123)
SPEC=$(token specialist@example.com specialist123)
MANAGER=$(token manager@example.com manager123)
CLIENT=$(token client@example.com client123)

curl -sS "$API/api/clients?q=Ромашка" -H "Authorization: Bearer $SPEC"
curl -sS "$API/api/configurations?q=Бухгалтерия" -H "Authorization: Bearer $SPEC"
# Take client_configuration_id from the client configurations list, then:
# curl -sS -X POST "$API/api/version-checks/run" -H "Authorization: Bearer $SPEC" \
#   -H 'Content-Type: application/json' -d '{"client_configuration_id":"<id>"}'
curl -sS "$API/api/version-checks/outdated?q=Ромашка" -H "Authorization: Bearer $SPEC"
curl -sS "$API/api/notifications" -H "Authorization: Bearer $CLIENT"
curl -sS "$API/api/update-slots/dates" -H "Authorization: Bearer $CLIENT"
curl -sS "$API/api/scheduled-updates?status=scheduled" -H "Authorization: Bearer $SPEC"
curl -sS "$API/api/reports/updated-clients" -H "Authorization: Bearer $MANAGER"
curl -sS "$API/api/reports/updates" -H "Authorization: Bearer $MANAGER"
curl -sS "$API/api/reports/outdated-clients" -H "Authorization: Bearer $MANAGER"
```

Interactive docs: http://127.0.0.1:8000/docs

## Run

### Docker Compose (API + Postgres + web console)

```bash
docker compose up --build
```

The API container waits for Postgres, runs `alembic upgrade head`, then starts uvicorn. Startup seeds roles (if the migration has not already inserted them) and the demo walkthrough data. The `web` service builds the SPA and proxies `/api` and `/health` to the API, so the browser stays on one origin. Interactive docs stay on port 8000.

- Web console: http://127.0.0.1:8080
- API: http://127.0.0.1:8000
- Docs: http://127.0.0.1:8000/docs
- Postgres on the host: `localhost:5433` (`postgres` / `postgres`, database `control_1c_version`)

### UI against an API that is already on port 8000

```bash
cd frontend
npm install
npm run dev
```

Open http://127.0.0.1:5173 . Vite proxies `/api` and `/health` to http://127.0.0.1:8000 , so `/docs` on port 8000 keeps working. The interface is in Russian. Sign in with the demo accounts in the next section; the same passwords are shown on the login screen as a local demo hint, not as production credentials.

`npm run preview` serves the production build on http://127.0.0.1:4173 and uses the same proxy.

The API allows browser calls from localhost (Vite `5173` and `4173`, compose UI `8080`, and any other localhost port). The supported setup is still the proxy.

### API on the host, Postgres from Compose

```bash
docker compose up -d db
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn main:app --host 0.0.0.0 --port 8000
```

Defaults match `.env.example` (`localhost:5433`). Copy `.env.example` to `.env` to override `JWT_SECRET`, `SEED_DEMO`, or `DATABASE_URL`.

Seed again without restarting the API:

```bash
python -m src.data.seed
```

Apply this only after `alembic upgrade head`. The process refuses to start if the tables are missing.

## Demo accounts

| Role | Email | Password |
| --- | --- | --- |
| Administrator | `admin@example.com` | `admin123` |
| Support specialist | `specialist@example.com` | `specialist123` |
| Head of support | `manager@example.com` | `manager123` |
| Client (ООО Ромашка) | `client@example.com` | `client123` |

Seeded data:

- **ООО Ромашка** — Бухгалтерия предприятия `3.0.150`, current release `3.0.175` (outdated), plus an unread update notification.
- **АО Василёк** — Зарплата и управление персоналом already on `3.1.32`, with one completed update in history.
- Open slots for the specialist on the next seven days (10:00–12:00 and 14:00–16:00).

Passwords are for the local demo. Set `SEED_DEMO=false` outside development. Change `JWT_SECRET` before any shared deployment.

## Who can do what

| | Admin | Specialist | Head | Client |
| --- | --- | --- | --- | --- |
| Register users, assign roles | yes | | | |
| Clients and installations | write | write | read | own company |
| Configuration catalog | write | write | read | read |
| Run a version check | yes | yes | | |
| Outdated list and check history | yes | yes | yes | |
| Create an update notification | yes | yes | | |
| Read notifications | all | all | all | own |
| Open slots | yes | yes | read | available dates only |
| Request an update / pick a date | yes | yes | | own configurations |
| Change update status | yes | yes | | |
| Reports | yes | | yes | |

A client user must be linked to a company (`client_id`). Create the company first, then the user.

## API map

| Requirement | Method and path |
| --- | --- |
| 1.1 Register users and assign roles | `POST /api/users`, `PATCH /api/users/{id}`, `GET /api/roles` |
| 1.2 Add and edit clients | `POST /api/clients`, `PATCH /api/clients/{id}`, `GET /api/clients?q=` |
| 1.3 Store configurations and versions | `POST /api/configurations`, `POST /api/configurations/{id}/versions`, `POST /api/clients/{id}/configurations` |
| 1.4 View a client's configurations | `GET /api/clients/{id}/configurations`, `GET /api/client-configurations?outdated=` |
| 2.1 Compare installed vs current | `POST /api/version-checks/run` |
| 2.2 Clients that need an update | `GET /api/version-checks/outdated` |
| 2.3 Keep check and status history | `GET /api/version-checks`, `GET /api/scheduled-updates/{id}` |
| 3.1–3.2 Tell the client | `POST /api/notifications` (one row per active portal user) |
| 3.3 Client reads the notice | `GET /api/notifications`, `POST /api/notifications/{id}/read` |
| 4.1 Available dates | `POST /api/update-slots`, `GET /api/update-slots/dates` |
| 4.2 Client picks a date | `POST /api/scheduled-updates` with `slot_id` |
| 4.3 Staff list | `GET /api/scheduled-updates` |
| 4.4 View and change status | `GET /api/scheduled-updates/{id}`, `PATCH /api/scheduled-updates/{id}/status` |
| 5.1 Clients whose configurations were updated | `GET /api/reports/updated-clients` |
| 5.2 Completed vs planned | `GET /api/reports/updates` |
| Head reviews outdated clients | `GET /api/reports/outdated-clients` |

Search and filters use query parameters: `q`, `status`, `role`, `outdated`, `is_read`, `date_from`, `date_to`, `client_id`. Lists are paged with `limit` and `offset`.

Planned updates in report 5.2 are `requested`, `scheduled`, and `in_progress`. `completed` and `cancelled` are counted separately in `by_status`. An optional date range applies `completed_at` to finished updates and the slot date (or creation date, if no slot) to the rest.

Status transitions: `requested → scheduled|cancelled`, `scheduled → in_progress|cancelled|requested`, `in_progress → completed|cancelled`. Moving to `completed` sets the installation's version to the target release and stores source/target on the update so report 5.1 still shows the old and new versions.

Bearer tokens from `POST /api/auth/login` (`{"email","password"}`). Send `Authorization: Bearer <access_token>`.

## Schema notes

The initial migration already created clients, configurations, version checks, notifications, slots, and scheduled updates. This MVP adds:

- `scheduled_updates.source_version_id` and `target_version_id` (`20261105_0002`) so a finished update can advance the installed version and reports can show from/to releases.
- Removal of the unused duplicate model `src/data/models/schedual_updates.py`. It mapped the same tables as `scheduled_updates.py` (and a target-version relationship the migration did not have). Importing both would register `scheduled_updates` twice.

`GET /health` and `GET /health/ready` are also mounted at `/api/health` and `/api/health/ready`.

## Layout

```text
main.py                     FastAPI app
src/api/routers             HTTP routes
src/services                checks, notifications, planning, reports
src/data/models             SQLAlchemy models
src/data/seed.py            roles and demo walkthrough
alembic/versions            schema
docker-compose.yml          Postgres 16, the API, and the web console
frontend/                   Vite + React console («Верконт»)
scripts/smoke.py            repeatable TZ walkthrough
```
