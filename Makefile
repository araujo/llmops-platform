COMPOSE_FILE = infrastructure/docker/docker-compose.yml

# Infra always shared
SHARED_PROFILE = --profile shared

# Agents available today/future
SHOPPING_PROFILE = --profile shopping
SUPPORT_PROFILE = --profile support
RESEARCH_PROFILE = --profile research

# Default: bring up shared + all currently relevant agents
DEFAULT_AGENT_PROFILES = $(SHOPPING_PROFILE)

# Optional: allow dynamic selection like:
# make up-agents AGENTS="shopping support"
define agent_profiles
$(foreach agent,$(AGENTS),--profile $(agent))
endef

.DEFAULT_GOAL := help

help:
	@echo "Targets:"
	@echo "  make up                # shared + default agents"
	@echo "  make up-shared         # shared infra only"
	@echo "  make up-shopping       # shared + shopping"
	@echo "  make up-support        # shared + support"
	@echo "  make up-agents AGENTS=\"shopping support\""
	@echo "  make down              # stop shared + default agents"
	@echo "  make down-agents AGENTS=\"shopping support\""
	@echo "  make logs              # logs for all services in default selection"
	@echo "  make ps                # show running services"
	@echo "  make health            # curl /health"
	@echo "  make shopping-info     # curl shopping info"
	@echo "  make test-shopping     # test shopping endpoint"

# Default up/down/logs operate on shared + default agents
up:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(DEFAULT_AGENT_PROFILES) up --build -d

down:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(DEFAULT_AGENT_PROFILES) down

logs:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(DEFAULT_AGENT_PROFILES) logs -f

ps:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(DEFAULT_AGENT_PROFILES) ps

clean:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(DEFAULT_AGENT_PROFILES) down -v

# Shared infra only
up-shared:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) up --build

down-shared:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) down

logs-shared:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) logs -f

# Single-agent shortcuts
up-faster-shopping:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(SHOPPING_PROFILE) up -d

up-shopping:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(SHOPPING_PROFILE) up --build -d

down-shopping:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(SHOPPING_PROFILE) down

logs-shopping:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(SHOPPING_PROFILE) logs -f api

up-support:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(SUPPORT_PROFILE) up --build

down-support:
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(SUPPORT_PROFILE) down

# Dynamic multi-agent selection
up-agents:
	@test -n "$(AGENTS)" || (echo 'Usage: make up-agents AGENTS="shopping support"' && exit 1)
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(call agent_profiles) up --build -d

down-agents:
	@test -n "$(AGENTS)" || (echo 'Usage: make down-agents AGENTS="shopping support"' && exit 1)
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(call agent_profiles) down

logs-agents:
	@test -n "$(AGENTS)" || (echo 'Usage: make logs-agents AGENTS="shopping support"' && exit 1)
	docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(call agent_profiles) logs -f

# Useful runtime checks
health:
	curl http://localhost:8000/health

root:
	curl http://localhost:8000/

shopping-info:
	curl http://localhost:8000/v1/agents/shopping_assistant/info

test-shopping:
	curl -X POST http://localhost:8000/v1/agents/shopping_assistant/chat/shopping \
		-H "Content-Type: application/json" \
		-d '{"message":"Show me a work bag"}'

env-check-api:
	docker exec -it $$(docker compose -f $(COMPOSE_FILE) $(SHARED_PROFILE) $(DEFAULT_AGENT_PROFILES) ps -q api) /usr/bin/env