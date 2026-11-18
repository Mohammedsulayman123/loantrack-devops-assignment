# AI Usage Log: LoanTrack DevOps Implementation

This document provides a transparent record of AI tooling assistance used during the completion of the take-home technical assignment, satisfying **Part E5**.

---

## 1. AI Tool Usage Matrix

| Task Area | Tool | What was Accepted As-Is | What was Changed and Why |
| :--- | :--- | :--- | :--- |
| **Branching Strategy** | Antigravity Agent | Half-page layout and trade-off comparison between Git Flow and Trunk-Based Development. | Kept argument focused on the explicit assignment prompt: why classic Git Flow with long-lived `develop` creates release bottlenecks for a 5-person team shipping daily. |
| **Database Schema** | Antigravity Agent | Table schema structure matching prompt constraints. | Added 6 realistic seed records covering different loan statuses (`APPROVED`, `PENDING`, `REJECTED`) and timestamps to satisfy the 5+ seed rows requirement. |
| **Backend Implementation** | Antigravity Agent | FastAPI structure with endpoints `/loans`, `/healthz`, `/readyz`. | Refactored DB connection to run asynchronously in a background lifespan task with exponential backoff logging so the process immediately starts and `/healthz` returns 200 even while PostgreSQL is temporarily down. Added active container hostname in responses to facilitate replica load balancing verification. |
| **Docker Packaging** | Antigravity Agent | Multi-stage builder/runtime split using pinned `python:3.12-slim` and `nginx:1.27.2-alpine`. | Added non-root unprivileged user creation (`appuser`, UID 10001) for both backend and frontend tiers; reordered Docker layers so `COPY requirements.txt` precedes source code, ensuring cached builds remain under 300 MB. |
| **Docker Compose** | Antigravity Agent | Bridge network configuration and service dependencies. | Parameterized `POSTGRES_PORT` in `.env` to avoid collisions with local host PostgreSQL instances; set `depends_on: postgres: condition: service_healthy`. |
| **Kubernetes Workloads** | Antigravity Agent | Baseline YAML manifests for Deployment, Service, and ConfigMap. | Replaced standard Deployment for PostgreSQL with a `StatefulSet` with `volumeClaimTemplates` to ensure persistent storage stability and predictable network naming. Added an alias service `backend` alongside `backend-service` to maintain uniform DNS resolution across both Docker Compose and Kubernetes. |
| **Automation** | Antigravity Agent | Deployment bash script template. | Added idempotent checks, automatic fallback creation of `k8s/secret.yaml` from `k8s/secret.example.yaml`, rollout timeout bounds, and NodePort URL display. |

---

## 2. Critical Analysis: Where the AI was Misleading or Incomplete

1. **Nginx Upstream Resolution in Kubernetes**: Initial AI-suggested Nginx configurations relied on a static `proxy_pass http://backend:8000/`. While functional inside Docker Compose where the service is named `backend`, the original Kubernetes manifest named the service `backend-service`. At pod startup, Nginx crashed with `[emerg] host not found in upstream "backend"` because Nginx validates upstream hostnames at boot. I noticed this by running `kubectl logs deployment/frontend -n loantrack` and fixed it by defining a `backend` ClusterIP service alias in `k8s/05-backend.yaml`.
2. **Host Port Collisions**: When initializing Docker Compose, the default port mapping `5432:5432` failed because a PostgreSQL service was already running on the host machine. Instead of killing host processes, I parameterized `POSTGRES_PORT` in `.env` and `docker-compose.yml` so host port binding can be adjusted without breaking container-to-container DNS communication on port 5432.
3. **Probe Independence vs Application Startup**: Standard AI boilerplate often couples `/healthz` and `/readyz` to the database ping inside the same handler. If PostgreSQL takes 10 seconds to start, the backend container fails its liveness probe and Kubernetes enters a `CrashLoopBackOff`. I decoupled the endpoints: `/healthz` checks process memory/event loop liveness, while `/readyz` performs the active DB ping and connection pool validation.
