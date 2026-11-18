.PHONY: all deploy undeploy docker-up docker-down

all: deploy

deploy:
	@bash scripts/deploy.sh

undeploy:
	kubectl delete namespace loantrack || true

docker-up:
	cp -n .env.example .env || true
	docker compose up -d

docker-down:
	docker compose down
