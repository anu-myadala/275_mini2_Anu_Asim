# 10-Minute Poster Speaking Notes

## 0:00-0:45 The Finding

Our poster is not a summary of Mini 2. The finding we want people to remember
is this: the fastest performance curve was not trustworthy until we broke the
system in several ways and proved the measurement path.

The final number is clear. On two laptops, returning the same 80,000 typed NYC
311 records took about 338 ms with 2 KB chunks and about 44 ms with 512 KB
chunks. That is about 7.7x faster. But the more interesting part is how many
things had to be fixed before that result meant anything.

## 0:45-1:45 Why Chunk Size Became Our Main Question

The assignment asked how to conserve memory, manage request-response pressure,
and allow fairness between endpoints. Chunk size touches all three.

Small chunks are gentle on each response, but they force the client to keep
coming back. In our final run, 2 KB meant 800 client-leader round trips.

Large chunks reduce that request pressure. At 512 KB, the same response only
needed 4 chunks. The tradeoff is that each response is heavier, so A holds and
sends larger buffers.

So our real question became: where does the cost move when the same data is
returned in different shapes?

## 1:45-2:45 What The Results Actually Show

The chart shows total request time by chunk size. The trend is strongest at the
extremes: 2 KB was much slower than 512 KB.

At 8 KB, total time dropped to about 91 ms. At 32 KB, it was about 46 ms. Then
128 KB and 512 KB were close to that range.

That middle flattening is important. It keeps us from overclaiming. The result
is not "bigger is always better." The result is that once the request count is
low enough, Wi-Fi variation and per-response cost start to matter.

## 2:45-3:45 The First Way The Graph Lied

The first failure was simple but useful: old processes were already bound to
some of the same ports. The client was not always talking to the cluster we
thought we had started.

That made us add a runbook habit: check listening ports before trusting a run.
It sounds basic, but in a distributed project the wrong process can make a
benchmark look like a code problem.

That is why our report includes failures. They are not side notes; they are
part of how we validated the final numbers.

## 3:45-4:45 The Second Way The Graph Lied

The next failure was topology. The assignment explicitly says not to flatten the
tree, and the tree creates real coordination issues. Our first derived tree made
A contact only B's side of the graph, so H, G, and I were missing.

That would have made the system look faster for the wrong reason: it was doing
less work.

The fix was to make the directed children explicit in `nodes.yaml`. That kept
the overlay configurable without hardcoding node roles in the code.

## 4:45-5:45 The Cross-Language Failure

Node I is Python and the rest are C++. That was not just a checkbox. It forced
us to treat the binary record layout as a real contract.

Each 311 record is 20 bytes: id, latitude, longitude, zip, year, status, and
borough. If Python and C++ disagree about that layout, the cluster can still run
but return nonsense.

The socket interoperability lab helped here. The lesson was that
cross-language communication is not only about the transport. The message shape
has to be verified too.

## 5:45-6:45 Fairness, Not Just Speed

We also ran four clients at 32 KB chunks. Each client received 50 chunks, so
the queue did prevent one client from draining the whole cached response first.

But the finish times were not identical. The slowest client was about 4.3%
slower than the fastest.

That is why we call it opportunity fairness. The scheduler gives clients turns,
but it does not guarantee identical wall-clock latency. That distinction matters
because the assignment asked about balance, not just throughput.

## 6:45-7:45 Failure Timing And Cache Tradeoff

The H-down test gave us the best distributed-systems lesson.

If H is down before a new request starts, A fails clearly with a child-fetch
error. That is the behavior we want because there is no replication. Returning
partial data would be worse than returning an error.

But if H dies after A has already gathered and cached the first page, that same
request can still finish from cache. So caching helps an active request survive
late node loss, but it also turns A into a memory pressure point.

That is exactly the kind of tradeoff Mini 2 was trying to make us see.

## 7:45-8:45 How The Labs Shaped The Solution

The `basic-grpc` lab gave us the mechanics: protobuf, generated stubs, and
simple unary calls.

The `leader-adv` lab influenced the split between the coordinator and the
workers. A coordinates; the data nodes do shard work and child fetches.

The socket lab and lectures influenced the chunk experiment because they showed
that message size and message count change behavior. The MPI round and baton
labs influenced how we thought about fairness: do clients get turns, or does
one actor dominate the shared path?

We did not make the code complicated just to look advanced. We used the labs as
design pressure, then kept the implementation readable.

## 8:45-9:30 Why This Is Unique

The unique part of our project is not that we used gRPC or had A-I processes.
That was the baseline.

The unique part is that the performance result and the failure result are tied
together. The 7.7x improvement is only meaningful because we proved the system
was using the full tree, real shards, the correct binary layout, unique request
ids, and a chunk cap that actually allowed large chunks.

In other words, the final graph is a validation story, not just a speed story.

## 9:30-10:00 Closing

Mini 1 taught us to care about memory layout inside one program. Mini 2 taught
us that once data crosses process and machine boundaries, message shape and
request count can dominate.

Our takeaway is simple: for distributed result sets, chunk size is a control
knob, but validation is what makes the knob worth measuring.
