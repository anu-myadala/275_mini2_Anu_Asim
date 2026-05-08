# Mini 2 Requirements Checklist

## Assignment Requirements

| Requirement | Status | Evidence |
|---|---|---|
| Use Mini 1 data or equivalent realistic data | Done | NYC 311 CSV converted by `scripts/make_shards.py` |
| Move away from linear search toward distributed organization | Done | Sharded B-I data nodes with configured scatter-gather tree |
| Use gRPC for process communication | Done | `proto/cluster.proto`, C++ and Python gRPC services |
| Do not use gRPC async/streaming APIs | Done | Uses unary `QueryOnce` and explicit chunk offsets |
| A-I processes | Done | A leader, B-H C++ team nodes, I Python node |
| Minimum two-computer final run | Pending | Local run done; two-computer checklist is in `RUN_RESULTS.md` |
| C++ server and client | Done | `build/leader`, `build/team_node`, `build/client` |
| Python server | Done | `src/python_server/server.py` for node I |
| Do not hardcode identity/hostnames | Done | Node id and config path are command-line arguments; hosts in YAML |
| Use tree overlay, not flat shortcut | Done | `children` tree in `config/nodes.yaml` |
| A is the only client-facing responder | Done | Client uses `cfg.root()` and only calls `LeaderService` |
| No shared memory responses | Done | Data moves through gRPC payloads |
| Realistic typed structures | Done | 20-byte typed 311 record, no string payload records |
| Fairness/balance explored | Done | Fair queue plus four-client benchmark |
| Failures documented | Done | Port collision, topology bug, partial cache bug, Python env, chunk cap, H-down behavior |
| 15-30 benchmark runs for final table | Pending | Script defaults to 15; local debug table used 3 |
| One-slide poster is a single finding | Done | Poster focuses on chunk-size result plus validation failures |

## Final Before Submission

Run these on the two-computer setup:

```bash
bash benchmark.sh build config/nodes.yaml 15 | tee results/chunk_sweep_2host.tsv
bash benchmark_fairness.sh build config/nodes.yaml 4 32000 | tee results/fairness_2host.txt
```

Then run two failure checks:

```bash
pkill -f "team_node H"
build/client config/nodes.yaml fail_h_down 512000 0
```

Restart H, run a long client request, then kill H after the first page:

```bash
build/client config/nodes.yaml fail_h_cached 2000 0
pkill -f "team_node H"
```

Record whether the request failed or completed from cache.
