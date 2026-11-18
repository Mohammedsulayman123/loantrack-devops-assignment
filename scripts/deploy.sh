#!/usr/bin/env bash
# ==============================================================================
# LoanTrack: One-Command Idempotent Deployment Script for Kubernetes (Minikube)
# Requirement: Part E2 - Take-Home Technical Assignment
# ==============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo "===> [1/6] Checking Minikube cluster status..."
if ! minikube status >/dev/null 2>&1; then
    echo "Minikube is not running. Starting minikube with docker driver..."
    minikube start --driver=docker
else
    echo "Minikube is running and ready."
fi

echo "===> [2/6] Building and loading application container images into Minikube..."
# Build locally and load into minikube cluster daemon
echo "Building backend image (loantrack-backend:v1.0.0)..."
docker build -t loantrack-backend:v1.0.0 "${ROOT_DIR}/backend"
minikube image load loantrack-backend:v1.0.0

echo "Building frontend image (loantrack-frontend:v1.0.0)..."
docker build -t loantrack-frontend:v1.0.0 "${ROOT_DIR}/frontend"
minikube image load loantrack-frontend:v1.0.0

echo "===> [3/6] Ensuring active Kubernetes secrets..."
if [ ! -f "${ROOT_DIR}/k8s/secret.yaml" ]; then
    echo "Generating k8s/secret.yaml from template k8s/secret.example.yaml..."
    cp "${ROOT_DIR}/k8s/secret.example.yaml" "${ROOT_DIR}/k8s/secret.yaml"
fi

echo "===> [4/6] Applying Kubernetes manifests in sequence..."
kubectl apply -f "${ROOT_DIR}/k8s/00-namespace.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/01-configmap.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/secret.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/03-postgres-init-configmap.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/04-postgres.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/05-backend.yaml"
kubectl apply -f "${ROOT_DIR}/k8s/06-frontend.yaml"

echo "===> [5/6] Waiting for workload rollouts to complete..."
echo "Waiting for PostgreSQL StatefulSet..."
kubectl rollout status statefulset/postgres -n loantrack --timeout=120s

echo "Waiting for Backend Deployment..."
kubectl rollout status deployment/backend -n loantrack --timeout=120s

echo "Waiting for Frontend Deployment..."
kubectl rollout status deployment/frontend -n loantrack --timeout=120s

echo "===> [6/6] All tiers deployed and healthy! Cluster URL:"
echo "------------------------------------------------------------------"
echo "Frontend NodePort Service URL:"
minikube service frontend-service -n loantrack --url || true
echo "------------------------------------------------------------------"
echo "Port-forward alternative:"
echo "kubectl port-forward svc/frontend-service 3000:8080 -n loantrack"
echo "kubectl port-forward svc/backend-service 8000:8000 -n loantrack"
echo "===> Deployment completed successfully!"
