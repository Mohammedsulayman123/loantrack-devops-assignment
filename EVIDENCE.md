# Live Operational Evidence: LoanTrack DevOps Implementation

This document contains the complete record of verified terminal commands, captured outputs, and operational proofs required by **Parts B, C, and D** of the technical assignment.

---

## Part B: Docker Packaging & Local Composition

### B1.1 Non-Root User Execution Proof
```bash
$ docker exec loantrack-backend whoami
appuser

$ docker exec loantrack-frontend whoami
appuser
```

### B1.2 Image Size Verification (< 300 MB Target)
```bash
$ docker images loantrack-backend:v1.0.0
REPOSITORY          TAG       IMAGE ID       CREATED        SIZE
loantrack-backend   v1.0.0    2b0ad6f127d3   2 hours ago    268MB

$ docker images loantrack-frontend:v1.0.0
REPOSITORY           TAG       IMAGE ID       CREATED        SIZE
loantrack-frontend   v1.0.0    666e321fcb6b   2 hours ago    80MB
```
*Result: Backend image is 268 MB, safely below the 300 MB maximum threshold.*

### B2.1 Docker Compose Services & Health Status
```bash
$ docker compose ps
NAME                 IMAGE                       COMMAND                  SERVICE    STATUS                    PORTS
loantrack-backend    loantrack-backend:v1.0.0    "uvicorn main:app --…"   backend    Up 14 seconds (healthy)   0.0.0.0:8000->8000/tcp
loantrack-frontend   loantrack-frontend:v1.0.0   "/docker-entrypoint.…"   frontend   Up 8 seconds (healthy)    0.0.0.0:3000->8080/tcp
loantrack-postgres   postgres:16-alpine          "docker-entrypoint.s…"   postgres   Up 20 seconds (healthy)   0.0.0.0:5433->5432/tcp
```

---

## Part C: Database & Three-Tier Connectivity

### C1. Automatic Schema Migration & Initial Seed
```bash
$ docker exec loantrack-postgres psql -U postgres -d loantrack -c "SELECT id, borrower_name, loan_amount, property_city, status FROM loans;"
 id |   borrower_name   | loan_amount |  property_city  |  status  
----+-------------------+-------------+-----------------+----------
  1 | Alice Henderson   |   350000.00 | Austin          | APPROVED
  2 | Bob Martinez      |   485000.50 | Seattle         | PENDING
  3 | Catherine Chen    |   720000.00 | San Francisco   | APPROVED
  4 | David Okafor      |   260000.00 | Chicago         | REJECTED
  5 | Elena Rostova     |   510000.00 | Denver          | PENDING
  6 | Faisal Al-Mansoor |   640000.00 | Boston          | APPROVED
(6 rows)
```

### C2. Startup Retry with Exponential Backoff
Tested by stopping PostgreSQL and restarting the backend service. The backend remained running and logged retries until the database recovered:
```log
2026-11-18 11:57:04,260 [INFO] [loantrack-api] Initializing database connection pool to postgres:5432/loantrack...
2026-11-18 11:57:04,260 [INFO] [loantrack-api] Database connection attempt #1 connecting to postgres:5432...
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
INFO:     127.0.0.1:43528 - "GET /healthz HTTP/1.1" 200 OK
2026-11-18 11:57:08,270 [WARNING] [loantrack-api] Database connection failed on attempt #1: [Errno -5] No address associated with hostname. Retrying in 1.0 seconds...
2026-11-18 11:57:09,271 [INFO] [loantrack-api] Database connection attempt #2 connecting to postgres:5432...
2026-11-18 11:57:13,276 [WARNING] [loantrack-api] Database connection failed on attempt #2: [Errno -5] No address associated with hostname. Retrying in 2.0 seconds...
2026-11-18 11:57:15,275 [INFO] [loantrack-api] Database connection attempt #3 connecting to postgres:5432...
2026-11-18 11:57:19,279 [WARNING] [loantrack-api] Database connection failed on attempt #3: [Errno -5] No address associated with hostname. Retrying in 4.0 seconds...
2026-11-18 11:57:23,977 [INFO] [loantrack-api] Database connection attempt #4 connecting to postgres:5432...
2026-11-18 11:57:27,982 [WARNING] [loantrack-api] Database connection failed on attempt #4: [Errno -5] No address associated with hostname. Retrying in 8.0 seconds...
2026-11-18 11:57:35,983 [INFO] [loantrack-api] Database connection attempt #5 connecting to postgres:5432...
2026-11-18 11:57:36,117 [INFO] [loantrack-api] SUCCESS: Connected to PostgreSQL successfully on attempt #5! Connection pool ready.
```

