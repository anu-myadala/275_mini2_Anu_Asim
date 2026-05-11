# Mini 2 – Installation and Run Guide

## Dependencies

### C++ side
- CMake ≥ 3.15
- gRPC (with CMake config)
- Protobuf
- yaml-cpp
- gcc/g++ ≥ 13 **or** Clang ≥ 16 (not Apple's Xcode Clang)

Install on Ubuntu/Debian:
```bash
sudo apt-get install -y cmake libgrpc++-dev protobuf-compiler-grpc \
     libprotobuf-dev libyaml-cpp-dev
```

On macOS with Homebrew:
```bash
brew install cmake grpc protobuf yaml-cpp
```

### Python side (node I)
```bash
python3 -m venv venv
venv/bin/python -m pip install -r src/python_server/requirements.txt
```

If the proto stubs need to be regenerated:
```bash
bash src/python_server/gen_proto.sh   # or run protoc manually
```

---

## Build

```bash
mkdir build && cd build
cmake ..
make -j$(nproc)
```

This produces three binaries:
- `leader`     – node A
- `team_node`  – nodes B through H (identity passed at runtime)
- `client`     – test client

---

## Configuration

Edit `config/nodes.yaml` before running on two machines:
- Set `hosts.host1.addr` to the IP of your first machine.
- Set `hosts.host2.addr` to the IP of your second machine.

For local single-machine testing leave both as `127.0.0.1`.

---

## Running (two machines)

**Machine 1 (nodes A–F):**
```bash
build/team_node  C  config/nodes.yaml
build/team_node  D  config/nodes.yaml
build/team_node  F  config/nodes.yaml
build/team_node  E  config/nodes.yaml
build/team_node  B  config/nodes.yaml
build/leader     A  config/nodes.yaml
```

**Machine 2 (nodes G–I):**
```bash
build/team_node  G  config/nodes.yaml
build/team_node  H  config/nodes.yaml
venv/bin/python src/python_server/server.py I config/nodes.yaml
```

**Client (any machine):**
```bash
build/client  config/nodes.yaml  cli1  32000  5
```

Or with a larger chunk size to test throughput vs. call count tradeoff:
```bash
build/client  config/nodes.yaml  cli1  512000  0
build/client  config/nodes.yaml  cli2  32000   0
```

---

## Overlay topology (tree)

```
Assignment overlay edges: AB BC BD BE EF ED EG AH AG AI
Directed tree used for scatter-gather:

              A (leader)
            / | \  \
           B  H  G  I(Python)
         / | \
        C  D  E
              |
              F
```

Node A is the only public-facing entry point. Clients connect only to A.

---

## Benchmarking chunk sizes

The chunk size controls how many bytes the leader returns per QueryOnce call.
Smaller chunks → more round trips, lower per-call memory; larger chunks → fewer
calls, higher peak memory.

Run the client with different chunk sizes and compare the printed timing:
```bash
for sz in 2000 8000 32000 128000 512000; do
  echo "=== chunk_size=$sz ==="
  build/client config/nodes.yaml cli1 $sz 0
done
```

For final results, use the benchmark script with 30 runs:

```bash
bash benchmark.sh build config/nodes.yaml 30 | tee results/chunk_sweep_2host_30runs.tsv
```

---

## Notes

- Node identity is **never** hardcoded in any binary; always pass it on the command line.
- Do not run from an IDE VM; run directly from a terminal.
- The Python server (node I) must be started from the `src/python_server/` directory
  **or** with the proto stubs importable (see `gen_proto.sh`).
