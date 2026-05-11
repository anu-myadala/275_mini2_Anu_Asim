# Mini 2 Poster Speaking Notes

## Slide Title

**THE 32 KB KNEE**

**Subtitle:** Repeated pages dominated until the gather/cache floor took over.

## 0:00-0:45 Opening: The Real Finding

Our poster is about one specific result from the final two-laptop Mini 2 run.
We used NYC 311 Service Requests from 2020 to Present, converted a 90,000-row
subset into typed binary shards, and returned the same 80,000 records through
the same nine-node gRPC tree. The only variable we changed was the chunk size.

At the extremes, the result looks simple: 2 KB chunks averaged 337.8 ms, while
512 KB chunks averaged 44.0 ms. That is a 7.7x improvement.

But the real finding is more interesting than "bigger chunks are faster." The
curve has a knee around 32 KB. At 32 KB, we still used 50 client-to-leader
pages. At 512 KB, we used only 4 pages. But the means were almost the same:
45.7 ms versus 44.0 ms. That is only a 1.7 ms difference.

So the question is: if page count matters so much, why did cutting 50 pages to
4 pages barely change the mean? That is what this slide explains.

How to read the slide: the left chart shows mean time as bars, median time as
white dots, and P90 as small tick marks. The page counts are written next to
each chunk size. The right side is the argument: 7.7x speedup at the extremes,
almost no mean difference between 32 KB and 512 KB, and higher tail risk after
the knee.

## 0:45-1:45 What The Timing Actually Measures

The client calls A with unary `QueryOnce` requests. The first page is special:
A gathers the full result from B-I, caches the 1.6 MB payload, and returns the
first chunk. Later pages come from A's cache.

So the total time is not just "network bandwidth." It has two broad parts:

First, repeated paging overhead. Every page has a unary RPC from the client to
A, fair-queue scheduling, cache lookup, copying/sub-stringing at A, protobuf
payload work, and response handling.

Second, a fixed floor. Every run has to gather the same 1.6 MB result from the
tree at least once. That includes remote nodes over Wi-Fi, serialization,
payload movement, and copying inside A.

When chunks are tiny, the repeated paging overhead dominates. When chunks are
large enough, the fixed gather/transfer floor dominates and the curve flattens.

## 1:45-2:45 Why 32 KB And 512 KB Are So Close

The data fits that story.

At 2 KB, the client made 800 pages. The mean was 337.8 ms.

At 8 KB, the client made 200 pages. The mean dropped to 91.3 ms.

At 32 KB, the client made 50 pages. The mean dropped to 45.7 ms.

After that, the returns nearly disappeared. At 128 KB, only 13 pages were
needed, but the mean was 47.5 ms. At 512 KB, only 4 pages were needed, but the
mean was 44.0 ms.

A rough fit across the means gives about 0.37 ms of cost per extra page and a
fixed floor around 33 ms. That is not a pure TCP-handshake number, and I would
not describe it that way. It includes local unary RPC overhead, cache copying,
protobuf work, and the first gather. But it is enough to explain the shape: by
32 KB, most of the page-count penalty is already gone.

## 2:45-3:45 Mean vs Median: Why The Large Chunks Look Flat

The means are only half the story. The medians show that larger chunks were
usually faster.

At 32 KB, the median was 39.9 ms. At 128 KB, the median was 28.3 ms. At 512 KB,
the median was 25.8 ms.

So in a typical run, 512 KB was faster than 32 KB. But the tail got much worse.
The 90th percentile at 32 KB was 61.0 ms. At 512 KB it was 110.1 ms. The
sample coefficient of variation went from 0.26 at 32 KB to 0.80 at 512 KB.

That means large chunks were fast when the network behaved, but one slow remote
gather or large response spike could dominate the whole run. With only 4 pages,
one bad page is a huge fraction of the request. With 50 pages, a spike is
spread across more calls and the run is more stable.

That is why the slide says 32 KB is the knee: it is near the fastest mean, but
with much lower tail risk than 128 KB or 512 KB.

## 3:45-4:45 The Six Things We Had To Validate First

None of this timing mattered until we fixed the measurement path.

First, stale processes were still bound to some ports, so early clients could
talk to the wrong cluster.

Second, the tree was partially derived wrong. A initially contacted only B's
subtree, which skipped H, G, and I. That made the benchmark look faster because
it was doing less work.

Third, the leader had a 64 KB chunk cap, so our early 128 KB and 512 KB tests
were not actually measuring those sizes.

Fourth, request ids were reused, which meant cached results could be returned
as if they were fresh gathers.

Fifth, Python and C++ had to agree on the exact 20-byte binary layout:
`int32 key`, `float lat`, `float lon`, `uint32 zip`, `uint16 year`, `uint8
status`, and `uint8 borough`.

Sixth, node I once used fallback sample data because the real `shards/`
directory was missing on host2.

The system could look alive during all of these mistakes. That is why
validation is part of the finding, not just cleanup.

## 4:45-5:35 Fairness

The fairness test used four concurrent clients at 32 KB, the knee point.

Every client received exactly 50 chunks. The fastest client finished in
116.8 ms and the slowest finished in 121.8 ms, a 4.3% spread.

