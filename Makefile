.PHONY: help up down rebuild logs ips verify clean

help:
	@echo "make ips      - list host IPs your VM can reach (pick one for .env)"
	@echo "make up       - build and start the lab"
	@echo "make down     - stop and remove the lab"
	@echo "make rebuild  - re-roll flags and secrets, then start"
	@echo "make logs     - follow container logs"
	@echo "make verify   - run the reference solver (SPOILERS) against the lab"

ips:
	@./scripts/host-ips.sh

up:
	@test -f .env || (cp .env.example .env && echo "created .env - set LAB_BIND_IP, then re-run")
	docker compose up -d --build
	@echo "Lab at http://$$(grep '^LAB_BIND_IP=' .env | cut -d= -f2):$$(grep '^LAB_PORT=' .env | cut -d= -f2)/"

down:
	docker compose down

rebuild:
	docker compose build --no-cache
	docker compose up -d

logs:
	docker compose logs -f

verify:
	@python3 -c "import flask, requests" 2>/dev/null || { \
	  echo "The solver needs 'flask' and 'requests':"; \
	  echo "    python3 -m venv .venv && .venv/bin/pip install flask requests"; \
	  echo "    .venv/bin/python solutions/solve.py http://HOST:PORT"; \
	  exit 1; }
	python3 solutions/solve.py "http://$$(grep '^LAB_BIND_IP=' .env | cut -d= -f2):$$(grep '^LAB_PORT=' .env | cut -d= -f2)"

clean: down
	-docker image rm pickled-cookie-lab:latest
