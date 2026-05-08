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
cd src/python_server
pip install grpcio grpcio-tools pyyaml
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
./leader     A  ../config/nodes.yaml
./team_node  B  ../config/nodes.yaml
./team_node  C  ../config/nodes.yaml
./team_node  D  ../config/nodes.yaml
./team_node  E  ../config/nodes.yaml
./team_node  F  ../config/nodes.yaml
```

**Machine 2 (nodes G–I):**
```bash
./team_node  G  ../config/nodes.yaml
./team_node  H  ../config/nodes.yaml
python3 src/python_server/server.py I config/nodes.yaml
```

**Client (any machine):**
```bash
./client  ../config/nodes.yaml  cli1  128
```

Or with a larger chunk size to test throughput vs. call count tradeoff:
```bash
./client  ../config/nodes.yaml  cli1  512
./client  ../config/nodes.yaml  cli2  128   # concurrent client
```

---

## Overlay topology (tree)

```
Edges: AB BC BD BE EF ED EG AH AG AI

              A (leader)
            / | \  \
           B  H  G  I(Python)
         / | \
        C  D  E
              |\ 
              F  D  G
```

Node A is the only public-facing entry point. Clients connect only to A.

---

## Benchmarking chunk sizes

The chunk size controls how many bytes the leader returns per QueryOnce call.
Smaller chunks → more round trips, lower per-call memory; larger chunks → fewer
calls, higher peak memory.

Run the client with different chunk sizes and compare the printed timing:
```bash
for sz in 13 52 128 256 520; do
  echo "=== chunk_size=$sz ==="
  ./client ../config/nodes.yaml cli1 $sz
done
```

---

## Notes

- Node identity is **never** hardcoded in any binary; always pass it on the command line.
- Do not run from an IDE VM; run directly from a terminal.
- The Python server (node I) must be started from the `src/python_server/` directory
  **or** with the proto stubs importable (see `gen_proto.sh`).
