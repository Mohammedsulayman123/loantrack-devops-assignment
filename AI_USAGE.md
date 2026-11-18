# AI Usage Log: LoanTrack DevOps Implementation

This document provides a transparent audit of AI tooling usage for scaffolding and boilerplate syntax, fulfilling **Part E5** of the technical assignment.

---

## 1. Tool Usage Matrix

| Task | Tool | What was Accepted As-Is | What was Changed and Why |
| :--- | :--- | :--- | :--- |
| **Backend API Scaffolding (`main.py`)** | ChatGPT / Claude | Standard FastAPI endpoint signatures (`GET /loans`, `POST /loans`). | AI initially generated synchronous, single-connection database queries that crashed if PostgreSQL was unavailable. I rewrote the persistence layer to use an `asyncpg` connection pool (`min_size=2, max_size=10`) and implemented an asynchronous exponential backoff retry loop (`connect_with_retry`) during lifespan startup so the application starts immediately without crashing. Also added active container hostname injection into API responses to verify Kubernetes replica load-balancing. |
| **Kubernetes YAML Scaffolding (`k8s/`)** | ChatGPT / Claude | Base YAML boilerplate (API versions, Namespace resource, and generic label/selector schemas). | Discarded the AI's generic Deployment for PostgreSQL in favor of a `StatefulSet` with `volumeClaimTemplates` for persistent volume guarantees and stable network identities. Configured explicit CPU and memory `requests` and `limits` on every container to prevent cluster resource exhaustion. Added decoupled `/healthz` (liveness) and `/readyz` (readiness) HTTP probes with calibrated delays, and defined a zero-downtime rolling update strategy (`maxSurge: 1, maxUnavailable: 0`). |
| **Frontend Dashboard Layout (`index.html`)** | ChatGPT / Claude | Basic HTML layout, CSS cards, and table styling. | Re-engineered the client-side JavaScript to decouple backend endpoints via dynamic origin resolution, added live polling for `/healthz` and `/readyz` indicators, and implemented visual error states for backend downtime. |
| **Deployment Automation (`scripts/deploy.sh`)** | ChatGPT / Claude | Initial bash command sequence structure. | Added cluster readiness checks, automated fallback generation of `k8s/secret.yaml` from `k8s/secret.example.yaml`, deterministic manifest ordering, rollout status timeout bounds, and NodePort URL display to make the deployment fully idempotent. |

---

## 2. Where the AI was Wrong or Misleading

1. **Coupled Health Probes**: The AI initially coupled `/healthz` directly to a database `SELECT 1` query. In a containerized environment, if the database takes 10–15 seconds to initialize, the backend container fails its liveness probe and Kubernetes enters a destructive `CrashLoopBackOff`. I caught this flaw and decoupled the endpoints: `/healthz` validates process event-loop liveness, while `/readyz` verifies active database pool connectivity.
2. **Stateless Assumptions for Databases**: The AI's initial manifest suggested running PostgreSQL as a standard Deployment with a shared PVC. In Kubernetes, stateful databases require stable network identity and dedicated volume attachment tied to pod ordinals (`postgres-0`); I corrected this by architecting PostgreSQL as a `StatefulSet` with `volumeClaimTemplates`.
3. **Nginx Upstream Hostname Resolution**: The AI's suggested Nginx reverse proxy configuration hardcoded `proxy_pass http://backend:8000/`. While valid in Docker Compose, Nginx crashed in Kubernetes at startup with `[emerg] host not found in upstream` because Nginx evaluates static upstream hosts at boot time. I resolved this by adding a matching `backend` ClusterIP service alias in the cluster manifests.
