# Mini 2 Report

## Research Question

Mini 2 asked us to take the 311 query from Mini 1 and distribute it across a cluster of processes. The specific question we focused on was:

**When A is the only public entry point and results have to come back in chunks, how much does chunk size actually affect total query time?**

The short answer from our final two-computer run: chunk size matters a lot, but not in a simple "bigger is always better" way. Returning the same 80,000 typed 311 records in 512 KB chunks averaged about 44 ms, while 2 KB chunks averaged about 338 ms — that's roughly 7.7x slower. The more interesting finding, though, is the knee around 32 KB. At 32 KB we got ~45.7 ms with 50 pages, and at 512 KB we got ~44.0 ms with just 4 pages. Past 32 KB, the fixed gather/transfer floor and tail variance start to matter more than cutting down page count.

## Mini 1 Feedback We Applied

Mini 1 came with a useful lesson: having a working program isn't enough if the report can't explain *why* the results happened. The feedback pushed us in four directions for Mini 2:

- **Avoid shared merge contention.** In Mini 1, we had a critical section during result collection that made the 8-thread results hard to explain. In Mini 2, each child response goes into its own buffer, and we merge only after all child RPCs finish.
- **Use tighter data types.** Instead of moving strings around the cluster, we convert 311 rows into compact 20-byte binary records.


## System Design

Our cluster has one public leader, A, and eight data nodes, B through I. Node I is implemented in Python; the rest are C++. The scatter-gather tree is defined in `config/nodes.yaml`:

```text
A -> B, H, G, I
B -> C, D, E
E -> F
```

Clients only ever talk to A. A forwards the query to its children, those nodes fetch their local shards and recursively contact their own children, and then A gathers the full payload. The client then pages through that result using `QueryOnce` calls that include a request id, byte offset, and chunk size.

We went with unary gRPC calls and explicit offsets throughout. Explicit chunk offsets made the chunk-size experiment much cleaner to measure.

## Data Representation

We're using a subset of the NYC 311 service request dataset (2020 to present) — 90,000 rows pulled from the public dataset on Data.gov. We used a fixed subset instead of the full thing to keep testing repeatable across machines. The CSV gets converted into one binary shard per data node. Each record is exactly 20 bytes:

| Field | Type | Bytes | Why we chose it |
|---|---:|---:|---|
| unique key | int32 | 4 | compact id field |
| latitude | float | 4 | enough precision for city-level spatial filtering |
| longitude | float | 4 | same reason as latitude |
| incident zip | uint32 | 4 | numeric filter field |
| created year | uint16 | 2 | year doesn't need 4 or 8 bytes |
| status | uint8 | 1 | encoded category |
| borough | uint8 | 1 | encoded category |

This is where the Mini 1 memory-density feedback paid off the most. If every row used CSV strings, the gRPC payload would've been measuring string allocation more than actual query behavior. With a fixed 20-byte record, 80,000 records is about 1.6 MB before gRPC framing, and every chunk size means the same amount of useful data — no noise from variable-length fields.

## Course and Lab Ideas We Used

A few course labs and lectures shaped how we built this:

- The `basic-grpc` lab gave us the protobuf/service pattern — define a small service, generate the stubs, then build the control logic around the calls.
- The `leader-adv` lab influenced how we split coordinator and worker roles. A handles client-facing coordination; B-I do shard work and child fetches.
- The sharding lecture motivated splitting binary data across B-I rather than letting one node own everything.
- The MPI round/baton labs influenced how we thought about the fairness test — we measured whether clients got turns, not just whether the fastest client finished quickly.

## Outside Sources Used

Most of the design came from class material: gRPC, overlays, sharding, fairness, and benchmarking, and from official docs:

- Python's `struct` documentation for the binary record contract shared between C++ and Python. The format string is `<iffIHBB`, which is exactly 20 bytes.
- CMake `add_custom_command` docs and the gRPC C++ basics tutorial for building the generated protobuf/gRPC sources.
- yaml-cpp (C++ side) and PyYAML (Python side) for loading the YAML config.

## Mini 2 Prompt Questions Answered

The Mini 2 prompt asked us to think beyond just making gRPC calls work. Here's how we addressed each challenge:

