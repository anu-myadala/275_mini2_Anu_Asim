# Mini 2 Poster Notes

## Main Message

Chunk size is the control knob, but validation is what made the result
trustworthy.

## Use This Figure

Make a bar chart from `results/chunk_sweep_local.tsv`:

| Chunk bytes | Avg total us |
|---:|---:|
| 2000 | 423093 |
| 8000 | 100274 |
| 32000 | 31579 |
| 128000 | 19446 |
| 512000 | 9073 |

Title: `The Fastest Curve Was Not Trustworthy Until We Broke It`

## One-Sentence Result

For the same 80,000 typed 311 records, 512 KB chunks finished in about 9 ms,
while 2 KB chunks took about 423 ms because they required 800 client-leader
round trips.

## Important Caveat

Large chunks improve total completion time, but each RPC carries more data and
has higher per-call latency. The best chunk size depends on fairness and memory
pressure, not only raw speed.

## Depth Angle

The poster should mention the failures that would have made the graph wrong:

- An old process on the same port made the client talk to the wrong server.
- Ambiguous tree derivation meant A only queried B's subtree at first.
- Partial child failures could be cached until we changed them to fail fast.

This is the part the professor is likely to care about: the final number is less
interesting than how we proved the number was real.

## Visual Layout

Use a dark background with one large chart in the center. Put the 46.6x number
large on the right, and place a small "validation failures caught" box under it.
Put the topology as a thin line drawing in the lower left. Keep the text short
enough that people can read it from the back of the room.

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
