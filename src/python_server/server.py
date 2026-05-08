#!/usr/bin/env python3
"""Python implementation of a Mini 2 team node."""

import os
import sys
import struct
import time
import yaml
import grpc
from concurrent import futures

import cluster_pb2
import cluster_pb2_grpc

RECORD_FMT  = "<iffIHBB"
RECORD_SIZE = struct.calcsize(RECORD_FMT)
assert RECORD_SIZE == 20, f"Record size mismatch: expected 20, got {RECORD_SIZE}"


def _build_children(cfg: dict) -> dict:
    if "children" in cfg:
        return {k: list(v or []) for k, v in cfg["children"].items()}

    adj: dict = {}
    for edge in cfg.get("overlay", []):
        a, b = edge
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)

    leader = next(
        k for k, v in cfg.get("roles", {}).items()
        if isinstance(v, dict) and v.get("role") == "leader"
    )

    parent: dict = {leader: None}
    queue = [leader]
    for cur in queue:
        for nb in adj.get(cur, []):
            if nb not in parent:
                parent[nb] = cur
                queue.append(nb)

    children: dict = {n: [] for n in parent}
    for child, par in parent.items():
        if par is not None:
            children[par].append(child)
    return children


def _node_endpoint(node_id: str, cfg: dict) -> str:
    for host_info in cfg.get("hosts", {}).values():
        if node_id in host_info.get("procs", []):
            addr = host_info["addr"]
            port = cfg["ports"][node_id]
            return f"{addr}:{port}"
    return f"127.0.0.1:{cfg['ports'][node_id]}"


class TeamServicer(cluster_pb2_grpc.TeamServiceServicer):
    def __init__(self, node_id: str, cfg: dict) -> None:
        self.node_id = node_id
        self.base = (ord(node_id) - ord("A")) * 10
        self.cfg  = cfg

        all_children = _build_children(cfg)

        self._child_stubs: list = []
        for cid in all_children.get(node_id, []):
            endpoint = _node_endpoint(cid, cfg)
            channel  = grpc.insecure_channel(endpoint)
            stub     = cluster_pb2_grpc.TeamServiceStub(channel)
            self._child_stubs.append((cid, stub))

        self._req_count = 0
        self._total_ns  = 0
        self._payload = self._load_shard_payload()
        if not self._payload:
            self._payload = self._build_fallback_payload()
            print(f"[{self.node_id}] WARNING: using fallback sample data; "
                  "run scripts/make_shards.py with the 311 CSV for final results",
                  flush=True)

    def _load_shard_payload(self) -> bytes:
        roots = []
        if os.environ.get("MINI2_SHARD_DIR"):
            roots.append(os.environ["MINI2_SHARD_DIR"])
        roots.extend(["shards", "../shards"])

        for root in roots:
            path = os.path.join(root, f"shard_{self.node_id}.bin")
            if not os.path.exists(path):
                continue
            with open(path, "rb") as f:
                data = f.read()
            extra = len(data) % RECORD_SIZE
            if extra:
                data = data[:-extra]
                print(f"[{self.node_id}] trimmed partial record bytes from {path}",
                      flush=True)
            print(f"[{self.node_id}] loaded {len(data) // RECORD_SIZE} records "
                  f"from {path}", flush=True)
            return data
        return b""

    def _build_fallback_payload(self) -> bytes:
        parts = []
        for i in range(self.base, self.base + 10):
            parts.append(struct.pack(
                RECORD_FMT,
                10000000 + i,
                40.7000 + float(i) * 0.001,
                -73.9000 - float(i) * 0.001,
                10000 + (i % 200),
                2020 + (i % 5),
                i % 4,
                i % 6,
            ))
        return b"".join(parts)

    def Fetch(self, request, context):
        t0 = time.monotonic_ns()

        segments = [
            cluster_pb2.Segment(payload=self._payload, last=False)
        ]

        for child_id, stub in self._child_stubs:
            if not context.is_active():
                context.abort(grpc.StatusCode.CANCELLED, "upstream cancelled")
                return cluster_pb2.ShardReply()

            sub_req = cluster_pb2.ShardRequest(query=request.query)
            try:
                reply = stub.Fetch(sub_req)
                segments.extend(reply.segments)
            except grpc.RpcError as exc:
                context.abort(grpc.StatusCode.INTERNAL,
                              f"child fetch failed: {child_id}: {exc.details()}")
                return cluster_pb2.ShardReply()

        if segments:
            last = segments[-1]
            segments[-1] = cluster_pb2.Segment(payload=last.payload, last=True)

        dt = time.monotonic_ns() - t0
        self._req_count += 1
        self._total_ns  += dt

        print(f"[{self.node_id}] Fetch base={self.base}"
              f" local_records={len(self._payload) // RECORD_SIZE}"
              f" segs={len(segments)} dt={dt // 1000}us", flush=True)

        return cluster_pb2.ShardReply(segments=segments)


def serve(node_id: str, config_path: str) -> None:
    with open(config_path) as f:
        cfg = yaml.safe_load(f)

    port     = cfg["ports"][node_id]
    server   = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = TeamServicer(node_id, cfg)
    cluster_pb2_grpc.add_TeamServiceServicer_to_server(servicer, server)
    server.add_insecure_port(f"[::]:{port}")
    server.start()
    print(f"[{node_id}] (Python) listening on :{port}", flush=True)

    try:
        server.wait_for_termination()
    except KeyboardInterrupt:
        server.stop(grace=1)

    avg_us = (servicer._total_ns // max(servicer._req_count, 1)) // 1000
    print(f"[{node_id}] shutdown. requests={servicer._req_count} avg={avg_us}us")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <node_id> <config_path>", file=sys.stderr)
        sys.exit(1)

    serve(sys.argv[1], sys.argv[2])