| Prompt challenge | What we did |
|---|---|
| Most performant way in time/resources | Swept chunk sizes over 30 runs each and measured total time, chunk count, avg RPC time, min RPC time, and max RPC time. |
| Conserve memory | Used 20-byte typed records, explicit chunk offsets, and a 1 MB maximum chunk instead of returning unbounded results. |
| Fairness between endpoints | Ran four clients at the same chunk size. Each received 50 chunks; finish times differed, so we reported opportunity fairness rather than claiming perfect fairness. |
| Flexible overlay | Kept host/process/tree configuration in YAML. Node identity and config path are command-line arguments. |
| Don't flatten the tree | Used the required shape: A -> B, H, G, I; B -> C, D, E; E -> F. An explicit `children` list fixed an early partial-tree bug. |
| Python plus C++ | Implemented I in Python and the rest in C++; verified the Python node was using real shards before collecting final timing. |
| No async/streaming shortcut | Used unary gRPC calls with request id + offset + chunk size, so chunk control stays in our code. |

## Measurement Plan

For the final chunk sweep, we ran two laptops on the same Wi-Fi. Host 1 ran A–F and the client. Host 2 ran G, H, and the Python node I. We generated 90,000 rows from the real NYC 311 CSV; since A is leader-only, the query returns 80,000 records from B-I.

We used 30 runs per chunk size to make sure the conclusions were well-supported, and we kept separate fairness and failure tests so the performance chart wasn't the only evidence.

## Two-Computer Chunk Results

| Chunk bytes | Avg total us | Avg chunks | Avg RPC us |
|---:|---:|---:|---:|
| 2,000 | 337,844 | 800 | 422 |
| 8,000 | 91,303 | 200 | 456 |
| 32,000 | 45,748 | 50 | 914 |
| 128,000 | 47,482 | 13 | 3,652 |
| 512,000 | 44,046 | 4 | 11,011 |

The main story at small chunk sizes is page count. The 2 KB run needed 800 client-to-leader round trips, while the 512 KB run needed only 4 — that's why the largest chunk is ~7.7x faster than the smallest.

The table also shows the knee pretty clearly. Going from 50 pages at 32 KB to 4 pages at 512 KB only improved the mean by about 1.7 ms. The way we read that: chunk size shifts cost from repeated paging overhead into a fixed gather/transfer floor. The first page makes A gather and cache the full 1.6 MB response from B-I. Later pages come from that cache, so small chunks pay for many client-to-A unary RPC/cache-copy steps. Once chunks are big enough, the remaining time is dominated by the one-time gather, payload movement, serialization overhead, and the occasional Wi-Fi spike.

## Mean, Median, and Tail Behavior

| Chunk bytes | Mean ms | Median ms | P90 ms | CV |
|---:|---:|---:|---:|---:|
| 2,000 | 337.8 | 345.6 | 391.7 | 0.14 |
| 8,000 | 91.3 | 85.8 | 105.4 | 0.16 |
| 32,000 | 45.7 | 39.9 | 61.0 | 0.26 |
| 128,000 | 47.5 | 28.3 | 115.3 | 0.74 |
| 512,000 | 44.0 | 25.8 | 110.1 | 0.80 |

CV here is the sample standard deviation divided by the mean across 30 runs. The medians confirm that large chunks are usually faster. But the tail numbers explain why the means flatten out: large chunks are way more sensitive to a single slow remote gather or response spike. In our setup, 512 KB had the best mean and median, but 32 KB was the more robust choice — almost the same mean as 512 KB and a better fit for the fairness test window.

## Fairness Test

We ran four clients simultaneously at 32 KB chunks.

| Client | Total us | Chunks | Avg RPC us | Max RPC us |
|---|---:|---:|---:|---:|
| cli1 | 121,275 | 50 | 2,425 | 70,184 |
| cli2 | 120,889 | 50 | 2,417 | 62,902 |
| cli3 | 121,798 | 50 | 2,435 | 50,136 |
| cli4 | 116,823 | 50 | 2,336 | 83,528 |

All four clients got their 50 chunks, so the queue did what we needed at the chunk-turn level. Finish times weren't identical — the slowest client was about 4.3% slower than the fastest. So what we have is opportunity fairness, not strict latency fairness.

## Failures and What We Changed

Our early prototypes were smaller than the final two-computer run, but honestly the failures were some of the more useful things we went through. Here's what went wrong and what it changed:

