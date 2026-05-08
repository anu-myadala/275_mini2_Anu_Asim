# Mini 2 Explained From Start to Finish

## The Simple Version

Imagine the NYC 311 data is too big for one worker to handle comfortably. We
split it into boxes. Each server owns one box. A client asks one front desk
server, A, for data. A does not store the data itself; it asks the other servers
for their boxes, combines the answers, and gives the client the answer in
chunks.

The project is about finding a good chunk size. Tiny chunks are easy on memory,
but they require many trips. Huge chunks need fewer trips, but each trip carries
more data.

## What Runs

There are nine nodes:

```text
A = leader/front door
B-H = C++ data nodes
I = Python data node
```

The tree is:

```text
A -> B, H, G, I
B -> C, D, E
E -> F
```

The client only talks to A. A talks to its children. B and E talk to their own
children. This is a scatter-gather pattern.

## What The Data Looks Like

The original 311 CSV has many string columns. Sending strings everywhere would
make the experiment noisy and memory-heavy. We convert each useful row into a
small typed record:

```text
unique key, latitude, longitude, zip, created year, status, borough
```

Each record is 20 bytes. That is why `scripts/make_shards.py` exists: it reads
the CSV and writes `shard_B.bin`, `shard_C.bin`, etc.

## What Each Main File Does

`config/nodes.yaml`

Defines the overlay, directed tree, host addresses, and ports. This keeps node
identity and network layout out of the source code.

`scripts/make_shards.py`

Reads the 311 CSV and creates binary shard files. It distributes rows round
robin across A-I. In the current experiment A is leader-only, so the query
returns B-I.

`src/team_node/team_node.cpp`

Loads one shard file for a node. When asked for data, it returns its own shard
and asks its child nodes for their shards too.

`src/leader/leader_node.cpp`

Accepts client queries. It asks B, H, G, and I for their subtrees, caches the
combined result for that request, and returns one chunk at a time.

`src/client/main.cpp`

Calls A repeatedly until all chunks are received. It prints timing numbers:
total time, number of chunks, average RPC time, min, and max.

`benchmark.sh`

Runs the client many times for different chunk sizes.

`benchmark_fairness.sh`

Runs several clients at once to see whether one client starves the others.

## What The Results Mean

For the local debug run, we used 80,000 returned records.

Small chunks:

```text
2 KB chunks -> 800 chunks -> about 423 ms total
```

Large chunks:

```text
512 KB chunks -> 4 chunks -> about 9 ms total
```

The meaning is not "always use giant chunks." The meaning is: the number of
round trips dominates local performance. Larger chunks reduce round trips, but
they also increase memory per response and may hurt fairness under load.

## Why This Connects To Class

The messaging lectures discuss payload size and latency. Small payloads can
increase overhead because each message still pays the cost of a round trip.

The sharding lecture discusses splitting large data sets across machines. This
project does that with 311 records.

The failure/recovery lecture discusses fail-fast and reroute behavior. Our
current design is fail-fast: if a child node cannot be reached, the client gets
an error instead of a fake partial success.

The notes say to average 15-30 runs. Our local table is a debug run with 3
trials; the final two-computer result should use at least 15.

## What To Say If Asked About Weaknesses

The current system caches the full gathered result at A, which is simple and
easy to measure. If a node dies after A has already gathered the result, the
current request can still finish from cache. The downside is that A can become a
memory pressure point for very large result sets.

The fair queue gives clients equal turns, but it does not guarantee identical
finish times.

The system fails clearly when a child is down, but it does not reroute to a
replica because the assignment says there is no replication.

## Final Two-Computer Plan

1. Put the same repo and config on both machines.
2. Set host IPs in `config/nodes.yaml`.
3. Start G, H, and I on host2.
4. Start C, D, F, E, B, and A on host1.
5. Run:

```bash
bash benchmark.sh build config/nodes.yaml 15 | tee results/chunk_sweep_2host.tsv
bash benchmark_fairness.sh build config/nodes.yaml 4 32000 | tee results/fairness_2host.txt
```

6. Do two failure tests: H down before a new request, and H killed after the
   first page of a request is cached.
