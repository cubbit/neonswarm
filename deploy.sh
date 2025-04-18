#!/bin/bash

set -euo pipefail

echo "🛜 Connecting to VPN"
netbird up

# Check for SSH key argument
if [ $# -lt 1 ]; then
    echo "Usage: $0 /path/to/ssh_key"
    exit 1
fi

SSH_KEY="$1"

if [ ! -f "$SSH_KEY" ]; then
    echo "❌ SSH key not found at: $SSH_KEY"
    exit 2
fi

USER="cubbit"
NODES=(
    pi-gateway.vpn.cubbit.dev
    pi-storage1-1.vpn.cubbit.dev
    pi-storage2.vpn.cubbit.dev
    pi-storage3.vpn.cubbit.dev
)
INSTALL_DEPS=false

PROJECT_NAME="neonswarm"
PROJECT_PATH="~/Projects/$PROJECT_NAME"
LOCAL_DIR="$(dirname "$(readlink -f "$0")")"

# Parse flags
for arg in "$@"; do
    case $arg in
    --install)
        INSTALL_DEPS=true
        ;;
    esac
done

echo "==> Starting deployment to ${#NODES[@]} nodes using key: $SSH_KEY"

for NODE in "${NODES[@]}"; do
    echo "🚀 Deploying to $NODE"

    ssh -i "$SSH_KEY" -o IdentitiesOnly=yes "$USER@$NODE" "mkdir -p $PROJECT_PATH"

    rsync -av \
        --exclude='__pycache__' \
        --exclude='*.pyc' \
        --exclude='.venv' \
        -e "ssh -i $SSH_KEY -o IdentitiesOnly=yes" \
        "$LOCAL_DIR/" "$USER@$NODE:$PROJECT_PATH/"

    ssh -i "$SSH_KEY" "$USER@$NODE" bash -c "'
        set -e
        cd $PROJECT_PATH
        if [ ! -d .venv ]; then
            echo \"📦 Creating virtual environment\"
            python3 -m venv .venv
        fi
        if $INSTALL_DEPS; then
            echo \"📦 Installing requirements\"
            . .venv/bin/activate
            pip install --upgrade pip > /dev/null
            pip install -r requirements.txt
        fi
        echo \"✅ Deployment done on $NODE\"
    '"
done

echo "✅ All nodes updated successfully."
