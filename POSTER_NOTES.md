# Mini 2 Poster Notes

## Main Message

Chunk size is the control knob, but validation is what made the result
trustworthy.

This should be treated like a poster, not a project-summary slide. The class
should walk away with one finding: our fastest chunk-size curve looked simple,
but it was only believable after we caught setup and correctness failures that
would have made the benchmark lie.

## Use This Figure

Make a bar chart from `results/chunk_sweep_2host_30runs.tsv`:

| Chunk bytes | Avg total us |
|---:|---:|
| 2000 | 337844 |
| 8000 | 91303 |
| 32000 | 45748 |
| 128000 | 47482 |
| 512000 | 44046 |

Title: `FAST LIES`

Subtitle: `Why our 7.7x chunk-size speedup only counted after validation`

## One-Sentence Result

For the same 80,000 typed 311 records split across two laptops, 512 KB chunks
averaged about 44 ms, while 2 KB chunks took about 338 ms because they required
800 client-leader round trips.

## Important Caveat

Large chunks improve total completion time, but each RPC carries more data and
has higher per-call latency. The best chunk size depends on fairness and memory
pressure, not only raw speed.

## What Makes It Worth Presenting

Do not spend the talk proving that we have A-I processes or a Python server.
Those are baseline requirements. Spend the talk on what we learned:

- A fast graph can be wrong if the tree is partial, ports are stale, or one node
  is using sample data.
- The chunk-size sweep answered the prompt's performance/resource question with
  timing, chunk count, and RPC cost.
- The fairness run answered the balance question honestly: equal chunk turns,
  not equal finish times.
- The H-down test answered the failure/caching question: fail-fast before
  gather, cache-complete after gather.

## Depth Angle

The poster should mention the failures that would have made the graph wrong:

- Early per-RPC stub/channel setup made a prototype measure setup overhead.
- A streaming/async detour was dropped because the assignment wanted unary gRPC
  and explicit chunking.
- An old process on the same port made the client talk to the wrong server.
- Ambiguous tree derivation meant A only queried B's subtree at first.
- Partial child failures could be cached until we changed them to fail fast.
- Python/C++ binary record mismatches made us validate the 20-byte layout.
- Host2 Python initially loaded the wrong `libexpat`, so `grpcio` could not be
  installed until we fixed the Python environment.
- Node I used fallback sample data until the real shards were copied and the
  node was restarted.

This is the part the professor is likely to care about: the final number is less
interesting than how we proved the number was real.

## Visual Layout

Use a dark background with one large horizontal-bar chart on the left. Put the
7.7x number large on the right, then show the round-trip collapse from 800
calls to 4 calls. Under that, use a compact row of validation gates:
stale ports, partial tree, cache bug, binary layout, missing shards.

Keep topology out of the main slide; it belongs in the talk if needed. The
slide should feel like a research poster, not an architecture diagram.

## Small Topology Graphic

```text
client -> A
          |-- B -- C
          |   |-- D
          |   `-- E -- F
          |-- H
          |-- G
          `-- I (Python)
```

## Do Not Put This on the Poster

Avoid listing every class or file. The poster should not be a code tour. Show
the chunk-size result, the validation failures, and one caveat.