### C3. Probe Independence when Database is Down
```bash
$ curl -i http://localhost:8000/healthz
HTTP/1.1 200 OK
content-type: application/json
{"status":"healthy","service":"loantrack-backend","pod_name":"dbc0e57c699c"}

$ curl -i http://localhost:8000/readyz
HTTP/1.1 503 Service Unavailable
content-type: application/json
{"status":"not_ready","reason":"Database connection pool is not yet initialized","pod_name":"dbc0e57c699c"}
```

### C4. Loan Insertion via API & Database Verification
```bash
# Created loan via POST /loans
$ curl -X POST http://localhost:8000/loans -H "Content-Type: application/json" -d '{"borrower_name":"Grace Hopper","loan_amount":850000.00,"property_city":"New York","status":"APPROVED"}'
{
  "message": "Loan created successfully",
  "loan": {
    "id": 7,
    "borrower_name": "Grace Hopper",
    "loan_amount": 850000.0,
    "property_city": "New York",
    "status": "APPROVED",
    "created_at": "2026-11-18T17:26:08.829037+05:30"
  },
  "pod_name": "05c78946e618"
}

# Verified row via psql in postgres container
$ docker exec loantrack-postgres psql -U postgres -d loantrack -c "SELECT id, borrower_name, loan_amount, property_city, status FROM loans WHERE id = 7;"
 id | borrower_name | loan_amount | property_city |  status  
----+---------------+-------------+---------------+----------
  7 | Grace Hopper  |   850000.00 | New York      | APPROVED
(1 row)
```

### C5. Persistence Survival (`down` vs `down -v`)
1. Executed `docker compose down` followed by `docker compose up -d`: Row 7 persisted intact.
2. Executed `docker compose down -v` followed by `docker compose up -d`:
   ```bash
   $ docker exec loantrack-postgres psql -U postgres -d loantrack -c "SELECT count(*) FROM loans;"
    count 
   -------
        6
   (1 row)
   ```
*One-line explanation of what changed:*
`docker compose down -v` destroyed the persistent named volume `loantrack_postgres_data`, discarding the manually created loan (id 7) and resetting the database to the 6 seed records re-applied by `001_init.sql` upon container initialization.

---

## Part D: Kubernetes Manifests & Cluster Operations

### D3. Internal DNS Resolution from Backend Pod to Database
```bash
$ kubectl exec -n loantrack backend-fb489c754-2qnxl -- python -c "import socket; print('Short DNS:', socket.gethostbyname('postgres-service')); print('FQDN:', socket.gethostbyname('postgres-service.loantrack.svc.cluster.local'))"
Short DNS: 10.106.42.38
FQDN: 10.106.42.38
```
*Fully qualified domain name (FQDN):* **`postgres-service.loantrack.svc.cluster.local`**

### D4.1 Backend Scaling to 3 Replicas & Round-Robin Proof
```bash
$ kubectl scale deployment backend --replicas=3 -n loantrack
deployment.apps/backend scaled

$ kubectl get pods -n loantrack -l app.kubernetes.io/name=backend
NAME                      READY   STATUS    RESTARTS   AGE
backend-fb489c754-2qnxl   1/1     Running   0          3m49s
backend-fb489c754-s5t9d   1/1     Running   0          22s
backend-fb489c754-sxjh2   1/1     Running   0          22s
```

Sending 6 sequential requests through `backend-service`:
```bash
$ kubectl exec -n loantrack deployment/frontend -- /bin/sh -c "for i in 1 2 3 4 5 6; do curl -s http://backend-service:8000/healthz; echo ''; done"
{"status":"healthy","service":"loantrack-backend","pod_name":"backend-fb489c754-sxjh2"}
{"status":"healthy","service":"loantrack-backend","pod_name":"backend-fb489c754-2qnxl"}
{"status":"healthy","service":"loantrack-backend","pod_name":"backend-fb489c754-s5t9d"}
{"status":"healthy","service":"loantrack-backend","pod_name":"backend-fb489c754-sxjh2"}
{"status":"healthy","service":"loantrack-backend","pod_name":"backend-fb489c754-sxjh2"}
{"status":"healthy","service":"loantrack-backend","pod_name":"backend-fb489c754-s5t9d"}
```
*Proof: Requests are served dynamically across all three replicas.*

