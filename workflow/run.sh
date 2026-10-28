#!/bin/bash
set -euo pipefail

# Alfred does not load interactive shell startup files.
export PATH="${HOME}/.local/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
# pbpaste and pbcopy use the locale to select their byte encoding.
export LC_ALL=en_US.UTF-8

if ! command -v uv >/dev/null 2>&1; then
    printf 'String Operations: install uv first (https://docs.astral.sh/uv/getting-started/installation/).\n' >&2
    exit 1
fi

# Select a base interpreter, not a virtual environment; never download at runtime.
if ! python=$(uv python find --system --no-project --no-config --offline --no-python-downloads ">=3.10"); then
    printf 'String Operations: Python 3.10+ is required. Run: uv python install 3.12\n' >&2
    exit 1
fi

workflow_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
exec "$python" -I -B "$workflow_dir/string_operations.py" "$@"
