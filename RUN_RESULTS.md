# Mini 2 Run Results

For the detailed two-laptop procedure, use `TWO_COMPUTER_RUNBOOK.md`. This
file is for the measured results and final observations.

Dataset used locally: NYC 311 CSV converted into binary shards with:

```bash
./scripts/make_shards.py "/Users/anumyad/Downloads/311_Service_Requests_from_2020_to_Present_20260209 (1).csv" --limit 90000 --out-dir shards
```

The leader A does not own a shard, so this local sample returns 80,000 records
from B-I. Each row is a 20-byte typed record: key, lat, lon, zip, created year,
status code, and borough code.

## Local Loopback Run

Machine: local macOS loopback, all processes on one host.
Topology: A -> B,H,G,I; B -> C,D,E; E -> F. Node I is Python.

Build and run:

```bash
cmake --build build -j4
bash run_cluster.sh build config/nodes.yaml
build/client config/nodes.yaml cli_smoke3 32000 0
```

Smoke result:

| Chunk bytes | Records | Chunks | Total us | Avg RPC us | Max RPC us |
|---:|---:|---:|---:|---:|---:|
| 32000 | 80000 | 50 | 42770 | 855 | 19205 |

## How Many Runs

The notes recommend testing 15-30 times to form an average and discarding clear
outliers. For the final two-computer run, we used:

- 30 runs per chunk size for the final chunk-sweep table.
- 3 runs only for smoke testing while debugging.

## Chunk Sweep

Final two-host command:

```bash
bash benchmark.sh build config/nodes.yaml 30 | tee results/chunk_sweep_2host_30runs.tsv
```

Two-host average of 30 runs per chunk size:

| Chunk bytes | Avg total us | Avg chunks | Avg RPC us | Min RPC us | Max RPC us |
|---:|---:|---:|---:|---:|---:|
| 2000 | 337844 | 800 | 422 | 155 | 151171 |
| 8000 | 91303 | 200 | 456 | 155 | 92230 |
| 32000 | 45748 | 50 | 914 | 176 | 71574 |
| 128000 | 47482 | 13 | 3652 | 208 | 113591 |
| 512000 | 44046 | 4 | 11011 | 311 | 130184 |

Takeaway: increasing chunk size reduces total wall time because it reduces the
number of client-leader round trips. On the two-laptop run, 512 KB was the
fastest average, but 32 KB and 128 KB were close. The max RPC column shows the
cost of Wi-Fi outliers and cold first requests; those spikes are why averaging
30 runs is more reliable than judging a single request.

## Fairness Run

Command:

```bash
bash benchmark_fairness.sh build config/nodes.yaml 4 32000
```

| Client | Total us | Chunks | Avg RPC us | Max RPC us |
|---|---:|---:|---:|---:|
| cli1 | 121275 | 50 | 2425 | 70184 |
| cli2 | 120889 | 50 | 2417 | 62902 |
| cli3 | 121798 | 50 | 2435 | 50136 |
| cli4 | 116823 | 50 | 2336 | 83528 |

Observation: all clients completed the same 50 chunks. The scheduler prevents a
single client from consuming the whole response stream first. In the two-host
run, the slowest client was about 4.3% slower than the fastest client. The
current fairness policy balances chunk opportunities, not exact end-to-end
latency, so this is a good metric to report instead of claiming perfect
fairness.

## Failures Found During Verification

- Another old Mini 2 process was already listening on ports 50051, 50052, and
  50058. The client connected to the wrong server and returned empty errors.
  Fix: stop old listeners with `lsof -nP -iTCP:50051 -sTCP:LISTEN` and `kill`.
- The original tree derivation only gave A one child, so only B's subtree was
  returned. Fix: make the directed tree explicit in `config/nodes.yaml`.
- The client reused the same request id, so a partial failed response could be
  served from cache. Fix: client request ids now include a per-run timestamp,
  and leader child fetch failures throw instead of caching partial data.
- The Python node failed under system Python because `yaml` was not installed.
  Fix: `run_cluster.sh` uses `venv/bin/python` when it exists.
