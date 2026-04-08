# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Neonswarm is a Raspberry Pi 5 demo panel for Cubbit DS3 distributed storage. It ships two Python services that run on K3S storage nodes plus a Helm umbrella chart that deploys everything (the services as DaemonSets and the Cubbit `agent` as per-node Deployments).

## Layout

```
Chart.yaml               # Helm umbrella chart — pulls in charts/agent, lcd-storage, led-sniffer
values.example.yaml      # Template for values.yaml (swarm agents, LED/LCD params, nodeAffinity)
deploy.sh                # Rsync source to pi-* nodes over VPN+SSH (dev loop, not prod deploy)
charts/
  agent/                 # Cubbit agent Deployment (+ PV) — one per swarm entry in values.yaml
  lcd-storage/           # DaemonSet, RBAC (needs to read/scale Deployments in its namespace)
  led-sniffer/           # DaemonSet with hostNetwork + privileged (needs raw packet capture)
libs/                    # Shared Python package `utils` (parsing, conversion, Loggable base)
storage-node/
  lcd_storage/           # I2C 16x2 LCD service — shows storage usage + scales agent via K8s API
  led_sniffer/           # scapy TCP sniffer that drives a WS2812 NeoPixel strip on threshold
```

Both Python services depend on `libs/` as an editable install — see the Dockerfiles, which copy `libs/` first and `pip install -e .` it before installing the service itself. Any local dev venv must do the same (`pip install -e libs && pip install -e storage-node/<service>`).

## Architecture Notes

- **`lcd-storage`** (`storage-node/lcd_storage/src/lcd_storage.py`) wires together three components: `StorageMonitor` (disk usage at `--path`), `K8SDeploymentMonitor` (reads/scales a Deployment matching `--prefix` on the current node — in-cluster kubeconfig), and `LCDController` (RPLCD over I2C). A GPIO button (`--button-pin`, default 17, pull-up) toggles the matched Deployment between 0 and 1 replicas via `when_pressed`/`when_released`. `NODE_NAME` env var (or `--node-name`) is **required** — it's how the pod figures out which Deployment on its node to track. This is why the chart runs as a DaemonSet with RBAC.
- **`led-sniffer`** (`storage-node/led_sniffer/src/led_sniffer.py`) uses scapy (via `ThresholdSniffer`) to count TCP bytes on a port; when a byte threshold is crossed it fires a NeoPixel wave animation on `LEDStrip` (adafruit-blinka, `D18` by default). Requires `hostNetwork: true` and `privileged: true` — sniffing needs CAP_NET_RAW and the NeoPixel driver needs `/dev/gpiomem` + `/dev/spidev0.0` (mounted via `values.yaml:led-sniffer.devices`).
- **`agent`** chart deploys one Cubbit DS3 agent per entry in `values.yaml:agent.swarm.agents`, each pinned to its `nodeName` with a PV. Secrets/machineIds come from the Cubbit Composer dashboard.
- **`global.nodeAffinity`** in `values.yaml` pins workloads to `pi-storage{1,2,3}` — the gateway node (`pi-gateway`) runs K3S control plane only.

## Common Commands

```bash
# Install/upgrade the full stack (run from repo root on a machine with kubectl context set)
helm upgrade --install neonswarm . -n neonswarm --create-namespace -f values.yaml

# Lint/template the umbrella chart without applying
helm dependency update
helm lint .
helm template neonswarm . -f values.yaml

# Dev loop: rsync repo to all pi nodes over VPN (requires netbird up + SSH key)
./deploy.sh ~/.ssh/ed25519_pi           # sync only
./deploy.sh ~/.ssh/ed25519_pi --install  # sync + pip install -r requirements.txt in .venv

# Run a service locally on a Pi (after editable installs of libs + service)
NODE_NAME=pi-storage1 lcd-storage -v --path / --namespace neonswarm --prefix agent
led-sniffer -v --port 4000 --interface eth0 --threshold 1K

# Build service images (Dockerfiles expect repo root as context so they can COPY libs/)
docker build -f storage-node/lcd_storage/Dockerfile -t cubbit/neonswarm-lcd-storage:latest .
docker build -f storage-node/led_sniffer/Dockerfile -t cubbit/neonswarm-led-sniffer:latest .
```

There is no test suite and no linter config in the repo.

## Editing Tips

- When adding a new shared helper, put it in `libs/src/utils/` and import as `from utils.<module>`. Both services already have `libs` on their `PYTHONPATH` via the editable install — don't duplicate code into a service.
- When changing a service's runtime flags, update **three** places: the `argparse` in `*.py`, the chart's `daemonset.y*ml` args block under `charts/<name>/templates/`, and the defaults in `values.example.yaml`.
- Hardware pin assignments live in the README's "PIN Connections" table — keep it in sync if GPIO usage changes (button pin, LED DIN, I2C bus).
- `lcd-storage` needs RBAC to `get`/`list`/`patch` Deployments in its namespace; changes to what it reads/writes must be reflected in `charts/lcd-storage/templates/role.yaml`.

## Commit Guidelines

- Don't mention Claude Code, AI assistance, or co-author tags in commit messages or PR descriptions.
- Keep commit messages concise.
