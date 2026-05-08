// Mini2 client – pages through results from the leader using QueryOnce.
//
// Measures per-chunk and total latency (ns precision). Run multiple clients
// in parallel from separate shells to observe FairQueue scheduling under
// concurrent load.
//
// Usage:
//   ./client <config_path> <client_id> [chunk_size_bytes]
//
// Examples:
//   ./client ../config/nodes.yaml cli1 128      # small chunks, many round trips
//   ./client ../config/nodes.yaml cli1 1500     # larger chunks, fewer round trips
//   ./client ../config/nodes.yaml cli1 0        # server picks default (128 B)
#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "../common/config.hpp"
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace mini2;

// Must match the packed Record in team_node.hpp exactly.
#pragma pack(push, 1)
struct Record {
    int32_t  id;
    double   value;
    int16_t  year;
    uint8_t  flag;
};
#pragma pack(pop)
static_assert(sizeof(Record) == 15, "Record layout mismatch");

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0]
                  << " <config_path> <client_id> [chunk_bytes]\n";
        return 1;
    }

    const std::string config_path = argv[1];
    const std::string client_id   = argv[2];
    const int         chunk_size  = (argc > 3) ? std::stoi(argv[3]) : 128;

    ClusterConfig cfg;
    if (!cfg.load(config_path)) {
        std::cerr << "Failed to load config: " << config_path << "\n";
        return 1;
    }

    NodeInfo leader_ni = cfg.getNode(cfg.root());
    auto channel = grpc::CreateChannel(leader_ni.endpoint(),
                                       grpc::InsecureChannelCredentials());
    auto stub = LeaderService::NewStub(channel);

    std::cout << "Client '" << client_id << "' -> leader at "
              << leader_ni.endpoint()
              << "  chunk=" << chunk_size << "B\n";

    int       offset        = 0;
    bool      has_more      = true;
    int       total_records = 0;
    int       call_count    = 0;
    NsCount   total_rpc_ns  = 0;
    NsCount   min_rpc_ns    = LLONG_MAX;
    NsCount   max_rpc_ns    = 0;

    while (has_more) {
        Query q;
        q.set_client_id(client_id);
        q.set_request_id("req-" + client_id);
        q.set_chunk_size(chunk_size);
        q.set_offset(offset);

        AggregatedReply rep;
        grpc::ClientContext ctx;

        NsCount t0     = now_ns();
        auto    status = stub->QueryOnce(&ctx, q, &rep);
        NsCount dt     = elapsed_ns(t0);

        if (!status.ok()) {
            std::cerr << "RPC error: " << status.error_message() << "\n";
            return 1;
        }

        total_rpc_ns += dt;
        if (dt < min_rpc_ns) min_rpc_ns = dt;
        if (dt > max_rpc_ns) max_rpc_ns = dt;
        ++call_count;

        std::cout << "  chunk " << call_count
                  << " (off=" << offset << ")"
                  << " dt=" << dt / 1000 << "us\n";

        for (const auto& seg : rep.segments()) {
            const std::string& data = seg.payload();
            int rec_count = static_cast<int>(data.size() / sizeof(Record));
            for (int i = 0; i < rec_count; ++i) {
                Record r;
                std::memcpy(&r, data.data() + i * sizeof(Record), sizeof(r));
                std::cout << "    id=" << std::setw(4) << r.id
                          << " year=" << r.year
                          << " val="  << std::fixed << std::setprecision(2) << r.value
                          << " flag=" << static_cast<int>(r.flag) << "\n";
                ++total_records;
            }
        }

        has_more = rep.has_more();
        offset   = rep.next_offset();
    }

    long long avg_rpc_us = call_count ? total_rpc_ns / call_count / 1000 : 0;

    std::cout << "\n=== Summary for client '" << client_id << "' ===\n"
              << "  records    : " << total_records  << "\n"
              << "  chunks     : " << call_count     << "\n"
              << "  chunk_size : " << chunk_size     << " B\n"
              << "  total_rpc  : " << total_rpc_ns / 1000 << " us\n"
              << "  avg_rpc    : " << avg_rpc_us     << " us\n"
              << "  min_rpc    : " << min_rpc_ns / 1000 << " us\n"
              << "  max_rpc    : " << max_rpc_ns / 1000 << " us\n";

    return 0;
}
