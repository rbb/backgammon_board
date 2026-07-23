#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

out_dir=""
remaining_args=()

while (($# > 0)); do
  case "$1" in
    --out)
      if (($# < 2)); then
        echo "error: --out requires a directory argument" >&2
        exit 1
      fi
      out_dir="$2"
      shift 2
      ;;
    --out=*)
      out_dir="${1#*=}"
      shift
      ;;
    *)
      remaining_args+=("$1")
      shift
      ;;
  esac
done

if [[ -z "$out_dir" ]]; then
  out_dir="."
fi

mkdir -p "$out_dir"
out_dir="$(cd "$out_dir" && pwd)"

for cut_flag in --cut --no-cut; do
  cut_name="${cut_flag#--}"
  for half_flag in --half --no-half; do
    half_name="${half_flag#--}"
    (cd "$script_dir" && uv run build-bg-board \
      "$cut_flag" "$half_flag" \
      --out "$out_dir/backgammon_board_${cut_name}_${half_name}.svg" \
      "${remaining_args[@]}")
  done
done
