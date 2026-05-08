#!/usr/bin/env bash
# benchmark_fairness.sh – verify WFQ fairness with N concurrent clients.
#
# Run from the PROJECT ROOT after starting the cluster.
#
# Usage:
#   bash benchmark_fairness.sh <build_dir> [config_path] [num_clients] [chunk_size]
#
# Example:
#   bash benchmark_fairness.sh build config/nodes.yaml 4 128

BUILD="${1:?Usage: bash benchmark_fairness.sh <build_dir> [config_path] [num_clients] [chunk_bytes]}"
CFG="${2:-config/nodes.yaml}"
N="${3:-4}"
SZ="${4:-128}"

mkdir -p results
TMPDIR=$(mktemp -d)

echo "Launching $N concurrent clients with chunk_size=${SZ}B..."

PIDS=()
for i in $(seq 1 "$N"); do
    "$BUILD/client" "$CFG" "cli${i}" "$SZ" > "$TMPDIR/cli${i}.out" 2>&1 &
    PIDS+=($!)
done

for PID in "${PIDS[@]}"; do wait "$PID"; done

echo ""
echo "=== Per-client summary ==="
printf "%-8s %12s %8s %12s %12s\n" "Client" "total_us" "chunks" "avg_rpc_us" "max_rpc_us"
for i in $(seq 1 "$N"); do
    TOTAL=$(awk -F': ' '/total_rpc/{gsub(/ us/,"",$2); print $2}' "$TMPDIR/cli${i}.out")
    CHUNKS=$(awk -F': ' '/^  chunks/{gsub(/ /,"",$2); print $2}' "$TMPDIR/cli${i}.out")
    AVG=$(awk -F': ' '/avg_rpc/{gsub(/ us/,"",$2); print $2}' "$TMPDIR/cli${i}.out")
    MAXV=$(awk -F': ' '/max_rpc/{gsub(/ us/,"",$2); print $2}' "$TMPDIR/cli${i}.out")
    printf "%-8s %12s %8s %12s %12s\n" "cli${i}" "$TOTAL" "$CHUNKS" "$AVG" "$MAXV"
done | tee results/fairness_${N}clients.txt

rm -rf "$TMPDIR"
echo ""
echo "Results saved to results/fairness_${N}clients.txt"
