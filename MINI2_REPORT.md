# Mini 2 Report

## Research Question

Mini 2 asks what happens when the 311 query is moved from one process into a
distributed group of processes. The question we focused on was:

**When A is the only public entry point and the result set has to be returned in
chunks, how much does chunk size change the total query time?**

The short answer from our final two-computer run is that chunk size mattered a
lot. Returning the same 80,000 typed 311 records in 512 KB chunks averaged about
44 ms, while 2 KB chunks averaged about 338 ms. That is about 7.7x faster, mostly
because the client made 4 round trips instead of 800. The important lesson is
not "always use the biggest chunk." The deeper lesson is that the result only
became believable after we fixed several failures that would have made the graph
wrong.

## Mini 1 Feedback We Applied

Mini 1 gave us a useful warning: a working program is not enough if the report
does not prove why the result happened. The professor's comments pushed us in
four directions for Mini 2:

- Avoid shared merge contention. Mini 1 had a critical section during result
  collection, which made the 8-thread result hard to explain. Mini 2 gathers
  each child response into a separate buffer and merges after the child RPCs
  finish.
- Use tighter data types. The 311 rows are converted into compact binary records
  instead of moving strings through the cluster.
- Pre-size or reuse storage when possible. Shard payloads are loaded as exact
  byte buffers, stubs are created once at startup, and the benchmark prints
  timing summaries instead of every record.
- Keep failed attempts. Several failures changed the final design, so they are
  included as data points instead of hidden.

## System Design

The cluster has one public leader, A, and eight data nodes, B-I. Node I is
implemented in Python; the other nodes are C++. The directed scatter-gather tree
is configured in `config/nodes.yaml`:

```text
A -> B, H, G, I
B -> C, D, E
E -> F
```

Clients only call A. A forwards the query to its children, those nodes fetch
their local shards and recursively fetch their children, and A gathers the final
payload. The client then pages through the gathered result with `QueryOnce`
calls that include a request id, byte offset, and requested chunk size.

We stayed with unary gRPC calls and explicit offsets. An early prototype tried
to move toward streaming, but that was not a good fit for the assignment
constraints and it made the failure cases harder to reason about. Explicit
chunk offsets also made the chunk-size experiment easier to measure.

## Data Representation

The NYC 311 CSV is converted into one binary shard per data node. Each record is
20 bytes:

| Field | Type | Bytes | Why we chose it |
|---|---:|---:|---|
| unique key | int32 | 4 | compact id field |
| latitude | float | 4 | enough precision for city-level spatial filtering |
| longitude | float | 4 | same reason as latitude |
| incident zip | uint32 | 4 | numeric filter field |
| created year | uint16 | 2 | year does not need 4 or 8 bytes |
| status | uint8 | 1 | encoded category |
| borough | uint8 | 1 | encoded category |

This is where the Mini 1 memory-density feedback mattered most. If every row
used CSV strings, the gRPC payload would measure string allocation behavior more
than query behavior. With a fixed 20-byte record, 80,000 records is about 1.6 MB
before gRPC framing, and every chunk size means the same amount of useful data.

## Course and Lab Ideas Used

The implementation was influenced by several course labs and lectures:

- The gRPC lab gave us the basic protobuf/service pattern for `cluster.proto`.
- The leader-election and leader-adv labs shaped the idea of A as the one
  client-facing coordinator.
- The socket and messaging lectures showed why many small messages can be
  slower than fewer larger messages, even when the total byte count is the same.
- The sharding lecture motivated splitting the binary data across B-I instead
  of letting one process own all rows.
- The MPI round/baton style labs influenced the fairness test: the goal was not
  perfect equal finish time, but making sure clients got turns instead of one
  client draining the entire cached result first.

## Measurement Plan

The final chunk sweep used two laptops on the same Wi-Fi. Host 1 ran A-F and
the client. Host 2 ran G, H, and Python node I. We generated 90,000 rows from
the real NYC 311 CSV; A is leader-only, so the query returns 80,000 records from
B-I.

The professor's guidance says the report should include enough runs to support
the conclusion. For the final table we used 30 runs per chunk size. We also kept
separate fairness and failure tests so the performance chart was not the only
evidence.

## Two-Computer Chunk Results

| Chunk bytes | Avg total us | Avg chunks | Avg RPC us |
|---:|---:|---:|---:|
| 2000 | 337844 | 800 | 422 |
| 8000 | 91303 | 200 | 456 |
| 32000 | 45748 | 50 | 914 |
| 128000 | 47482 | 13 | 3652 |
| 512000 | 44046 | 4 | 11011 |

The main trend is the round-trip count. The 2 KB run needed 800 client-leader
calls, while the 512 KB run needed only 4. That is why the largest chunk size
was about 7.7x faster in total time.

The table also shows a tradeoff. The average RPC time grows as the chunk gets
larger, because each response carries more data. The 32 KB, 128 KB, and 512 KB
rows are close in total time, which makes sense on Wi-Fi: once the request count
is low enough, network variation starts to blur the curve. Our conclusion is
therefore careful: larger chunks helped this workload, but the best chunk size
depends on memory pressure, fairness, and network stability.

