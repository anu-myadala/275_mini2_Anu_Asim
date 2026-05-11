# Mini 2 Poster Notes

## Main Message

Chunk size has a knee around 32 KB: below it, repeated paging dominates; above
it, the fixed gather/transfer floor and tail variance dominate.

This should be treated like a poster, not a project-summary slide. The class
should walk away with one finding: **repeated pages dominate until they do not**.
The 512 KB mean is fastest, but 32 KB is the robust operating point because it
is near the fastest mean with much lower tail risk.

## Use This Figure

Make a chart from `results/chunk_sweep_2host_30runs.tsv`. Bars should show mean
total time, dots should show median total time, and small ticks should show P90.

| Chunk bytes | Mean ms | Median ms | P90 ms | CV |
|---:|---:|---:|---:|---:|
| 2000 | 337.8 | 345.6 | 391.7 | 0.14 |
| 8000 | 91.3 | 85.8 | 105.4 | 0.16 |
| 32000 | 45.7 | 39.9 | 61.0 | 0.26 |
| 128000 | 47.5 | 28.3 | 115.3 | 0.74 |
| 512000 | 44.0 | 25.8 | 110.1 | 0.80 |

Title: `THE 32 KB KNEE`

Subtitle: `Repeated pages dominated until the gather/cache floor took over`

## One-Sentence Result

For the same 80,000 typed 311 records split across two laptops, 512 KB chunks
averaged about 44 ms while 2 KB chunks took about 338 ms. But the real discovery
is that 32 KB and 512 KB means were only 1.7 ms apart, so the useful design point
is the knee, not blindly choosing the largest chunk.

## Important Caveat

Large chunks improve typical completion time, but they have higher tail risk.
The best chunk size depends on fairness, memory pressure, and p90 behavior, not
only raw mean speed.

## What Makes It Worth Presenting

Do not spend the talk proving that we have A-I processes or a Python server.
Those are baseline requirements. Spend the talk on what we learned:

- A fast graph can be wrong if the tree is partial, ports are stale, the cache
  is stale, the chunk cap is hidden, or one node is using sample data.
- The chunk-size sweep answered the prompt's performance/resource question with
  timing, chunk count, median, p90, and variance.
- The fairness run answered the balance question honestly: equal chunk turns,
  not equal finish times.
- The H-down test answered the failure/caching question: fail-fast before
  gather, cache-complete after gather.

## Depth Angle

The poster should mention the failures that would have made the graph wrong:

- An old process on the same port made the client talk to the wrong server.
- Ambiguous tree derivation meant A only queried B's subtree at first.
- Partial child failures could be cached until we changed them to fail fast.
- Request ids had to be unique so cached results did not masquerade as fresh
  gathers.
- The 64 KB chunk cap had to be raised before 128 KB and 512 KB tests were real.
- Python/C++ binary record mismatches made us validate the 20-byte layout:
  `int32`, `float`, `float`, `uint32`, `uint16`, `uint8`, `uint8`.
- Node I used fallback sample data until the real shards were copied and the
  node was restarted.

This is the part the professor is likely to care about: the final number is
less interesting than how we proved the number was real.

## Visual Layout

Use a dark background with one large horizontal chart on the left. Put the 7.7x
number on the right, but make the key comparison 32 KB vs 512 KB:

`45.7 ms vs 44.0 ms mean, but 61 ms vs 110 ms P90.`

Under that, show why the result is trustworthy: ports, tree, cache ids, chunk
cap, binary layout, and shards were validated.

Keep topology out of the main slide; it belongs in the talk if needed. The
slide should feel like a research poster, not an architecture diagram.

## Do Not Put This on the Poster

Avoid listing every class or file. The poster should not be a code tour. Show
the knee, the tail-risk tradeoff, and why the benchmark is credible.
