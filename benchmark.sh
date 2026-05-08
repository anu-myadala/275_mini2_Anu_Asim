#!/usr/bin/env bash
# benchmark.sh – sweep chunk sizes and record latency results.
#
# Run from the PROJECT ROOT after starting the cluster (run_cluster.sh).
#
# Usage:
#   bash benchmark.sh <build_dir> [config_path] [runs_per_size]
#
# Output: TSV to stdout and results/chunk_sweep.tsv
# Example:
#   bash benchmark.sh build config/nodes.yaml 15 | tee results/chunk_sweep.tsv

BUILD="${1:?Usage: bash benchmark.sh <build_dir> [config_path] [runs_per_size]}"
CFG="${2:-config/nodes.yaml}"
RUNS="${3:-15}"

mkdir -p results

# Chunk sizes to sweep (bytes). Keep the default practical for real shards.
# Set MINI2_TINY_CHUNKS=1 for a stress run with 20/100/200-byte chunks.
if [[ "${MINI2_TINY_CHUNKS:-0}" == "1" ]]; then
    SIZES=(20 100 200 400 1000 2000 8000 32000)
else
    SIZES=(2000 8000 32000 128000 512000)
fi

echo -e "chunk_bytes\trun\ttotal_us\trecords\tchunks\tavg_rpc_us\tmin_rpc_us\tmax_rpc_us"

for SZ in "${SIZES[@]}"; do
    for RUN in $(seq 1 "$RUNS"); do
        OUTPUT="$("$BUILD/client" "$CFG" "bench_cli" "$SZ" 0 2>/dev/null)"
        TOTAL=$(echo "$OUTPUT" | awk -F': ' '/total_rpc/{gsub(/ us/,"",$2); print $2}')
        RECS=$(echo  "$OUTPUT" | awk -F': ' '/^  records/{gsub(/ /,"",$2); print $2}')
        CHUNKS=$(echo "$OUTPUT"| awk -F': ' '/^  chunks/{gsub(/ /,"",$2); print $2}')
        AVG=$(echo   "$OUTPUT" | awk -F': ' '/avg_rpc/{gsub(/ us/,"",$2); print $2}')
        MINV=$(echo  "$OUTPUT" | awk -F': ' '/min_rpc/{gsub(/ us/,"",$2); print $2}')
        MAXV=$(echo  "$OUTPUT" | awk -F': ' '/max_rpc/{gsub(/ us/,"",$2); print $2}')
        echo -e "${SZ}\t${RUN}\t${TOTAL}\t${RECS}\t${CHUNKS}\t${AVG}\t${MINV}\t${MAXV}"
    done
done
