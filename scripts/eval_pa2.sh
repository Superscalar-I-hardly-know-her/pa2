#!/bin/bash
# Build and, when traces are present, run the PA2 configurations.
#
# Task 1: ./build_champsim.sh no|ip_stride|spp lru <name>
# Task 2: ./build_champsim.sh no irrip|dyn_irrip <name>
# Task 3: ./build_champsim.sh spp dyn_irrip spp_dyn_irrip
#         The Task 3 run sets DYN_IRRIP_PREFETCH=1. Without that flag the
#         same replacement file behaves as Task 2 dynamic I-RRIP.
#
# Stats are taken from the Region of Interest section only. See plot_pa2.py.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$ROOT"

export CC="${CC:-gcc-7}"
export CXX="${CXX:-g++-7}"
export CHAMPSIM_REQUIRE_GCC7="${CHAMPSIM_REQUIRE_GCC7:-1}"

WARMUP="${WARMUP:-25000000}"
SIM="${SIM:-25000000}"
TRACE_DIR="${TRACE_DIR:-}"
if [ -z "$TRACE_DIR" ]; then
    if [ -d traces ] && compgen -G "traces/*.gz" > /dev/null; then
        TRACE_DIR=traces
    else
        TRACE_DIR=../traces
    fi
fi

LOG_ROOT=results/pa2/logs
mkdir -p "$LOG_ROOT"

build_one() {
    local pref="$1" repl="$2" name="$3"
    echo "=== ./build_champsim.sh $pref $repl $name ==="
    ./build_champsim.sh "$pref" "$repl" "$name"
}

binary_for() {
    local pref="$1" repl="$2" name="$3"
    echo "bin/hashed_perceptron-no-${pref}-no-no-no-no-no-lru-lru-lru-${repl}-lru-lru-lru-lru-1core-${name}"
}

run_one() {
    local pref="$1" repl="$2" name="$3" trace="$4"
    local bin
    bin=$(binary_for "$pref" "$repl" "$name")
    local base
    base=$(basename "$trace")
    base="${base%.gz}"
    base="${base%.xz}"
    local log="$LOG_ROOT/$name/${base}.log"
    mkdir -p "$(dirname "$log")"
    if [ "${RERUN:-0}" != 1 ] && grep -q "Region of Interest Statistics" "$log" 2>/dev/null; then
        echo "skip $name $base"
        return
    fi

    local env_args=()
    if [ "$name" = "spp_dyn_irrip" ]; then
        env_args+=(env DYN_IRRIP_PREFETCH=1)
    fi

    echo "run $name $base"
    "${env_args[@]}" "$bin" -warmup_instructions "$WARMUP" -simulation_instructions "$SIM" -traces "$trace" > "$log"
}

MODE="${1:-all}"
case "$MODE" in
    --build-only|build) DO_BUILD=1; DO_RUN=0; DO_PLOT=0 ;;
    --run-only|run) DO_BUILD=0; DO_RUN=1; DO_PLOT=1 ;;
    --plots-only|plots) DO_BUILD=0; DO_RUN=0; DO_PLOT=1 ;;
    all) DO_BUILD=1; DO_RUN=1; DO_PLOT=1 ;;
    *) echo "usage: $0 [all|--build-only|--run-only|--plots-only]" >&2; exit 1 ;;
esac

if [ "$DO_BUILD" = 1 ]; then
    build_one no lru baseline
    build_one ip_stride lru ip_stride
    build_one spp lru spp
    build_one no irrip irrip
    build_one no dyn_irrip dyn_irrip
    build_one spp dyn_irrip spp_dyn_irrip
fi

if [ "$DO_RUN" = 1 ]; then
    shopt -s nullglob
    traces=("$TRACE_DIR"/*.gz "$TRACE_DIR"/*.xz)
    if [ "${#traces[@]}" -eq 0 ]; then
        echo "no traces in $TRACE_DIR" >&2
        exit 1
    fi
    for trace in "${traces[@]}"; do
        run_one no lru baseline "$trace"
        run_one ip_stride lru ip_stride "$trace"
        run_one spp lru spp "$trace"
        run_one no irrip irrip "$trace"
        run_one no dyn_irrip dyn_irrip "$trace"
        run_one spp dyn_irrip spp_dyn_irrip "$trace"
    done
fi

if [ "$DO_PLOT" = 1 ]; then
    python3 scripts/plot_pa2.py --logs "$LOG_ROOT" --out results/pa2
fi
