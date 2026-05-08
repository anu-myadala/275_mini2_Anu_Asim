#!/usr/bin/env bash
# Generate Python gRPC bindings from cluster.proto.
# Run this script from the src/python_server/ directory.
set -e
python3 -m grpc_tools.protoc \
    -I ../../proto \
    --python_out=. \
    --grpc_python_out=. \
    ../../proto/cluster.proto
echo "Generated: cluster_pb2.py  cluster_pb2_grpc.py"
