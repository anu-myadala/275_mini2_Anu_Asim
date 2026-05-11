# Mini 2: Distributed 311 Query Chunking

This project implements a distributed query system over NYC 311 data. The
cluster has one public leader, A, and eight data nodes, B-I. Nodes communicate
with unary gRPC calls, and the client pages through the gathered result with an
explicit chunk size.

Team members: Anukrithi Myadala and Asim Mohammed.

The final report finding is that chunk size strongly controlled total request
time in the two-laptop run. For the same 80,000 typed records, 512 KB chunks
averaged about 44 ms while 2 KB chunks averaged about 338 ms, mostly because the
client made 4 round trips instead of 800.

## Important Files

- `MINI2_REPORT.md` and `mini2-report.docx`: final report.
- `mini2-poster.pptx`: one-slide presentation.
- `RUN_RESULTS.md`: measured two-computer results and failure observations.
- `TWO_COMPUTER_RUNBOOK.md`: detailed run instructions.
- `INSTALL.md`: build and dependency notes.
- `scripts/make_shards.py`: converts the 311 CSV into binary shards.
- `config/nodes.yaml`: host/process/tree configuration.

Do not include the large 311 CSV or generated `shards/` directory in the Canvas
submission archive.
