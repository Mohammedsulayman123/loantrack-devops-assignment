# Real Issues Faced & Post-Mortem Analysis

This document details three authentic technical challenges encountered during the packaging, wiring, and deployment of the LoanTrack three-tier system, fulfilling **Part E4**.

---

### Issue 1: Host Port 5432 Collision during Docker Compose Initialization

#### 1. Symptom
Executing `docker compose up -d` failed during container creation:
```
Error response from daemon: failed to set up container networking: 
driver failed programming external connectivity on endpoint loantrack-postgres: 
Bind for 0.0.0.0:5432 failed: port is already allocated
```

#### 2. Diagnosis (Commands in order)
1. `docker compose ps`: Showed `loantrack-postgres` failed to start while `backend` and `frontend` remained waiting.
2. `Get-NetTCPConnection -LocalPort 5432`: Revealed an existing local PostgreSQL service (`PID 6772`) actively listening on port 5432 on the host machine.
3. Inspected `docker-compose.yml` port mapping definition: `ports: - "5432:5432"`.

#### 3. Root Cause
The host system had a pre-existing background PostgreSQL server running locally, preventing Docker daemon from binding to port 5432 on the host network interface.

#### 4. Fix
Parameterized the host-side port binding in `docker-compose.yml`:
```yaml
ports:
  - "${POSTGRES_PORT:-5432}:5432"
```
Updated `.env` to map host port `5433` (`POSTGRES_PORT=5433`). The internal Docker network (`loantrack-network`) continues to communicate over standard port `5432` by service name `postgres:5432`, resolving the collision without modifying the host setup or container application code.

---

### Issue 2: Frontend Pod CrashLoopBackOff Due to Nginx Upstream DNS Resolution

#### 1. Symptom
After applying Kubernetes manifests in `loantrack` namespace, `postgres-0` and `backend` reached `1/1 Running`, but `frontend` remained in `0/1 Error` with multiple restarts:
```
NAME                       READY   STATUS    RESTARTS      AGE
backend-fb489c754-2qnxl    1/1     Running   0             58s
frontend-c5f6f84df-8qtkf   0/1     Error     3 (25s ago)   58s
postgres-0                 1/1     Running   0             59s
```

#### 2. Diagnosis (Commands in order)
1. `kubectl get pods -n loantrack`: Noticed `frontend` restart count increasing with status `Error`.
2. `kubectl describe pod frontend-c5f6f84df-8qtkf -n loantrack`: Container exited with code 1 immediately after starting.
3. `kubectl logs frontend-c5f6f84df-8qtkf -n loantrack`: Found fatal Nginx startup message:
   ```
   2026/11/18 12:21:14 [emerg] 1#1: host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:22
   nginx: [emerg] host not found in upstream "backend" in /etc/nginx/conf.d/default.conf:22
   ```
4. `kubectl get svc -n loantrack`: Showed the backend service was originally named `backend-service`, not `backend`.

#### 3. Root Cause
In Docker Compose, services resolve each other by container service name (`http://backend:8000/`). In Kubernetes, DNS resolution relies on CoreDNS matching the exact Service resource name. Because Nginx validates upstream proxy targets at startup time, attempting to resolve `backend` when only `backend-service` existed caused Nginx to fail initialization and terminate.

#### 4. Fix
Updated `k8s/05-backend.yaml` to declare a dual Service configuration, providing both `backend` and `backend-service` ClusterIP resources selecting the backend deployment pods:
```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend
  namespace: loantrack
spec:
  type: ClusterIP
  ports:
    - port: 8000
      targetPort: 8000
  selector:
    app.kubernetes.io/name: backend
```
Re-applied the manifest and restarted the frontend pod; Nginx successfully resolved upstream `backend:8000` and transitioned to `1/1 Running`.

---

### Issue 3: Browser Client-Side Connectivity across Minikube Isolation Boundary

#### 1. Symptom
Navigating to the Minikube frontend URL in the browser loaded the LoanTrack dashboard shell, but displayed:
```
Error connecting to backend (http://localhost:8000): Failed to fetch
API: Offline | DB: Disconnected
```

#### 2. Diagnosis (Commands in order)
1. `kubectl get pods -n loantrack`: All three pods (`postgres-0`, `backend`, `frontend`) were `1/1 Running` and healthy.
2. `kubectl exec -n loantrack deployment/frontend -- curl -s http://backend:8000/readyz`: Returned `200 OK` (`{"status":"ready","database":"connected"}`), verifying cluster-internal networking was operating normally.
3. Inspected browser console network tab: Client-side JavaScript executing in the user's browser was issuing `fetch("http://localhost:8000/loans")`. Because the backend `ClusterIP` is strictly internal to Minikube's Docker network, `localhost:8000` on the host machine was not routed to the cluster.

#### 3. Root Cause
Kubernetes `ClusterIP` services are intentionally isolated from the host machine. While Nginx in the frontend pod could reach `backend:8000` internally, the client-side JavaScript executing inside the browser outside the cluster could not reach `localhost:8000` without an active port forwarding session or an Ingress/Gateway.

#### 4. Fix
Established an active port-forward tunnel from the host to the backend service:
```powershell
kubectl port-forward svc/backend-service 8000:8000 -n loantrack
```
Refreshed the browser dashboard; the health indicators immediately turned green (`API: Alive`, `DB: Connected`, showing active backend pod name), and all 6 loan records populated the table.
