# Mini 2 Report Draft

## What We Changed After Mini 1

Mini 1 showed that a working implementation is not enough; the report has to
prove why the design behaves the way it does. The main takeaways we applied in
Mini 2 were:

- Avoid shared merge contention. Mini 1 used a critical section during result
  collection, which made the 8-thread result hard to interpret. Mini 2 gathers
  child replies into separate buffers and merges after the child RPCs complete.
- Do not use strings for typed fields. Each 311 row is stored as a 20-byte binary
  record instead of CSV strings.
- Pre-size or reuse storage where possible. Payload strings reserve or load the
  exact shard bytes, child stubs are created once at startup, and benchmark code
  avoids printing every row.
- Test a specific claim. For Mini 2 the claim is not "gRPC is fast"; it is that
  chunk size controls the memory/latency tradeoff in a distributed result set.

## System Design

The cluster has one public leader, A, and eight data nodes, B-I. Node I is
implemented in Python; the rest are C++. The directed scatter-gather tree is
configured in `config/nodes.yaml`:

```text
A -> B, H, G, I
B -> C, D, E
E -> F
```

Clients only call A. A forwards the query to its children, children recursively
fetch their subtrees, and A returns the final result set in client-requested
chunks. The first request for a logical query gathers and caches the full result;
later `QueryOnce` calls page through the cached payload by byte offset.

## Data Representation

The 311 CSV is converted into one binary shard per node. Each record is:

| Field | Type | Bytes | Reason |
|---|---:|---:|---|
| unique key | int32 | 4 | 311 id fits in signed 32-bit |
| latitude | float | 4 | enough precision for city-level spatial queries |
| longitude | float | 4 | same as latitude |
| incident zip | uint32 | 4 | numeric filter field |
| created year | uint16 | 2 | 4-digit year without 8-byte storage |
| status | uint8 | 1 | encoded category |
| borough | uint8 | 1 | encoded category |

The packed record is 20 bytes. This is the Mini 1 data-density lesson applied
directly: avoid `std::string` payloads and avoid `double` when `float` is enough.

## Results

For validation, we generated 90,000 rows from the real NYC 311 CSV. A is
leader-only, so the query returns 80,000 records from B-I. The final run split
the cluster across two laptops on the same Wi-Fi:

```text
host1: A, B, C, D, E, F, client
host2: G, H, I
```

The course notes recommend averaging 15-30 runs and discarding clear outliers.
The table below uses 30 runs per chunk size.

| Chunk bytes | Avg total us | Avg chunks | Avg RPC us |
|---:|---:|---:|---:|
| 2000 | 337844 | 800 | 422 |
| 8000 | 91303 | 200 | 456 |
| 32000 | 45748 | 50 | 914 |
| 128000 | 47482 | 13 | 3652 |
| 512000 | 44046 | 4 | 11011 |

The largest chunks finished about 7.7x faster than 2 KB chunks because they
reduced the number of client-leader round trips from 800 to 4. The cost is
higher per-call latency and larger per-response memory pressure. The 32 KB,
128 KB, and 512 KB results were close on Wi-Fi, which is a useful reminder that
network outliers can flatten a benchmark curve even when the round-trip-count
trend is clear.

## Fairness

With four clients at 32 KB chunks, each client received 50 chunks.

| Client | Total us | Chunks | Avg RPC us | Max RPC us |
|---|---:|---:|---:|---:|
| cli1 | 121275 | 50 | 2425 | 70184 |
| cli2 | 120889 | 50 | 2417 | 62902 |
| cli3 | 121798 | 50 | 2435 | 50136 |
| cli4 | 116823 | 50 | 2336 | 83528 |

The fair queue balances chunk turns, but it does not guarantee identical
end-to-end latency. In the two-host run, all four clients received 50 chunks and
the slowest client was about 4.3% slower than the fastest client. The honest
conclusion is that the current design improves opportunity fairness but does
not prove strict latency fairness.

## Failures and Fixes

The first local run returned zero records because an unrelated old server was
already bound to the same ports. We verified this with `lsof` and stopped the
old process.

The second run returned only 50,000 records. The cause was tree ambiguity in the
overlay derivation: A only contacted B. We fixed this by keeping the assignment
overlay in YAML and adding an explicit directed `children` tree.

A failed child fetch originally produced a partial cached result. That was
dangerous because later pages could look successful while missing shards. The
leader now treats child fetch failure as a request failure, and the client uses
a unique request id for each run.

The Python node failed under the system Python because `yaml` was not installed.
The launcher now chooses `venv/bin/python` when the project virtual environment
exists.

The host2 Python setup exposed a lower-level environment problem: Homebrew
Python loaded macOS's older `libexpat`, which broke `ensurepip` and prevented
`grpcio` from installing. We fixed the run by using Python 3.12 and launching
node I with Homebrew's expat library path.

The first host2 Python run also warned that it was using fallback sample data.
The cause was that `shards/` had not been copied into the expected project
directory yet. We copied the real shards to host2 and restarted node I before
collecting final numbers.

Our first benchmark settings included one-record chunks. That was useful as a
stress case, but it made normal result collection too slow and hid the main
payload-size trend. The benchmark script now uses practical chunk sizes by
default and keeps the tiny chunks behind `MINI2_TINY_CHUNKS=1`.

We also found that the leader silently clamped requested chunks to 64 KB. That
made 128 KB and 512 KB tests misleading. The cap is now 1 MB, so the sweep
actually measures large payloads.

One important limitation remains: the fair queue schedules equal chunk turns,
not equal finish times. In the four-client two-host run, each client completed
50 chunks, but cli3 still finished about 4.3% slower than cli4.

Failure timing also mattered. If H is down before a new request starts, A fails
the request clearly instead of returning a partial answer. In two-host
verification, the client received `child fetch failed: H`. If H dies after A has already
gathered and cached the first page, the same request can still finish from
cache. This is a real design tradeoff: caching protects an active request after
gather, but it increases memory pressure at A.

## What Is Still Missing for the Final Submission

Run a larger shard generation, ideally millions of records if time allows:

```bash
./scripts/make_shards.py "/path/to/311.csv" --limit 9000000 --out-dir shards
```

The two-computer benchmark, fairness run, and H-down failure test are complete.
If time allows, add one more experiment where H is killed after the first page is
cached. Do not hide the difference; it is one of the more interesting
distributed-systems lessons in the project.

## Notes and Course Concepts Used

The design was checked against the course notes in four places. First, the
benchmark count follows the notes' 15-30 run recommendation. Second, the chunk
experiment follows the socket lecture's warning that small payloads increase
latency overhead while large payloads increase buffer pressure. Third, the
explicit shards follow the sharding lecture's emphasis on splitting large data
sets for scalability and parallel request handling. Fourth, the failure section
uses the failure/recovery lecture idea of fail-fast behavior when a resource
cannot be reached.

## Poster Claim

Use one focused poster point:

**Chunk size is the control knob: on our two-laptop 80,000-record run, moving
from 2 KB chunks to 512 KB chunks reduced average total request time from
338 ms to 44 ms, but that conclusion only became trustworthy after we fixed port
collisions, tree ambiguity, partial-result caching, Python environment issues,
and missing shard deployment.**

That is stronger than a general architecture summary because it has a claim,
evidence, failures, and a tradeoff.
