# Mini 2 Requirements Checklist

## Assignment Requirements

| Requirement | Status | Evidence |
|---|---|---|
| Code included | Done | C++ leader/client/team node, Python node I, scripts, config, proto |
| Report included | Done | `MINI2_REPORT.md` and generated `mini2-report.docx` |
| One-page presentation included | Done | `mini2-poster.pptx`, `POSTER_NOTES.md`, `POSTER_SPEAKING_NOTES_10MIN.md` |
| Use Mini 1 data or equivalent realistic data | Done | NYC 311 CSV converted by `scripts/make_shards.py` |
| Do not include test data in submission | Done | Large CSV/shards should stay out of the Canvas archive |
| Move away from one-process linear search | Done | Sharded B-I data nodes with a configured scatter-gather tree |
| Use gRPC for process communication | Done | `proto/cluster.proto`, C++ services, Python service |
| Avoid gRPC async/streaming APIs | Done | Unary `QueryOnce`/`Fetch` calls with explicit chunk offsets |
| A-I processes | Done | A leader, B-H C++ team nodes, I Python node |
| Minimum two-computer final run | Done | `results/chunk_sweep_2host_30runs.tsv`, fairness and failure logs |
| C++ server and client | Done | `build/leader`, `build/team_node`, `build/client` |
| Python server | Done | `src/python_server/server.py` for node I |
| Do not hardcode identity/hostnames | Done | Node id and config path are command-line arguments; hosts in YAML |
| Use tree overlay, not a flat shortcut | Done | Explicit `children` tree in `config/nodes.yaml` |
| A is the only client-facing responder | Done | Client calls `cfg.root()` and only uses `LeaderService` |
| No shared-memory responses | Done | Data moves through gRPC payloads |
| Realistic typed structures | Done | 20-byte typed 311 record, not string payload records |
| Fairness/balance explored | Done | Fair queue plus four-client two-host benchmark |
| Failures documented | Done | Report includes port, topology, cache, Python, shard, chunk-cap, and H-down failures |
| 15-30 benchmark runs for final table | Done | Final chunk sweep uses 30 runs per chunk size |
| Tabular and graph results | Done | Tables in report, chart in `results/chunk_sweep_chart.png` and poster |
| Presentation is a single finding | Done | Poster focuses on chunk size plus validation failures, not a project summary |
| Individual contributions included | Done | Included in `MINI2_REPORT.md` |
```
