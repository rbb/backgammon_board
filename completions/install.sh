#!/usr/bin/env bash
# Install bash tab completion for build-bg-board and build-hex-rosette.
#
# Usage:
#   source completions/install.sh          # current shell only
#   ./completions/install.sh --persist     # append to ~/.bashrc

set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
register_cmd=()

if command -v register-python-argcomplete >/dev/null 2>&1; then
    register_cmd=(register-python-argcomplete)
elif [[ -x "${repo_root}/.venv/bin/register-python-argcomplete" ]]; then
    register_cmd=("${repo_root}/.venv/bin/register-python-argcomplete")
elif [[ -x "${repo_root}/.venv/bin/python" ]]; then
    register_cmd=("${repo_root}/.venv/bin/python" -m argcomplete._scripts.register_python_argcomplete)
else
    echo "error: register-python-argcomplete not found; run 'uv sync' first" >&2
    exit 1
fi

completion_snippet="$("${register_cmd[@]}" build-bg-board build-hex-rosette)"

if [[ "${1:-}" == "--persist" ]]; then
    marker="# backgammon-board CLI tab completion"
    if grep -Fq "${marker}" "${HOME}/.bashrc" 2>/dev/null; then
        echo "Completion already present in ~/.bashrc"
    else
        {
            echo ""
            echo "${marker}"
            echo "${completion_snippet}"
        } >>"${HOME}/.bashrc"
        echo "Appended completion to ~/.bashrc; run 'source ~/.bashrc' or open a new shell"
    fi
else
    eval "${completion_snippet}"
    echo "Loaded tab completion for build-bg-board and build-hex-rosette in this shell"
fi
