#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "../common/config.hpp"
#include <algorithm>
#include <chrono>
#include <climits>
#include <cstring>
#include <iomanip>
#include <iostream>
#include <string>
#include <vector>

using namespace mini2;

#pragma pack(push, 1)
struct Record {
    int32_t  unique_key;
    float    latitude;
    float    longitude;
    uint32_t incident_zip;
    uint16_t created_year;
    uint8_t  status;
    uint8_t  borough;
};
#pragma pack(pop)
static_assert(sizeof(Record) == 20, "Record layout mismatch");

int main(int argc, char* argv[]) {
    if (argc < 3) {
        std::cerr << "Usage: " << argv[0]
                  << " <config_path> <client_id> [chunk_bytes]\n";
        return 1;
    }

    const std::string config_path = argv[1];
    const std::string client_id   = argv[2];
    const int         chunk_size  = (argc > 3) ? std::stoi(argv[3]) : 128;
    const int         max_print   = (argc > 4) ? std::stoi(argv[4]) : 20;
    const auto        run_id      = std::to_string(
        std::chrono::steady_clock::now().time_since_epoch().count());

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
        q.set_request_id("req-" + client_id + "-" + run_id);
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
                if (total_records < max_print) {
                    std::cout << "    key=" << r.unique_key
                              << " zip=" << r.incident_zip
                              << " year=" << r.created_year
                              << " lat=" << std::fixed << std::setprecision(4) << r.latitude
                              << " lon=" << r.longitude
                              << " status=" << static_cast<int>(r.status)
                              << " borough=" << static_cast<int>(r.borough)
                              << "\n";
                }
                ++total_records;
            }
        }

        has_more = rep.has_more();
        offset   = rep.next_offset();
    }

    long long avg_rpc_us = call_count ? total_rpc_ns / call_count / 1000 : 0;

    std::cout << "\n=== Summary for client '" << client_id << "' ===\n"
              << "  records    : " << total_records  << "\n"
              << "  printed    : " << std::min(total_records, max_print) << "\n"
              << "  chunks     : " << call_count     << "\n"
              << "  chunk_size : " << chunk_size     << " B\n"
              << "  total_rpc  : " << total_rpc_ns / 1000 << " us\n"
              << "  avg_rpc    : " << avg_rpc_us     << " us\n"
              << "  min_rpc    : " << min_rpc_ns / 1000 << " us\n"
              << "  max_rpc    : " << max_rpc_ns / 1000 << " us\n";

    return 0;
}
