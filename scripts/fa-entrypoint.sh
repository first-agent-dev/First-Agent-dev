#!/usr/bin/env bash
set -euo pipefail

# /workspace/src is a live bind-mount from the host; PYTHONPATH lets the
# container pick up code changes without a rebuild.
export PYTHONPATH="/workspace/src${PYTHONPATH:+:$PYTHONPATH}"

if [ -n "${FA_TASK:-}" ]; then
    # Auto-run mode: execute the LLM-driven loop with the supplied task.
    # Optional overrides via compose environment or docker exec -e.
    exec fa run \
        --task "$FA_TASK" \
        --workspace /workspace \
        ${FA_ROLE:+--role "$FA_ROLE"} \
        ${FA_MAX_TURNS:+--max-turns "$FA_MAX_TURNS"} \
        ${FA_RUN_ID:+--run-id "$FA_RUN_ID"}
elif [ $# -gt 0 ]; then
    # Allow manual command override (e.g. docker run ... bash)
    exec "$@"
else
    # Stand-by mode: keep the container alive for manual docker exec.
    exec sleep infinity
fi
