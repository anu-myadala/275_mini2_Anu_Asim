// Team node main – starts any non-leader node (B through I) depending on
// command-line arguments.  The node identity is NEVER hardcoded here; it
// must be supplied at runtime so the same binary can serve any role.
//
// Usage:
//   ./team_node <node_id> <config_path>
//
// Example:
//   ./team_node B ../config/nodes.yaml
//   ./team_node E ../config/nodes.yaml
#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "team_node.hpp"
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0]
                  << " <node_id> <config_path>\n"
                  << "  node_id    – single letter, e.g. B, C, D … H\n"
                  << "  config_path – path to nodes.yaml\n";
        return 1;
    }

    const std::string node_id     = argv[1];
    const std::string config_path = argv[2];

    ClusterConfig config;
    if (!config.load(config_path)) {
        std::cerr << "Failed to load config: " << config_path << "\n";
        return 1;
    }

    NodeInfo ni;
    try {
        ni = config.getNode(node_id);
    } catch (const std::exception& ex) {
        std::cerr << ex.what() << "\n";
        return 1;
    }

    TeamServiceImpl service(config, node_id);

    const std::string listen_addr = "0.0.0.0:" + std::to_string(ni.port);

    grpc::ServerBuilder builder;
    builder.AddListeningPort(listen_addr, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);

    auto server = builder.BuildAndStart();
    if (!server) {
        std::cerr << "Failed to start server on " << listen_addr << "\n";
        return 1;
    }

    std::cout << "[" << node_id << "] listening on " << listen_addr << "\n";
    server->Wait();

    std::cout << "[" << node_id << "] shutdown."
              << " requests=" << service.total_requests()
              << " avg_us=";
    if (service.total_requests() > 0)
        std::cout << (service.total_ns_serving() / service.total_requests()) / 1000;
    else
        std::cout << 0;
    std::cout << "\n";

    return 0;
}