- The first benchmark attempted 20-byte chunks on 80,000 records, which created
  thousands of client calls and was not useful for iteration. Fix: the default
  benchmark now uses practical chunk sizes; set `MINI2_TINY_CHUNKS=1` only for
  a stress test.
- The leader capped chunk size at 64 KB, so larger requested chunks did not
  actually test larger payload behavior. Fix: the cap is now 1 MB.
- The launcher started processes correctly, but background jobs could disappear
  when the shell closed. Fix: `run_cluster.sh` now uses `nohup` and PID files.
- The early local fairness run had a much wider client spread even though all
  clients received 50 chunks. This is not hidden in the report: our queue
  balances turns, not exact wall-clock completion time.
- The final two-host fairness run was much tighter: the slowest client was
  about 4.3% slower than the fastest, while all clients still received 50
  chunks.
- On host2, Homebrew Python initially loaded macOS's older `libexpat` instead
  of Homebrew's `expat`, which broke `ensurepip` and prevented `grpcio` from
  installing. Fix: use Python 3.12 and run the Python node with
  `DYLD_LIBRARY_PATH=/opt/homebrew/opt/expat/lib:$DYLD_LIBRARY_PATH`.
- The first host2 Python run used fallback sample data because `shards/` was not
  present in the expected project directory yet. Fix: copy the full `shards/`
  directory to host2 before starting node I and restart node I after copying.
- Host2 initially refused `rsync` because Remote Login/SSH was off. Fix: either
  enable Remote Login for user `sasank` or send `shards.zip` by AirDrop and
  unzip it into the project root.

## Two-Computer Run Checklist

1. Copy the repo to both machines and build both.
2. Generate or copy the same `shards/` directory to both machines. Each node
   only reads its own `shard_X.bin`, so host2 at minimum needs G, H, and I.
3. Edit `config/nodes.yaml` on both machines:

```yaml
hosts:
  host1: { addr: 192.168.1.139, procs: [A, B, C, D, E, F] }
  host2: { addr: 192.168.1.118, procs: [G, H, I] }
```

4. On host2, start G, H, and I first:

```bash
build/team_node G config/nodes.yaml
build/team_node H config/nodes.yaml
venv/bin/python src/python_server/server.py I config/nodes.yaml
```

5. On host1, start C, D, F, E, B, then A:

```bash
build/team_node C config/nodes.yaml
build/team_node D config/nodes.yaml
build/team_node F config/nodes.yaml
build/team_node E config/nodes.yaml
build/team_node B config/nodes.yaml
build/leader A config/nodes.yaml
```

6. Run the client and benchmarks from host1:

```bash
build/client config/nodes.yaml two_host_smoke 32000 5
bash benchmark.sh build config/nodes.yaml 15 | tee results/chunk_sweep_2host.tsv
bash benchmark_fairness.sh build config/nodes.yaml 4 32000 | tee results/fairness_2host.txt
```

Add the two-host numbers beside the loopback numbers. Expect higher absolute
latency, especially on the first chunk, but the same trend that larger chunks
reduce total request time.

## Two-Computer Failure Test

Run this after the normal two-host benchmark. There are two useful cases:

Case A: H is down before a new request starts. This should fail fast.

1. Start the cluster normally.
2. Stop H on host2:

```bash
pkill -f "team_node H"
```

3. Start a new client request:

```bash
build/client config/nodes.yaml fail_h_down 512000 0
```

Expected behavior: the client receives an RPC error instead of a partial result.
In local verification, the error was:

```text
RPC error: child fetch failed: H: failed to connect to all addresses; last error:
UNKNOWN: ipv4:192.168.1.118:50058: Failed to connect to remote host:
Connection refused
```

Case B: H dies after the first chunk of the same request. This may still finish
because A caches the gathered result after the first successful page. That is
not a failure of the test; it shows a design tradeoff. The cache protects an
already-gathered request from later node loss, but it also makes A a memory
pressure point.

To try Case B, start a long request and stop H while it is paging:

```bash
build/client config/nodes.yaml fail_h 2000 0
```

Then stop H on host2:

```bash
pkill -f "team_node H"
```

Record which case you ran, the exact error line if any, the number of chunks
completed, and whether the remaining nodes stayed alive.
