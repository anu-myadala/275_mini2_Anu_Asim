# Mini 2 Two-Computer Runbook

This is the exact checklist for running Mini 2 on two laptops on the same
Wi-Fi/network, collecting results, and recording failures. Use your laptop as
`host1` and your husband's laptop as `host2`.

## Goal

The final experiment should show that the same distributed overlay works when
the nodes are split across two machines instead of only running on loopback.

Use this split:

| Machine | Runs |
|---|---|
| host1, your laptop | A, B, C, D, E, F, client, benchmark scripts |
| host2, husband's laptop | G, H, I |

Node A is the leader. Node I is the Python node. All other nodes are C++ team
nodes.

## What To Collect

Save these final files from host1:

| File | Purpose |
|---|---|
| `results/two_host_smoke.txt` | One proof that the cluster returns records |
| `results/chunk_sweep_2host.tsv` | Main performance table, 15 or 30 runs |
| `results/fairness_2host.txt` | Concurrent-client fairness result |
| `results/failure_h_down_2host.txt` | Failure behavior when H is down |
| `results/two_host_notes.md` | Machine specs, IPs, Wi-Fi notes, failures |

For the report/poster, the strongest story is:

1. Loopback is the baseline.
2. Two laptops add real network latency.
3. Larger chunks reduce round trips and usually win on total time.
4. Fairness balances chunk turns, but it does not make every client finish at
   exactly the same time.
5. Failure testing showed whether the leader returns a clear error or a cached
   response.

## Before You Start

Do these on both laptops.

1. Make sure both laptops are on the same Wi-Fi.
2. Turn off VPNs if they block local traffic.
3. Keep both laptops awake and plugged in.
4. Close old copies of this project that might still be listening on ports
   `50051` through `50059`.
5. Use the same git commit on both machines.

Check the commit:

```bash
git rev-parse --short HEAD
```

Both laptops should print the same commit id.

## Step 1: Find Both IP Addresses

On each laptop, run:

```bash
ipconfig getifaddr en0
```

If that prints nothing, try:

```bash
ifconfig | grep "inet " | grep -v 127.0.0.1
```

Your current two-laptop setup:

```text
host1 your laptop:        192.168.1.139
host2 husband's laptop:   192.168.1.118
```

Write the real values into `results/two_host_notes.md`.

## Step 2: Build On Both Laptops

Run from the project root on both laptops:

```bash
mkdir -p build
cmake -S . -B build
cmake --build build -j4
```

Then set up Python on both laptops. This matters because host2 runs node I.

```bash
python3 -m venv venv
venv/bin/python -m pip install -r src/python_server/requirements.txt
```

Quick checks:

```bash
build/client --help
venv/bin/python -c "import grpc, yaml; print('python deps ok')"
```

It is fine if `build/client --help` exits with usage text. The important part
is that the executable exists.

## Step 3: Make Sure Both Laptops Have Shards

If `shards/` already exists on your laptop, copy it to the same project path on
host2.

From host1:

```bash
rsync -av shards/ USERNAME@HOST2_IP:/path/to/anu--asim-275-mini-2/shards/
```

Replace `USERNAME`, `HOST2_IP`, and the path.

If copying is annoying, generate the shards on both laptops using the same CSV
and same limit:

```bash
./scripts/make_shards.py "/path/to/311_Service_Requests_from_2020_to_Present.csv" --limit 90000 --out-dir shards
```

Sanity check on both laptops:

```bash
ls -lh shards
```

You should see shard files for the nodes. Host2 needs at least the shards for
`G`, `H`, and `I`.

## Step 4: Edit `config/nodes.yaml` On Both Laptops

Use the same IP addresses on both machines.

Example:

```yaml
hosts:
  host1: { addr: 192.168.1.139, procs: [A, B, C, D, E, F] }
  host2: { addr: 192.168.1.118, procs: [G, H, I] }
```

Do not leave both addresses as `127.0.0.1` for the two-computer run. That only
works when every process is on the same machine.

## Step 5: Check Ports Are Free

