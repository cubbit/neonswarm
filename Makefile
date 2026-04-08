# Neonswarm — Raspberry Pi DS3 demo panel
#
# Targets intended for local iteration and cluster deployment.
# Override `NAMESPACE`, `RELEASE`, `VALUES`, `KUBECONFIG` on the command
# line if the defaults do not match your setup.

NAMESPACE    ?= neonswarm
RELEASE      ?= neonswarm
VALUES       ?= values.yaml
KUBECONFIG   ?= $(HOME)/.kube/config
CONTEXT      ?= neonswarm
PLATFORM     ?= linux/arm64
REGISTRY     ?= cubbit
LCD_IMAGE    ?= $(REGISTRY)/neonswarm-lcd-storage:latest
LED_IMAGE    ?= $(REGISTRY)/neonswarm-led-sniffer:latest

KUBECTL      := kubectl --context=$(CONTEXT) -n $(NAMESPACE)
HELM         := helm --kube-context=$(CONTEXT)

.PHONY: help
help: ## Show this help message
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  \033[36m%-18s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# ---------------------------------------------------------------- chart ----

.PHONY: deps
deps: ## Refresh Helm subchart dependencies
	helm dependency update .

.PHONY: lint
lint: deps ## helm lint against $(VALUES)
	helm lint . -f $(VALUES)

.PHONY: template
template: deps ## Render templates to stdout
	helm template $(RELEASE) . -f $(VALUES) --namespace $(NAMESPACE)

.PHONY: diff
diff: deps ## Diff the current cluster state against local templates (needs helm-diff plugin)
	$(HELM) diff upgrade $(RELEASE) . -n $(NAMESPACE) -f $(VALUES) --allow-unreleased

.PHONY: validate
validate: lint template ## Run lint + a dry-run install against the cluster
	$(HELM) upgrade --install $(RELEASE) . -n $(NAMESPACE) -f $(VALUES) --dry-run --debug | tail -20

# ----------------------------------------------------------- deployment ----

.PHONY: deploy
deploy: deps ## helm upgrade --install the umbrella chart
	$(HELM) upgrade --install $(RELEASE) . -n $(NAMESPACE) --create-namespace -f $(VALUES)

.PHONY: status
status: ## Show release + pod status
	$(HELM) status $(RELEASE) -n $(NAMESPACE)
	@echo
	$(KUBECTL) get pods -l app.kubernetes.io/instance=$(RELEASE) -o wide

.PHONY: logs-lcd
logs-lcd: ## Tail logs from all lcd-storage pods
	$(KUBECTL) logs -f -l app.kubernetes.io/component=storage-monitor --prefix --tail=50

.PHONY: logs-led
logs-led: ## Tail logs from all led-sniffer pods
	$(KUBECTL) logs -f -l app.kubernetes.io/component=packet-sniffer --prefix --tail=50

.PHONY: logs-agent
logs-agent: ## Tail logs from all Cubbit agents
	$(KUBECTL) logs -f -l app.kubernetes.io/component=swarm-agent --prefix --tail=50

.PHONY: rollout
rollout: ## Force a rolling restart of both DaemonSets (pulls latest image)
	$(KUBECTL) rollout restart ds/$(RELEASE)-lcd-storage ds/$(RELEASE)-led-sniffer

.PHONY: uninstall
uninstall: ## helm uninstall the release (does NOT delete PVs — they Retain)
	$(HELM) uninstall $(RELEASE) -n $(NAMESPACE)

# -------------------------------------------------------------- images ----

.PHONY: build-lcd
build-lcd: ## Build + push the lcd-storage image for $(PLATFORM)
	docker buildx build --platform $(PLATFORM) \
		-f storage-node/lcd_storage/Dockerfile \
		-t $(LCD_IMAGE) --push .

.PHONY: build-led
build-led: ## Build + push the led-sniffer image for $(PLATFORM)
	docker buildx build --platform $(PLATFORM) \
		-f storage-node/led_sniffer/Dockerfile \
		-t $(LED_IMAGE) --push .

.PHONY: build
build: build-lcd build-led ## Build + push both service images

# --------------------------------------------------------------- tests ----

.PHONY: test
test: ## Run Python unit tests for both services
	nix run nixpkgs#python313Packages.pytest -- \
		storage-node/lcd_storage/tests/ \
		storage-node/led_sniffer/tests/

# --------------------------------------------------------------- ship ----

.PHONY: ship
ship: test lint build deploy status ## Full pipeline: test -> lint -> build -> deploy -> status
	@echo
	@echo "Shipped. Physical verification needed: LCD + LED behavior on the panel."
