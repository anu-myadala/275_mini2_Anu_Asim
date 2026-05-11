cmake_minimum_required(VERSION 3.15)
project(mini2 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

set(CMAKE_BUILD_TYPE Release CACHE STRING "Build type" FORCE)

find_package(gRPC     CONFIG REQUIRED)
find_package(yaml-cpp REQUIRED)

include_directories(${CMAKE_BINARY_DIR}/proto)

add_subdirectory(proto)

include_directories(${CMAKE_SOURCE_DIR}/src/common)
include_directories(${CMAKE_SOURCE_DIR}/src/team_node)

add_executable(leader
    src/leader/main.cpp
)
target_link_libraries(leader PRIVATE
    cluster_proto
    gRPC::grpc++
    yaml-cpp::yaml-cpp
)

add_executable(team_node
    src/team_node/main.cpp
    src/team_node/team_node.cpp
)
target_link_libraries(team_node PRIVATE
    cluster_proto
    gRPC::grpc++
    yaml-cpp::yaml-cpp
)

add_executable(client
    src/client/main.cpp
)
target_link_libraries(client PRIVATE
    cluster_proto
    gRPC::grpc++
    yaml-cpp::yaml-cpp
)