That is opportunity fairness. A rotates chunk turns so one client cannot drain
the whole cached result before the others get access. It does not guarantee
identical wall-clock completion, because each client's RPCs still experience
their own timing and network variation.

This is why 32 KB is a practical operating point. It is already past most of
the paging penalty, and it keeps chunk turns small enough to support concurrent
clients.

## 5:35-6:25 Failure Behavior

We also tested node H going down on host2.

If H is down before a new request starts, A fails clearly with a child-fetch
error. That is correct because there is no replication. Returning partial data
would be worse than returning an error.

If H dies after A has already gathered and cached the first page, that same
request can still finish from cache. That protects an active request from late
node loss, but it also makes A a memory pressure point because A is holding the
full result while the client pages through it.

That failure test supports the same conclusion: chunking is not only about
speed. It changes memory pressure and failure behavior too.

## 6:25-7:15 Closing

The safest way to say our discovery is this:

Chunk size shifts the bottleneck. Below 32 KB, repeated pages dominate. Above
32 KB, the fixed gather/cache floor and tail variance dominate.

If we optimize only for mean or median, 512 KB wins by a small amount. If we
care about robustness, fairness, and tail behavior, 32 KB is the better
operating point for this setup.

So the final lesson is not "round trips are the bottleneck forever." It is that
repeated pages dominate until they do not. The useful discovery is the knee in
the curve, and the reason we trust it is that we validated the ports, full tree,
chunk cap, cache ids, binary layout, and real shards before presenting the
numbers.

## Backup Q&A

**What is the one-sentence discovery?**
The useful discovery is the 32 KB knee: below it, page count dominates; above
it, the fixed gather/cache floor and tail variance dominate.

**Why are 50 pages at 32 KB and 4 pages at 512 KB almost the same mean?**
Because by 32 KB, most repeated paging overhead is already removed. The
remaining time is dominated by the first gather/cache of the full result,
payload movement, copying/serialization, and Wi-Fi tail spikes.

**Is the 0.37 ms/page estimate a new TCP connection cost?**
No. The client creates one gRPC channel to A, so it is not a new connection per
page. The estimate lumps together local unary RPC overhead, fair queue, cache
copying, protobuf work, and response handling.

**Which chunk size is best?**
It depends on the objective. 512 KB had the best mean and median. 32 KB was the
robust knee: 45.7 ms mean versus 44.0 ms at 512 KB, but P90 was 61.0 ms instead
of 110.1 ms.

**Why not just recommend 512 KB since it is fastest?**
Because the assignment asks about resources and fairness, not only fastest mean.
512 KB is faster in a typical run, but it has worse tail behavior and larger
per-response memory pressure. 32 KB gives almost the same mean with much lower
P90.

**Why use P90 and coefficient of variation?**
The mean alone hides Wi-Fi spikes. P90 shows what a slower-but-real run looks
like, and CV shows how unstable each chunk size was across 30 runs.

**What does "fixed gather/cache floor" mean?**
The first page makes A gather the full result from B-I and cache it. That
one-time cost is still paid even if the client asks for a huge chunk. After
that, more pages are mostly cache paging work at A.

**Did the client talk to every node?**
No. The client only talks to A. A gathers from B, H, G, and I; B gathers from
C, D, and E; E gathers from F.

**What is the exact record layout?**
`<iffIHBB`: `int32 key`, `float latitude`, `float longitude`, `uint32 incident
zip`, `uint16 created year`, `uint8 status`, and `uint8 borough`, for exactly
20 bytes.

**How did you know all nodes used real data?**
Each node printed how many records it loaded from its shard file. We also caught
and fixed the case where Python node I warned that it was using fallback sample
data.

**Why NYC 311?**
It is a real public dataset with enough rows to make memory layout and payload
size matter. We used 90,000 rows total; because A is leader-only, B-I returned
80,000 records.

**Why not use streaming?**
The assignment prohibited async/streaming gRPC. More importantly, explicit
offsets let us control and measure chunk size directly instead of letting gRPC
hide the flow-control behavior.

**What class labs influenced this?**
`basic-grpc` gave us the unary service pattern, `leader-adv` gave the
coordinator/worker idea, socket labs motivated message-size testing, and MPI
round/baton labs influenced how we framed fairness.

**What code came from outside class topics?**
The runtime design is class-based. Outside documentation mainly supported
implementation details: Python `struct` for the C++/Python binary layout, CMake
`add_custom_command` and gRPC C++ docs for generated sources, yaml-cpp/PyYAML
for config parsing, and python-pptx/Matplotlib for generating the report poster.

**What happened when H was down?**
If H was down before gather, A failed the request clearly. If H died after A had
already cached the result, the current request could still finish from cache.
That shows the memory/failure tradeoff at A.

**Did Python node I make the system slower than C++ nodes?**
We did not isolate language runtime as a separate benchmark. The Python-specific
issues we actually observed were deployment issues: dependencies, expat library
path, and making sure the shard files were present.

**What would you improve with more time?**
Run the same sweep on a wired network, test a larger shard set, and record
server-side timing at A separately for gather time versus cache-page time. That
would make the cost model cleaner.