### D4.2 Rolling Update to :v2 & Rollback Undo
```bash
# 1. Update image to :v2
$ kubectl set image deployment/backend backend=loantrack-backend:v2 -n loantrack
deployment.apps/backend image updated

# 2. Capture rollout status
$ kubectl rollout status deployment/backend -n loantrack
Waiting for deployment "backend" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "backend" rollout to finish: 2 out of 3 new replicas have been updated...
Waiting for deployment "backend" rollout to finish: 1 old replicas are pending termination...
deployment "backend" successfully rolled out

# 3. Rollback
$ kubectl rollout undo deployment/backend -n loantrack
deployment.apps/backend rolled back

$ kubectl rollout status deployment/backend -n loantrack
Waiting for deployment "backend" rollout to finish: 1 out of 3 new replicas have been updated...
Waiting for deployment "backend" rollout to finish: 2 out of 3 new replicas have been updated...
deployment "backend" successfully rolled out
```
*One-line explanation:*
A user hitting the application mid-rollout experiences uninterrupted, zero-downtime service transparently handled by either the existing or newly ready pods without errors, controlled by `strategy.rollingUpdate.maxUnavailable: 0` combined with the container's `readinessProbe`.

### D4.3 Pod Self-Healing Verification
```bash
# Deleted active backend pod
$ kubectl delete pod backend-fb489c754-blj5h -n loantrack
pod "backend-fb489c754-blj5h" deleted from loantrack namespace

# Replacements automatically scheduled
$ kubectl get pods -n loantrack -l app.kubernetes.io/name=backend
NAME                      READY   STATUS    RESTARTS   AGE
backend-fb489c754-qmmfr   0/1     Running   0          3s
backend-fb489c754-tvnwd   1/1     Running   0          71s
backend-fb489c754-w8mhn   1/1     Running   0          33s
```
*Proof: Replacement pod `backend-fb489c754-qmmfr` was immediately spawned within 3 seconds.*

### D4.4 Database Pod Deletion & Data Persistence
```bash
# Row count before deletion
$ kubectl exec -n loantrack postgres-0 -- psql -U postgres -d loantrack -c "SELECT count(*) FROM loans;"
 count 
-------
     6

# Deleted stateful pod
$ kubectl delete pod postgres-0 -n loantrack
pod "postgres-0" deleted from loantrack namespace

# Verified data survived upon pod recreation
$ kubectl exec -n loantrack postgres-0 -- psql -U postgres -d loantrack -c "SELECT count(*) FROM loans;"
 count 
-------
     6
```
*Proof: StatefulSet re-attached persistent volume claim `postgres-storage-postgres-0` to the recreated pod, keeping all database records intact.*

### D4.5 Complete Cluster Inventory Output
```bash
$ kubectl get all -n loantrack
NAME                               READY   STATUS    RESTARTS   AGE
pod/backend-fb489c754-qmmfr        1/1     Running   0          39s
pod/backend-fb489c754-tvnwd        1/1     Running   0          107s
pod/backend-fb489c754-w8mhn        1/1     Running   0          69s
pod/frontend-c5f6f84df-wfhsm       1/1     Running   0          4m51s
pod/postgres-0                     1/1     Running   0          26s

NAME                               TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)          AGE
service/backend                    ClusterIP   10.100.239.124   <none>        8000/TCP         5m3s
service/backend-service            ClusterIP   10.110.132.15    <none>        8000/TCP         6m59s
service/frontend-service           NodePort    10.111.172.1     <none>        8080:30080/TCP   6m59s
service/postgres-service           ClusterIP   10.106.42.38     <none>        5432/TCP         7m

NAME                               READY   UP-TO-DATE   AVAILABLE   AGE
deployment.apps/backend            3/3     3            3           6m59s
deployment.apps/frontend           1/1     1            1           6m59s

NAME                               DESIRED   CURRENT   READY   AGE
replicaset.apps/backend-fb489c754  3         3         3       6m59s
replicaset.apps/frontend-c5f6f84df 1         1         1       6m59s

NAME                               READY   AGE
statefulset.apps/postgres          1/1     7m

$ kubectl get pvc,configmap,secret -n loantrack
NAME                                                STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS   AGE
persistentvolumeclaim/postgres-storage-postgres-0   Bound    pvc-24082cd6-26e2-448b-84f2-cffeaed02987   1Gi        RWO            standard       7m1s

NAME                             DATA   AGE
configmap/kube-root-ca.crt       1      7m2s
configmap/loantrack-config       4      7m2s
configmap/postgres-init-script   1      7m1s

NAME                      TYPE     DATA   AGE
secret/loantrack-secret   Opaque   3      7m2s
```
