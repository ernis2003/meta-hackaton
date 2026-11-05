#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
# A Linux venv is distinct from the Windows .venv-ai.
source .venv-ai-wsl/bin/activate
exec python -m src.ai.training.run_pipeline "$@"
