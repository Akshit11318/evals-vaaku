#!/usr/bin/env bash
# Run on the GPU box after the repository is at ~/vaku.
set -euo pipefail
cd "$(dirname "$0")/.."

sudo DEBIAN_FRONTEND=noninteractive apt-get update
sudo DEBIAN_FRONTEND=noninteractive apt-get install -y \
  python3-venv python3-dev ffmpeg libsndfile1 nvidia-driver-580

python3 -m venv .venv
.venv/bin/python -m pip install -U pip
if ! .venv/bin/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu128; then
  .venv/bin/python -m pip install torch torchaudio --index-url https://download.pytorch.org/whl/cu130
fi
.venv/bin/python -m pip install -r requirements.txt

if [[ ! -f .env ]]; then
  umask 077
  cat > .env << EOF
DASHBOARD_TOKEN=
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8787
DASHBOARD_AUTH_DISABLED=1
DATA_DIR=data
OUTPUT_DIR=outputs
DB_PATH=outputs/benchmark.db
LOG_LEVEL=INFO
PREFER_GPU=1
ALLOW_CPU_FALLBACK=1
INDIC_DECODER=rnnt
MAX_SAMPLES=200
EOF
fi

sudo cp scripts/vaku.service /etc/systemd/system/vaku.service
sudo systemctl daemon-reload
sudo systemctl enable vaku
sudo systemctl restart vaku
echo "SETUP_OK"
