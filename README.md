# LoanTrack — Three-Tier Reference Architecture & DevOps Deployment

LoanTrack is a production-grade three-tier financial application engineered and packaged to demonstrate standard Site Reliability Engineering (SRE) and DevOps practices across Docker Compose and Kubernetes.

---

## 1. Tool & Runtime Versions

| Tool | Version | Purpose |
| :--- | :--- | :--- |
| **Docker Engine** | `28.5.2 (build ecc6942)` | Container engine & local image builds |
| **Minikube** | `v1.38.1` | Local single-node Kubernetes cluster (docker driver) |
| **Kubectl** | `v1.34.1 (Client) / v1.35.1 (Server)` | Kubernetes cluster control CLI |
| **Python** | `3.12.3` | Backend microservice runtime (FastAPI / asyncpg) |
| **Nginx** | `1.27.2-alpine` | Frontend web server runtime |
| **PostgreSQL** | `16-alpine` | Relational database system |

---

## 2. Architecture Diagram

```
                        ┌───────────────────────────────────────────────┐
                        │             Client / Web Browser              │
                        └───────────────────────┬───────────────────────┘
                                                │
                     HTTP (Port 3000 / NodePort 30080 / Tunnel)
                                                ▼
                        ┌───────────────────────────────────────────────┐
                        │                 Frontend Tier                 │
                        │    Nginx (Alpine) unprivileged (port 8080)    │
                        │    Static HTML/JS calling API over HTTP       │
                        └───────────────────────┬───────────────────────┘
                                                │
                           Internal HTTP (Port 8000 / ClusterIP)
                                                ▼
                        ┌───────────────────────────────────────────────┐
                        │                 Backend Tier                  │
                        │  Python 3.12-slim (FastAPI + asyncpg pool)    │
                        │  Endpoints: /loans, /healthz, /readyz         │
                        └───────────────────────┬───────────────────────┘
                                                │
                           PostgreSQL TCP (Port 5432 / ClusterIP)
                                                ▼
                        ┌───────────────────────────────────────────────┐
                        │                Database Tier                  │
                        │        PostgreSQL 16 (StatefulSet)            │
                        │    Persistent Volume: 1Gi (standard class)    │
                        │  Init Script: db/migrations/001_init.sql      │
                        └───────────────────────────────────────────────┘
```

---

## 3. Copy-Pasteable Run Instructions

### Option A: Local Run via Docker Compose

```bash
# 1. Clone repository
git clone https://github.com/Mohammedsulayman123/loantrack-devops-assignment.git
cd loantrack-devops-assignment

# 2. Setup environment variables from template
cp .env.example .env

# 3. Start entire 3-tier stack in detached mode
docker compose up -d

# 4. Open in browser
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000/loans
# Health check: http://localhost:8000/healthz

# 5. Teardown
docker compose down
```

---

### Option B: Local Run via Kubernetes (Minikube)

#### Fast Path (One-Command Deploy):
```bash
# Automated build, apply, and rollout wait
bash scripts/deploy.sh
# or using make
make deploy
```

#### Manual Step-by-Step Path:
```bash
# 1. Start Minikube cluster
minikube start --driver=docker

# 2. Build and load container images into Minikube
docker build -t loantrack-backend:v1.0.0 ./backend
minikube image load loantrack-backend:v1.0.0

docker build -t loantrack-frontend:v1.0.0 ./frontend
minikube image load loantrack-frontend:v1.0.0

# 3. Prepare secret from template
cp k8s/secret.example.yaml k8s/secret.yaml

# 4. Apply manifests in sequence
kubectl apply -f k8s/00-namespace.yaml
kubectl apply -f k8s/01-configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/03-postgres-init-configmap.yaml
kubectl apply -f k8s/04-postgres.yaml
kubectl apply -f k8s/05-backend.yaml
kubectl apply -f k8s/06-frontend.yaml

# 5. Wait for all rollouts to complete
kubectl rollout status statefulset/postgres -n loantrack
kubectl rollout status deployment/backend -n loantrack
kubectl rollout status deployment/frontend -n loantrack

# 6. Open application in browser
minikube service frontend-service -n loantrack
# Or via port-forwarding:
kubectl port-forward svc/frontend-service 3000:8080 -n loantrack
kubectl port-forward svc/backend-service 8000:8000 -n loantrack
```

---

## 4. Design Decisions

* **Backend Base Image Choice:** We chose `python:3.12-slim` over Alpine to leverage standard glibc wheels for C-extensions (`asyncpg`) without compilation overhead, while remaining lightweight and secure.
* **Layer-Cache Boundary:** `COPY requirements.txt` and package installation precede copying application source code (`main.py`), ensuring code edits do not trigger unnecessary dependency rebuilds.
* **StatefulSet vs Deployment for Postgres:** We chose `StatefulSet` with `volumeClaimTemplates` because relational databases require stable network identity, ordered lifecycle management, and dedicated volume bindings per pod ordinal to prevent data corruption.
* **Liveness vs Readiness Probes:** Liveness (`/healthz`) verifies the process is alive without touching external services to prevent cascading restart loops, whereas Readiness (`/readyz`) pings the database connection pool to hold ingress traffic until dependencies are operational.
* **Memory Limit vs CPU Limit Breach:** When a container exceeds its memory limit, the Linux kernel terminates it immediately via Out-Of-Memory killer (`OOMKilled`), whereas exceeding a CPU limit results only in CPU throttling (CFS quota) without killing the container.
* **Base64 in Secrets vs Production Best Practices:** Base64 encoding in Kubernetes Secrets is simple obfuscation readable by anyone with cluster access; in production, secrets should be stored in an external secrets manager (such as HashiCorp Vault, AWS Secrets Manager, or GCP Secret Manager) and synced via the External Secrets Operator (ESO) with encryption at rest enabled in etcd.

---

## 5. Repository Documentation Index
- [BRANCHING.md](file:///c:/Users/mdsul/Desktop/loantrack-devops-assignment/BRANCHING.md): Git branching model followed and assessment for a 5-person daily shipping team.
- [EVIDENCE.md](file:///c:/Users/mdsul/Desktop/loantrack-devops-assignment/EVIDENCE.md): Live operational verification logs for Parts B, C, and D.
- [ISSUES_FACED.md](file:///c:/Users/mdsul/Desktop/loantrack-devops-assignment/ISSUES_FACED.md): Three genuine technical challenges (Symptom → Diagnosis → Root cause → Fix).
- [AI_USAGE.md](file:///c:/Users/mdsul/Desktop/loantrack-devops-assignment/AI_USAGE.md): Full audit log of AI tooling, adjustments, and critique.