Run this on both laptops:

```bash
lsof -nP -iTCP:50051-50059 -sTCP:LISTEN
```

If old project processes are still running, stop them:

```bash
kill $(cat logs/*.pid 2>/dev/null) 2>/dev/null || true
pkill -f "team_node|leader|src/python_server/server.py" 2>/dev/null || true
```

Run the `lsof` command again. It should print nothing before you start the
cluster.

## Step 6: Test Network Reachability

From host1, ping host2:

```bash
ping HOST2_IP
```

From host2, ping host1:

```bash
ping HOST1_IP
```

Stop ping with `Ctrl+C`.

If ping fails, the laptops are probably not reachable on the same network. Try
the same Wi-Fi, disable VPN, or use a phone hotspot that allows device-to-device
traffic.

## Step 7: Start Host2 First

On host2, from the project root, run each command in a separate terminal tab:

```bash
build/team_node G config/nodes.yaml
```

```bash
build/team_node H config/nodes.yaml
```

```bash
venv/bin/python src/python_server/server.py I config/nodes.yaml
```

Leave these running. If macOS asks about accepting incoming connections, allow
it for this experiment.

Check that host2 is listening:

```bash
lsof -nP -iTCP:50057-50059 -sTCP:LISTEN
```

Expected ports:

| Node | Port |
|---|---:|
| G | 50057 |
| H | 50058 |
| I | 50059 |

## Step 8: Start Host1

On host1, from the project root, run each command in a separate terminal tab.
Start leaves first, then parents, then the leader.

```bash
build/team_node C config/nodes.yaml
```

```bash
build/team_node D config/nodes.yaml
```

```bash
build/team_node F config/nodes.yaml
```

```bash
build/team_node E config/nodes.yaml
```

```bash
build/team_node B config/nodes.yaml
```

```bash
build/leader A config/nodes.yaml
```

Check that host1 is listening:

```bash
lsof -nP -iTCP:50051-50056 -sTCP:LISTEN
```

Expected ports:

| Node | Port |
|---|---:|
| A | 50051 |
| B | 50052 |
| C | 50053 |
| D | 50054 |
| E | 50055 |
| F | 50056 |

## Step 9: Smoke Test

Run this on host1:

```bash
mkdir -p results
build/client config/nodes.yaml two_host_smoke 32000 0 | tee results/two_host_smoke.txt
```

Expected:

- The command completes without an RPC error.
- Records should match the same dataset/shard setup you used locally.
- With the 90,000-row sample and A as leader-only, the earlier local result was
  80,000 records. If your shard generation changed, record the new number.

If this fails, do not start the 15-run benchmark yet. Fix the smoke test first.

## Step 10: Main Chunk Sweep

Use 15 runs per chunk size if time is limited. Use 30 if both laptops are stable
and you have time.

For 15 runs:

```bash
bash benchmark.sh build config/nodes.yaml 15 | tee results/chunk_sweep_2host.tsv
```

For 30 runs:

```bash
bash benchmark.sh build config/nodes.yaml 30 | tee results/chunk_sweep_2host_30runs.tsv
```

The script tests:

```text
2000, 8000, 32000, 128000, 512000 bytes
```

Do not use tiny chunks for the final table unless you clearly label it as a
stress test. Tiny chunks create many round trips and can make the experiment
drag.

## Step 11: Fairness Test

Run this on host1 after the chunk sweep:

```bash
bash benchmark_fairness.sh build config/nodes.yaml 4 32000 | tee results/fairness_2host.txt
```

Record:

- Did all 4 clients finish?
- Did all clients get the same number of chunks?
- How far apart were the fastest and slowest total times?

This is important depth for the presentation: the scheduler is fair by chunk
opportunity, not perfect wall-clock time.

## Step 12: Failure Test, H Down Before Request

This test shows what happens when part of the tree is missing before a new
request starts.

On host2, stop only H:

```bash
pkill -f "team_node H"
```

On host1, run:

```bash
build/client config/nodes.yaml fail_h_down_2host 512000 0 2>&1 | tee results/failure_h_down_2host.txt
```

