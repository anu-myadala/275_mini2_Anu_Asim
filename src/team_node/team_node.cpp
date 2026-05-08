#include "team_node.hpp"
#include <cstring>
#include <grpcpp/grpcpp.h>

TeamServiceImpl::TeamServiceImpl(ClusterConfig& cfg, const std::string& my_id)
    : config_(cfg), id_(my_id) {

    // Shard base: node A=0, B=10, C=20, ..., I=80.
    // In a real deployment each node loads its own partition of the dataset
    // from disk. The deterministic offset ensures records are unique per node.
    base_ = (static_cast<int>(id_[0]) - static_cast<int>('A')) * 10;

    // Build reusable stubs for all children at startup (not per-RPC).
    // Re-using channels avoids repeated TCP handshake + HTTP/2 SETTINGS
    // negotiation on every request – critical for latency under load.
    for (const std::string& child_id : config_.getChildren(id_)) {
        NodeInfo ni = config_.getNode(child_id);
        auto channel = grpc::CreateChannel(ni.endpoint(),
                                           grpc::InsecureChannelCredentials());
        child_stubs_.push_back({ child_id, TeamService::NewStub(channel) });
    }
}

std::string TeamServiceImpl::buildOwnPayload() const {
    // Serve 10 typed, packed records per shard. Each field uses its correct
    // primitive type (int32, double, int16, uint8) rather than strings, which
    // allows the binary payload to be cast directly to Record* on the client
    // without any string parsing or type conversion.
    std::string payload;
    payload.reserve(10 * sizeof(Record));

    for (int i = base_; i < base_ + 10; ++i) {
        Record r;
        r.id    = static_cast<int32_t>(i);
        r.value = static_cast<double>(i) * 1.1;
        r.year  = static_cast<int16_t>(2020 + (i % 5));
        r.flag  = static_cast<uint8_t>(i % 2);
        payload.append(reinterpret_cast<const char*>(&r), sizeof(r));
    }
    return payload;
}

grpc::Status TeamServiceImpl::Fetch(grpc::ServerContext* ctx,
                                    const ShardRequest*  req,
                                    ShardReply*          out) {
    NsCount t0 = now_ns();

    // Serve own shard.
    {
        auto* seg = out->add_segments();
        seg->set_payload(buildOwnPayload());
        seg->set_last(false);
    }

    // Parallel subtree fan-out. Mini 1 feedback identified contention and
    // serialization as a scaling issue, so child RPCs are overlapped here.
    // Each child fills its own temporary reply buffer to avoid lock contention
    // while the requests are in flight.
    std::vector<ShardReply> child_replies(child_stubs_.size());
    std::vector<std::thread> workers;
    workers.reserve(child_stubs_.size());

    for (size_t i = 0; i < child_stubs_.size(); ++i) {
        workers.emplace_back([&, i] {
            if (ctx->IsCancelled()) return;

            ShardRequest sub_req;
            sub_req.mutable_query()->CopyFrom(req->query());
            grpc::ClientContext sub_ctx;

            auto status = child_stubs_[i].stub->Fetch(
                &sub_ctx,
                sub_req,
                &child_replies[i]
            );

            if (!status.ok()) {
                std::cerr << "[" << id_ << "] child "
                          << child_stubs_[i].id
                          << " error: "
                          << status.error_message()
                          << "\n";
            }
        });
    }

    for (auto& t : workers) t.join();

    for (auto& rep : child_replies) {
        for (const auto& s : rep.segments()) {
            *out->add_segments() = s;
        }
    }

    // Mark the final segment so callers know the payload boundary.
    if (out->segments_size() > 0)
        out->mutable_segments(out->segments_size() - 1)->set_last(true);

    NsCount dt = elapsed_ns(t0);
    req_count_.fetch_add(1, std::memory_order_relaxed);
    total_ns_.fetch_add(dt, std::memory_order_relaxed);

    std::cout << "[" << id_ << "] Fetch"
              << " base=" << base_
              << " segs=" << out->segments_size()
              << " dt=" << dt / 1000 << "us\n";

    return grpc::Status::OK;
}
