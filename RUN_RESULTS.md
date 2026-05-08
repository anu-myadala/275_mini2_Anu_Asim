# Mini 2 – How to Run, Collect Results, and Update the Report

This guide walks through every step from cloning to having actual benchmark
numbers to drop into the report. Answer to your question at the top:
**yes, two machines on the same network gives you real-world results**,
but a single machine with loopback is sufficient for the benchmarks the
professor expects. Section 4 explains the difference.

---

## 1. Prerequisites

### macOS (with Homebrew)
```bash
brew install cmake grpc protobuf yaml-cpp llvm
# Use Homebrew clang, NOT Xcode clang:
export PATH="/opt/homebrew/opt/llvm/bin:$PATH"
export CC=clang
export CXX=clang++
```

### Ubuntu / Debian
```bash
sudo apt-get update
sudo apt-get install -y \
    cmake \
    libgrpc++-dev \
    protobuf-compiler-grpc \
    libprotobuf-dev \
    libyaml-cpp-dev \
    build-essential \
    python3-pip
```

### Python (both platforms)
```bash
cd src/python_server
pip3 install -r requirements.txt
# Regenerate proto stubs if cluster_pb2.py is missing or proto changed:
bash gen_proto.sh
cd ../..
```

---

## 2. Git Setup and Build

```bash
# 1. Initialize repo and push (one-time)
git init
git add .
git commit -m "Initial mini2 submission"
git remote add origin https://github.com/YOUR_USERNAME/mini2-cmpe275.git
git push -u origin main

# 2. Build (run from project root every time you change code)
mkdir -p build
cd build
cmake .. -DCMAKE_BUILD_TYPE=Release
make -j$(nproc)       # Linux
# make -j$(sysctl -n hw.ncpu)   # macOS
cd ..
```

You should see three binaries in `build/`:
- `leader`
- `team_node`
- `client`

---

## 3. Single-Machine Run (loopback — required baseline)

### Step 1: Start the cluster
Open a terminal in the project root:
```bash
bash run_cluster.sh build config/nodes.yaml
```

This starts all 9 nodes in the background and logs to `logs/`.
Wait ~2 seconds for all gRPC servers to bind their ports.

Verify nodes are up:
```bash
grep "listening on" logs/*.log
```
Expected output (order may vary):
```
logs/leader.log:[A] listening on 0.0.0.0:50051
logs/node_B.log:[B] listening on 0.0.0.0:50052
...
logs/node_I.log:[I] (Python) listening on :50059
```

### Step 2: Single client smoke test
```bash
build/client config/nodes.yaml cli1 128
```
You should see 90 records printed (9 nodes × 10 records each) and a summary like:
```
=== Summary for client 'cli1' ===
  records    : 90
  chunks     : 9
  chunk_size : 128 B
  total_rpc  : 1243 us
  avg_rpc    : 138 us
  min_rpc    : 98 us
  max_rpc    : 312 us
```

### Step 3: Chunk-size sweep (10 runs per size)
```bash
bash benchmark.sh build config/nodes.yaml 10 | tee results/chunk_sweep.tsv
```

This saves a TSV file. Open it in Excel or Numbers to make the chart for
Section 4.1 of the report. Expected pattern:
- `chunk=15` → ~90 chunks, highest total_us (~8,000–15,000 us loopback)
- `chunk=1500` → 1 chunk, lowest total_us (~200–500 us loopback)

### Step 4: Fairness test (4 concurrent clients)
```bash
bash benchmark_fairness.sh build config/nodes.yaml 4 128
```

Expected: all four clients finish within ~5% of each other on total_us.
Results saved to `results/fairness_4clients.txt`.

### Step 5: Stop the cluster
```bash
pkill -f "team_node|leader" ; pkill -f "server.py"
```
Or: `kill $(pgrep -f "team_node|leader|server.py")`

---

## 4. Two-Machine Run (recommended for final results)

Running on two real machines gives you meaningful network latency (1–5 ms
per hop instead of ~50 µs loopback). This is what the professor means by
"two computer minimum configuration."

### Setup
Edit `config/nodes.yaml`. Replace both `127.0.0.1` addresses:
```yaml
hosts:
  host1: { addr: 192.168.1.10, procs: [A, B, C, D, E, F] }  # Machine 1 IP
  host2: { addr: 192.168.1.20, procs: [G, H, I] }            # Machine 2 IP
```
Find your IP with `ip addr` (Linux) or `ifconfig en0` (macOS).

**Both machines need the same `config/nodes.yaml`** — copy it via scp:
```bash
scp config/nodes.yaml user@192.168.1.20:~/mini2/config/nodes.yaml
```

### Machine 1 (runs A–F):
```bash
cd ~/mini2/build
./leader     A ../config/nodes.yaml &
./team_node  B ../config/nodes.yaml &
./team_node  C ../config/nodes.yaml &
./team_node  D ../config/nodes.yaml &
./team_node  E ../config/nodes.yaml &
./team_node  F ../config/nodes.yaml &
```

### Machine 2 (runs G–I):
```bash
cd ~/mini2/build
./team_node  G ../config/nodes.yaml &
./team_node  H ../config/nodes.yaml &
python3 ../src/python_server/server.py I ../config/nodes.yaml &
```

### Client (run from either machine):
```bash
./client ../config/nodes.yaml cli1 128
bash benchmark.sh . ../config/nodes.yaml 10 | tee results/chunk_sweep_2machine.tsv
```

---

## 5. Saving and Committing Results

After collecting data, commit everything:
```bash
# Results live in results/
git add results/
git add logs/          # optional — shows the cluster ran
git commit -m "Add benchmark results: chunk sweep + fairness test"
git push
```

---

## 6. Plugging Numbers into the Report

### Section 4.1 table (chunk size vs latency)
From `results/chunk_sweep.tsv`, take the **average** of all 10 runs for each
chunk size. Fill in the table in the report:

| Chunk (B) | Avg total_us | Chunks | Avg RPC (us) |
|-----------|--------------|--------|--------------|
| 15        | [your number]| [...]  | [...]        |
| ...       | ...          | ...    | ...          |

### Section 4.2 table (fairness)
From `results/fairness_4clients.txt`, copy the four client rows directly.

### Key numbers for the poster stat boxes
- **Latency ratio**: total_us(chunk=15) ÷ total_us(chunk=1500)  →  update "20×" if different
- **Fairness spread**: max(total_us across clients) − min  →  update "CV < 2%" if different
- **Page density**: always 60% (this is structural, not measured — keep it)

---

## 7. Two-Machine vs. Single-Machine: Which to Submit?

You should run on **both** and report both sets. For the submission:
- **Loopback numbers** go in the main results table (reproducible by the grader)
- **Two-machine numbers** go in a short paragraph in Section 4 noting
  the higher absolute latency and the same relative trend

The professor specifically requires a "Final run with at least two computers"
per the mini2 spec. Even if you can only do one real run, document that you did it.

---

## 8. Quick Troubleshooting

| Symptom | Fix |
|---------|-----|
| `Failed to load config` | Run from the project root, not `build/` |
| `Failed to start server` | A port is in use. `lsof -i :50051` to find it. |
| Python `ModuleNotFoundError: cluster_pb2` | Run `bash gen_proto.sh` from `src/python_server/` |
| Nodes connect but client gets 0 records | Check that all 9 nodes are running (`grep listening logs/*.log`) |
| `grpc_cpp_plugin not found` on macOS | `export PATH="/opt/homebrew/bin:$PATH"` |
| macOS SDK conflict (ldiv_t error) | Use Homebrew clang: `export CXX=clang++` with Homebrew LLVM |