Expected:

- The client should fail with a clear RPC error.
- It should not silently return partial data.

Good report sentence:

```text
When H was down before a new request, the leader reported a child fetch failure
instead of caching or returning a partial result. This made the failure visible
to the client, which is better correctness behavior than silently hiding data
loss.
```

Restart H before any more normal runs:

```bash
build/team_node H config/nodes.yaml
```

## Step 13: Optional Failure Test, H Dies During Paging

This test is more subtle. If the first page already caused A to gather and cache
the full result, later pages may still finish even after H is stopped.

On host1:

```bash
build/client config/nodes.yaml fail_h_mid_request_2host 2000 0
```

While it is running, stop H on host2:

```bash
pkill -f "team_node H"
```

Record exactly what happened:

- Did the client finish?
- How many chunks completed?
- Did it fail immediately, fail later, or finish from cache?
- Did other nodes stay alive?

This is a good presentation point because it shows the difference between
availability for an already-gathered request and correctness for a new request.

## Step 14: Machine Notes Template

Create this file on host1:

```bash
cat > results/two_host_notes.md <<'EOF'
# Two-Host Notes

Date:
Git commit:

host1:
- owner:
- model:
- OS:
- CPU:
- RAM:
- IP:
- role: A, B, C, D, E, F, client

host2:
- owner:
- model:
- OS:
- CPU:
- RAM:
- IP:
- role: G, H, I

Network:
- same Wi-Fi? yes/no
- VPN off? yes/no
- plugged in? yes/no
- anything unusual:

Smoke test:
- command:
- records:
- chunks:
- total_us:

Chunk sweep:
- runs per chunk size:
- result file:
- fastest chunk size by total_us:
- slowest chunk size by total_us:
- outliers noticed:

Fairness:
- result file:
- fastest client:
- slowest client:
- did every client get same chunks?

Failure:
- result file:
- exact error:
- did it return partial data?

What we learned:
- 
EOF
```

Then fill it in while the run is still fresh.

Useful machine-info commands:

```bash
sw_vers
sysctl -n machdep.cpu.brand_string
sysctl -n hw.memsize
```

## Step 15: Stop Everything

On both laptops:

```bash
pkill -f "team_node|leader|src/python_server/server.py" 2>/dev/null || true
```

Verify ports are clear:

```bash
lsof -nP -iTCP:50051-50059 -sTCP:LISTEN
```

## Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Client says failed to connect | Node not running, wrong IP, firewall blocked | Check `config/nodes.yaml`, `lsof`, and macOS firewall prompt |
| Works on one laptop but not two | `127.0.0.1` still in config | Replace with real LAN IPs on both machines |
| Python node I crashes | Missing Python packages | Run `venv/bin/python -m pip install -r src/python_server/requirements.txt` |
| Records are different between laptops | Shards were generated differently | Copy the same `shards/` directory or regenerate with the same CSV/limit |
| Ports already in use | Old run still alive | Use `lsof` and `pkill` commands above |
| Benchmark has blank fields | Client command failed inside script | Run the smoke test manually and check node terminals |
| First run is slower | Cold start, Wi-Fi, cache warmup | Keep it, but mention outliers; average over 15-30 runs |

## What To Put In The Report

After the two-host run, update `RUN_RESULTS.md` with:

1. The two laptop specs and IP roles.
2. The number of runs per chunk size.
3. The average table from `results/chunk_sweep_2host.tsv`.
4. A loopback vs two-host comparison.
5. The fairness table.
6. The H-down failure result.
7. A short explanation of failures and fixes.

Depth points your professor is likely to care about:

- Chunk size is a round-trip vs payload-size tradeoff.
- The two-host run separates local process overhead from real network overhead.
- The tree shape matters because A waits on B, H, G, and I.
- Caching helps repeated pages but can hide mid-request node death.
- The fairness policy is measurable and imperfect, which is more honest than
  claiming it fully solves fairness.
- Failure behavior should be explicit: partial data is worse than a clear error
  for this dataset query.
