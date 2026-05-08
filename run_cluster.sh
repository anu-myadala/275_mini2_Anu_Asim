#!/usr/bin/env bash
# run_cluster.sh – launch all nodes in background for local testing.
#
# Usage (run from the PROJECT ROOT, not the build dir):
#   bash run_cluster.sh <build_dir> [config_path]
#
# Example:
#   mkdir -p build && cd build && cmake .. && make -j$(nproc) && cd ..
#   bash run_cluster.sh build config/nodes.yaml
#
# For a two-machine deployment, update config/nodes.yaml host addresses
# first, then run the relevant subset of nodes on each machine manually.

set -e

BUILD="${1:?Usage: bash run_cluster.sh <build_dir> [config_path]}"
CFG="${2:-config/nodes.yaml}"
REPO_ROOT="$(cd "$(dirname "$0")" && pwd)"
PY_SERVER="$REPO_ROOT/src/python_server/server.py"

if [[ ! -f "$BUILD/leader" ]]; then
    echo "ERROR: $BUILD/leader not found. Build first: cd build && cmake .. && make"
    exit 1
fi
if [[ ! -f "$PY_SERVER" ]]; then
    echo "ERROR: Python server not found at $PY_SERVER"
    exit 1
fi

echo "=== Starting mini2 cluster ==="
echo "    build : $BUILD"
echo "    config: $CFG"
echo ""

mkdir -p logs

start_node() {
    local name="$1"; shift
    "$@" > "logs/${name}.log" 2>&1 &
    echo "[$name] pid=$!  log=logs/${name}.log"
}

# Start leaves first so they are ready when their parents connect.
start_node node_C  "$BUILD/team_node" C "$CFG"
start_node node_D  "$BUILD/team_node" D "$CFG"
start_node node_F  "$BUILD/team_node" F "$CFG"
sleep 0.2

# Mid-level nodes
start_node node_E  "$BUILD/team_node" E "$CFG"
start_node node_G  "$BUILD/team_node" G "$CFG"
start_node node_H  "$BUILD/team_node" H "$CFG"
start_node node_I  python3 "$PY_SERVER" I "$CFG"
sleep 0.2

# B depends on C, D, E being up
start_node node_B  "$BUILD/team_node" B "$CFG"
sleep 0.2

# Leader last — it fans out to B, H, G, I
start_node leader  "$BUILD/leader"    A "$CFG"
sleep 0.5

echo ""
echo "All nodes started. Run the client with:"
echo "  $BUILD/client $CFG cli1 128"
echo ""
echo "Run benchmarks with:"
echo "  bash benchmark.sh $BUILD $CFG 10"
echo ""
echo "Stop everything with:"
echo "  kill \$(cat logs/*.pid 2>/dev/null) 2>/dev/null || pkill -f 'team_node|leader'"
