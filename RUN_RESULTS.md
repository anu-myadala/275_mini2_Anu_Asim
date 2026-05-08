# Mini 2 Run Results

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
outliers. For the final two-computer run, use:

- 15 runs per chunk size as the minimum final table.
- 30 runs per chunk size if there is enough time.
- 3 runs only for smoke testing while debugging.

The local table below used 3 runs because it was a quick verification pass. Do
not present it as the final experimental count after the two-computer run.

## Chunk Sweep

Command:

```bash
bash benchmark.sh build config/nodes.yaml 15 | tee results/chunk_sweep_2host.tsv
```

Local debug average of three runs:

| Chunk bytes | Avg total us | Avg chunks | Avg RPC us | Min RPC us | Max RPC us |
|---:|---:|---:|---:|---:|---:|
| 2000 | 423093 | 800 | 528 | 223 | 19252 |
| 8000 | 100274 | 200 | 501 | 219 | 9169 |
| 32000 | 31579 | 50 | 631 | 335 | 7085 |
| 128000 | 19446 | 13 | 1496 | 450 | 11862 |
| 512000 | 9073 | 4 | 2268 | 334 | 7119 |

Takeaway: increasing chunk size reduces total wall time because it reduces the
number of client-leader round trips. The largest chunks have higher per-RPC
latency, but the total request finishes faster because only four chunks are
needed.

## Fairness Run

Command:

```bash
bash benchmark_fairness.sh build config/nodes.yaml 4 32000
```

| Client | Total us | Chunks | Avg RPC us | Max RPC us |
|---|---:|---:|---:|---:|
| cli1 | 91514 | 50 | 1830 | 15658 |
| cli2 | 128746 | 50 | 2574 | 20441 |
| cli3 | 96256 | 50 | 1925 | 29361 |
| cli4 | 97142 | 50 | 1942 | 24460 |

Observation: all clients completed the same 50 chunks. The scheduler prevents a
single client from consuming the whole response stream first, but cli2 was about
41% slower than cli1 in this run. That should be reported as a limitation:
the current fairness policy balances chunk opportunities, not exact end-to-end
latency.

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
- The local fairness run showed cli2 about 41% slower than cli1 even though all
  clients received 50 chunks. This is not hidden in the report: our queue
  balances turns, not exact wall-clock completion time.

## Two-Computer Run Checklist

1. Copy the repo to both machines and build both.
2. Generate or copy the same `shards/` directory to both machines. Each node
   only reads its own `shard_X.bin`, so host2 at minimum needs G, H, and I.
3. Edit `config/nodes.yaml` on both machines:

```yaml
hosts:
  host1: { addr: 192.168.1.10, procs: [A, B, C, D, E, F] }
  host2: { addr: 192.168.1.20, procs: [G, H, I] }
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

Run this after the normal two-host benchmark:

1. Start the cluster normally.
2. Start a client with small chunks so it runs long enough:

```bash
build/client config/nodes.yaml fail_h 2000 0
```

3. While it runs, stop H on host2:

```bash
pkill -f "team_node H"
```

Expected behavior: the client should receive an RPC error instead of a partial
result. Record the exact error line, the number of chunks completed before the
failure, and whether the remaining nodes stayed alive.