## Fairness Test

We ran four clients at 32 KB chunks.

| Client | Total us | Chunks | Avg RPC us | Max RPC us |
|---|---:|---:|---:|---:|
| cli1 | 121275 | 50 | 2425 | 70184 |
| cli2 | 120889 | 50 | 2417 | 62902 |
| cli3 | 121798 | 50 | 2435 | 50136 |
| cli4 | 116823 | 50 | 2336 | 83528 |

All four clients received 50 chunks, so the queue did what we needed at the
chunk-turn level. The finish times were not identical. The slowest client was
about 4.3% slower than the fastest client. That means our design gives
opportunity fairness, not strict latency fairness.

## Failures and What We Changed

The old Mini 2 report had a smaller prototype, but its failures were useful.
We kept the lessons that affected the final code and measurement plan.

**Per-RPC setup overhead.** In an early version, outgoing gRPC channels and
stubs were created inside the fetch path. That made the benchmark measure
connection setup too much. The final nodes build their child stubs once during
startup.

**Async/streaming detour.** We tried to reason about a streaming version because
it felt natural for chunked data. It was dropped because the assignment asked
for non-streaming gRPC, and because the completion-queue logic made failure
behavior harder to explain. The final design uses unary requests with explicit
offsets.

**Port collision.** A local test returned bad/empty results because an older
server from another folder was already listening on the same ports. We found it
with `lsof`, killed the old process, and added runbook checks before starting a
cluster.

**Topology ambiguity.** Our first tree derivation let the overlay shape decide
too much, and A only contacted B's subtree. That missed H, G, and I. The final
YAML keeps the directed `children` tree explicit.

**Partial result caching.** A failed child fetch originally risked becoming a
partial cached result. That is dangerous because later pages can look successful
while silently missing shards. The leader now treats a child fetch failure as a
request failure.

**Request id reuse.** Reusing request ids hid some cache behavior during
testing. The benchmark/client now uses unique ids for runs that should not share
state.

**Binary format mismatch.** The Python node exposed an easy mistake: C++ and
Python have to agree on exact record size and field order. We fixed this by
using one 20-byte layout and validating the shard size instead of assuming the
serializer was correct.

**Python environment failures.** On host2, Python setup failed in two ways:
`yaml` was missing at first, and Homebrew Python loaded macOS's older `libexpat`
when installing gRPC packages. The final run used a project virtual environment
and launched Python with the Homebrew expat library path.

**Missing shard deployment.** Node I once warned that it was using fallback
sample data. That was a real measurement danger, because the cluster would have
looked alive while one node was not using the real dataset. We copied the shards
to host2 and restarted node I before collecting final numbers.

**Bad benchmark defaults.** One-record chunks were useful as a stress case, but
they made normal runs painfully slow and hid the trend we cared about. Tiny
chunks are now opt-in. We also found that a 64 KB leader cap made 128 KB and
512 KB tests misleading, so the cap was raised to 1 MB.

**Failure timing.** If H is down before a new request starts, A returns a clear
`child fetch failed: H` error. If H dies after A already gathered and cached the
first page, that same request can still complete from cache. That is a useful
distributed-systems tradeoff: caching protects an active request after gather,
but it also increases memory pressure at A.

## Conclusion

The final result supports one focused conclusion: for this 311 scatter-gather
workload, chunk size is a major control knob because it changes the number of
client-leader round trips. The result is strongest at the extremes: 2 KB chunks
were much slower than 512 KB chunks. The middle values were closer, which tells
us not to overclaim. On a noisy two-laptop Wi-Fi setup, after the round-trip
count is reduced enough, network variation and per-response cost start to
matter.

The failures were just as important as the successful graph. Port collisions,
missing shards, topology mistakes, Python dependency problems, and partial-cache
behavior all could have produced numbers that looked real but were not. The
poster should focus on that discovery instead of summarizing every class or
file: **the fastest curve was only trustworthy after we broke the system and
proved the measurement path.**

## Deliverables

The repo contains the code, the report, and a one-slide poster. For Canvas, the
submission archive should include these project files but should not include the
large 311 CSV or generated shard data.

## Individual Contributions

Anukrithi Myadala focused on the Mini 1 feedback analysis, runbooks,
two-computer setup, result collection, report, and presentation framing. Asim
Mohammed contributed to the cluster/protobuf implementation and helped with the
final code cleanup and validation.

## References

- NYC Open Data, 311 Service Requests dataset.
- Course lectures: messaging/socket costs, sharding, parallelism, failure
  behavior, and benchmarking guidance.
- Course labs: basic gRPC, leader/leader-adv, MPI round/baton, socket examples.
- gRPC C++ and Python documentation for unary RPC service structure.
- Protocol Buffers documentation for typed message definitions.
- Data structure alignment notes used after Mini 1 feedback to avoid assuming
  struct size is only the sum of field sizes.