**Per-RPC setup overhead.** In an early version, we were creating outgoing gRPC channels and stubs inside the fetch path. That meant the benchmark was measuring connection setup time, not query time. The fix was building child stubs once at startup.

**Port collision.** A local test was returning bad/empty results because an older server from a different folder was already sitting on the same ports. We tracked it down with `lsof` and killed the stale process.

**Topology ambiguity.** Our first tree derivation let the overlay shape decide too much, and A ended up only contacting B's subtree — missing H, G, and I entirely. We fixed this by keeping the directed `children` list explicit in YAML.

**Partial result caching.** A failed child fetch could have turned into a partial cached result. That's dangerous because later pages look successful while silently missing shards. We fixed it so the leader treats any child fetch failure as a full request failure.

**Request id reuse.** Reusing request ids was hiding some cache behavior during testing. The benchmark now uses unique ids for any run that shouldn't share state.

**Python environment failures.** Setting up host2 hit two problems: `yaml` was missing at first, and Homebrew Python was loading macOS's older `libexpat` when installing gRPC packages. The final run uses a project virtual environment and launches Python with the correct Homebrew expat library path.

**Missing shard deployment.** Node I warned us at one point that it was falling back to sample data — a real measurement danger, since the cluster would've looked alive while one node wasn't using the actual dataset. We copied the shards to host2 and restarted node I before collecting any final numbers.

**Failure timing.** If H is down before a new request starts, A returns a clear `child fetch failed: H` error. If H dies *after* A has already gathered and cached the first page, that same request can still complete from cache. That's an interesting distributed systems tradeoff — caching protects an active request after gather, but it also increases memory pressure at A.

## Conclusion

The final result points to one main conclusion: for this 311 scatter-gather workload, chunk size is a major control knob, but the really interesting discovery is the knee. Below 32 KB, repeated paging dominates. Above 32 KB, the fixed gather/transfer floor and tail variance take over. If you just want the lowest mean or median, 512 KB wins. If you care about robustness, fairness, and tail behavior, 32 KB is the better operating point for this two-laptop setup.

The failures were just as important as the results. Port collisions, missing shards, topology mistakes, Python dependency issues, and partial-cache behavior all could have produced numbers that looked real but weren't. The key takeaway: **the fastest curve was only trustworthy after we broke the system and proved the measurement path.**

## Deliverables

The repo includes the code, the report, and a one-slide poster.

## Individual Contributions

| Member | Contributions |
|---|---|
| Anukrithi Myadala | Mini 1 feedback analysis, runbooks, two-computer setup, result collection, report, presentation framing |
| Asim Mohammed | Cluster/protobuf implementation, final code cleanup and validation |

## References

- NYC Open Data / Data.gov, "311 Service Requests from 2020 to Present."
  https://catalog.data.gov/dataset/311-service-requests-from-2010-to-present
- NYC Open Data, "311 Service Requests Updates."
  https://opendata.cityofnewyork.us/311-service-requests-from-2010-to-present-updates/
- gRPC, "Performance Best Practices."
  https://grpc.io/docs/guides/performance/
- Protocol Buffers, "Encoding."
  https://protobuf.dev/programming-guides/encoding/
- Protocol Buffers, "Language Guide (proto3)."
  https://protobuf.dev/programming-guides/proto3/
- Python documentation, "`struct` - Interpret bytes as packed binary data."
  https://docs.python.org/3/library/struct.html
- CMake documentation, "`add_custom_command`."
  https://cmake.org/cmake/help/latest/command/add_custom_command.html
- gRPC, "Basics tutorial: C++."
  https://grpc.io/docs/languages/cpp/basics/
- PyYAML documentation.
  https://pyyaml.org/wiki/PyYAMLDocumentation
- yaml-cpp project documentation.
  https://github.com/jbeder/yaml-cpp
- python-pptx documentation.
  https://python-pptx.readthedocs.io/
- Matplotlib documentation, `barh`.
  https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.barh.html
- AMD Vitis HLS Documentation, "Data Structure Padding."
  https://docs.amd.com/r/2024.1-English/ug1399-vitis-hls/Data-Structure-Padding
- Course labs: `basic-grpc`, `leader-adv`, MPI round/baton, and socket interoperability examples.
