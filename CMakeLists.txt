cmake_minimum_required(VERSION 3.15)
project(mini2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Optimise for performance measurements (same as mini1 baseline flags).
# Switch to RelWithDebInfo if you need gdb symbols.
set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)

find_package(gRPC     CONFIG REQUIRED)
find_package(yaml-cpp REQUIRED)

# Note: protobuf is found in proto/CMakeLists to avoid duplicate target
# definitions when gRPC's CMake config also depends on protobuf.
include_directories(${CMAKE_BINARY_DIR}/proto)

add_subdirectory(proto)

# ── Shared include path for common headers ───────────────────────────────────
include_directories(${CMAKE_SOURCE_DIR}/src/common)
include_directories(${CMAKE_SOURCE_DIR}/src/team_node)

# ── Leader (node A) ──────────────────────────────────────────────────────────
# The node identity is passed as a command-line argument at runtime,
# NOT hardcoded in the binary.
add_executable(leader
    src/leader/main.cpp
)
target_link_libraries(leader PRIVATE
    cluster_proto
    gRPC::grpc++
    yaml-cpp::yaml-cpp
)

# ── Team node (nodes B-H) ────────────────────────────────────────────────────
# A single binary serves any letter node depending on the first argument.
# Previously eight identical binaries were built; now one is sufficient.
add_executable(team_node
    src/team_node/main.cpp
    src/team_node/team_node.cpp
)
target_link_libraries(team_node PRIVATE
    cluster_proto
    gRPC::grpc++
    yaml-cpp::yaml-cpp
)

# ── Client ───────────────────────────────────────────────────────────────────
add_executable(client
    src/client/main.cpp
)
target_link_libraries(client PRIVATE
    cluster_proto
    gRPC::grpc++
    yaml-cpp::yaml-cpp
)

# ── Node I is the Python server (no C++ binary needed) ──────────────────────
# See src/python_server/server.py
