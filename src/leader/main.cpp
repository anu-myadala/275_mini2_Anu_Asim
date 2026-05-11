#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "leader_node.cpp"
#include <iostream>
#include <string>

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0]
                  << " <node_id> <config_path>\n"
                  << "  node_id     - typically 'A'\n"
                  << "  config_path - path to nodes.yaml\n";
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

    LeaderServiceImpl service(config, node_id);

    const std::string listen_addr = "0.0.0.0:" + std::to_string(ni.port);

    grpc::ServerBuilder builder;
    builder.AddListeningPort(listen_addr, grpc::InsecureServerCredentials());
    builder.RegisterService(&service);

    auto server = builder.BuildAndStart();
    if (!server) {
        std::cerr << "Failed to start server on " << listen_addr << "\n";
        return 1;
    }

    std::cout << "[Leader " << node_id << "] listening on " << listen_addr << "\n";
    server->Wait();

    service.printStats();
    return 0;
}
