# 10-Minute Poster Speaking Notes

## 0:00-0:45 Opening

Our Mini 2 project is a distributed query system over NYC 311 data. The main
question we focused on was: when a distributed result set is too large to return
all at once, how much does chunk size affect performance?

The one-slide poster is built around that question, but it also shows the deeper
lesson: our first measurements were not automatically trustworthy. Chunk size
mattered a lot, but we only trusted the curve after we found and fixed several
ways the system could return misleading results.

## 0:45-1:45 System Setup

The system has nine processes, A through I. A is the leader and the only public
entry point. The client never calls the data nodes directly.

The tree is A to B, H, G, and I. B then talks to C, D, and E. E talks to F. Node
I is written in Python and the rest are C++.

This gives us a scatter-gather design. A scatters the query down the tree, the
data nodes return their shard data, and A gathers the responses before returning
chunks to the client.

## 1:45-2:45 Data Representation

We used the NYC 311 Open Data CSV. The original CSV is very large and mostly
string-based, so before running the cluster we convert it into binary shard
files.

Each record is 20 bytes: unique key, latitude, longitude, incident zip, created
year, status, and borough. This connects directly to the Mini 1 feedback. In
Mini 1, we were told to be more careful with data types and memory density.

So instead of shipping strings through gRPC, we use typed binary records. That
makes the payload size predictable and makes the chunk-size experiment cleaner.

## 2:45-4:00 What Chunking Means

The client does not receive the whole result in one response unless it asks for
a very large chunk. It calls `QueryOnce` repeatedly with an offset.

For example, if the chunk size is 2 KB, the client gets a small piece of the
result, then asks for the next offset, and keeps going. For our local 80,000
record run, that meant 800 chunks.

If the chunk size is 512 KB, the same result comes back in only 4 chunks.

So the tradeoff is: small chunks reduce per-response memory pressure, but they
create many more round trips. Large chunks reduce round trips, but each response
is heavier.

## 4:00-5:15 Results

The chart on the poster shows total request time by chunk size.

At 2 KB, the average total time was about 423,000 microseconds, or 423
milliseconds. At 8 KB, it dropped to about 100 milliseconds. At 32 KB, it was
about 32 milliseconds. At 512 KB, it was about 9 milliseconds.

That is about a 46.6 times improvement from 2 KB to 512 KB in the local loopback
run.

The important part is not that 512 KB is always the best value. The important
part is that the cost of repeated request-response cycles dominated the local
run.

## 5:15-6:15 Fairness Result

We also tested fairness with four clients at the same time using 32 KB chunks.

All four clients received 50 chunks, so the queue did prevent one client from
running all the way to the end before the others got turns.

But the finish times were not identical. One client was about 41 percent slower
than the fastest client. So our conclusion is careful: the current queue gives
opportunity fairness, not strict latency fairness.

That is a good limitation to report because it shows the measurement was not
just a success story.

## 6:15-7:30 Failures We Found

We found several issues while testing.

First, an older Mini 2 server from another folder was already listening on some
of the same ports. The client connected to the wrong service and gave empty RPC
errors. We found it with `lsof` and stopped the old process.

Second, the original tree derivation only made A contact B, so we were missing
H, G, and I. That caused partial results. We fixed it by making the directed
tree explicit in `nodes.yaml`.

Third, partial failed results could be cached under the same request id. We
changed the client to use unique request ids and changed the leader to fail the
request if a child fetch fails.

Fourth, the Python server failed under the system Python because `yaml` was not
installed. The launcher now uses the project virtual environment if it exists.

The newest failure test is also useful. If node H is down before a new request,
the client gets a clear child-fetch error. But if H dies after A has already
gathered and cached the first page, that same request can still complete. That
means the cache helps an active request survive late node loss, but it also
turns A into a memory pressure point.

## 7:30-8:30 Class Concepts

This project connects to several lecture topics.

From the socket and messaging lectures, payload size affects latency and
throughput. Small messages have overhead. Large messages can cause buffer or
network pressure.

From the sharding lecture, splitting data across nodes improves scalability and
parallel request handling, but it creates coordination costs.

From failure and balance, we chose a fail-fast behavior. Since the assignment
does not use replication, if a child node is down, returning a clear error is
better than returning a partial answer that looks successful.

## 8:30-9:30 Two-Computer Run Plan

The local result is not the final result. The final run needs two physical
computers.

For that run, we will put A-F on host1 and G-I on host2. Then we will run the
same chunk sweep with at least 15 runs per chunk size, following the course
notes.

I expect the absolute latency to be higher because now traffic crosses the
network. But the trend should still show that chunk size controls the number of
round trips.

We will also do two failure runs: one with H down before a new request, and one
where H dies after the first page is already cached. The difference between
those two runs is part of the learning, not something to hide.

## 9:30-10:00 Closing

The main takeaway is that distributed performance was not just about using gRPC
or adding more processes. The biggest lever we measured was how the result was
broken into chunks, and the biggest lesson was that distributed measurements can
look convincing while still being wrong.

Mini 1 taught us to care about data representation. Mini 2 showed us that once
the data crosses process and machine boundaries, message shape and request
count become just as important.
