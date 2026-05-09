find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)

# Locate protoc and the gRPC plugin. Some Homebrew gRPC installs export the
# plugin target but leave IMPORTED_LOCATION unset, so verify the path before
# using it.
unset(_GRPC_CPP_PLUGIN_EXECUTABLE CACHE)
set(_GRPC_CPP_PLUGIN "")
if(TARGET gRPC::grpc_cpp_plugin)
    get_target_property(_GRPC_CPP_PLUGIN_FROM_TARGET
        gRPC::grpc_cpp_plugin IMPORTED_LOCATION)
    if(NOT _GRPC_CPP_PLUGIN_FROM_TARGET)
        get_target_property(_GRPC_CPP_PLUGIN_FROM_TARGET
            gRPC::grpc_cpp_plugin IMPORTED_LOCATION_RELEASE)
    endif()
    if(_GRPC_CPP_PLUGIN_FROM_TARGET AND EXISTS "${_GRPC_CPP_PLUGIN_FROM_TARGET}")
        set(_GRPC_CPP_PLUGIN "${_GRPC_CPP_PLUGIN_FROM_TARGET}")
    endif()
endif()

if(NOT _GRPC_CPP_PLUGIN)
    find_program(_GRPC_CPP_PLUGIN_EXECUTABLE
        NAMES grpc_cpp_plugin
        HINTS /opt/homebrew/bin /usr/local/bin
        REQUIRED)
    set(_GRPC_CPP_PLUGIN "${_GRPC_CPP_PLUGIN_EXECUTABLE}")
endif()

message(STATUS "Using grpc_cpp_plugin: ${_GRPC_CPP_PLUGIN}")

set(_PROTOBUF_PROTOC ${Protobuf_PROTOC_EXECUTABLE})

get_filename_component(hw_proto "${CMAKE_CURRENT_SOURCE_DIR}/cluster.proto" ABSOLUTE)
get_filename_component(hw_proto_path "${hw_proto}" PATH)

set(hw_proto_srcs "${CMAKE_CURRENT_BINARY_DIR}/cluster.pb.cc")
set(hw_proto_hdrs "${CMAKE_CURRENT_BINARY_DIR}/cluster.pb.h")
set(hw_grpc_srcs  "${CMAKE_CURRENT_BINARY_DIR}/cluster.grpc.pb.cc")
set(hw_grpc_hdrs  "${CMAKE_CURRENT_BINARY_DIR}/cluster.grpc.pb.h")

add_custom_command(
    OUTPUT  "${hw_proto_srcs}" "${hw_proto_hdrs}"
            "${hw_grpc_srcs}"  "${hw_grpc_hdrs}"
    COMMAND "${_PROTOBUF_PROTOC}"
    ARGS    --grpc_out "${CMAKE_CURRENT_BINARY_DIR}"
            --cpp_out  "${CMAKE_CURRENT_BINARY_DIR}"
            --plugin=protoc-gen-grpc="${_GRPC_CPP_PLUGIN}"
            -I "${hw_proto_path}"
            "${hw_proto}"
    DEPENDS "${hw_proto}"
)

add_library(cluster_proto
    ${hw_proto_srcs} ${hw_proto_hdrs}
    ${hw_grpc_srcs}  ${hw_grpc_hdrs}
)

target_include_directories(cluster_proto PUBLIC "${CMAKE_CURRENT_BINARY_DIR}")

target_link_libraries(cluster_proto
    PUBLIC
    protobuf::libprotobuf
    gRPC::grpc++
)
