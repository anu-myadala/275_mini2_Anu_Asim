#include "team_node.hpp"
#include <cstring>
#include <cstdlib>
#include <fstream>
#include <thread>
#include <grpcpp/grpcpp.h>

TeamServiceImpl::TeamServiceImpl(ClusterConfig& cfg, const std::string& my_id)
    : config_(cfg), id_(my_id) {

    base_ = (static_cast<int>(id_[0]) - static_cast<int>('A')) * 10;
    payload_ = loadShardPayload();
    if (payload_.empty()) {
        payload_ = buildFallbackPayload();
        std::cerr << "[" << id_ << "] WARNING: using fallback sample data; "
                  << "run scripts/make_shards.py with the 311 CSV for final results\n";
    }

    for (const std::string& child_id : config_.getChildren(id_)) {
        NodeInfo ni = config_.getNode(child_id);
        auto channel = grpc::CreateChannel(ni.endpoint(),
                                           grpc::InsecureChannelCredentials());
        child_stubs_.push_back({ child_id, TeamService::NewStub(channel) });
        std::cerr << "[" << id_ << "] child " << child_id
                  << " -> " << ni.endpoint() << "\n";
    }
}

std::string TeamServiceImpl::loadShardPayload() const {
    std::vector<std::string> roots;
    if (const char* env = std::getenv("MINI2_SHARD_DIR"))
        roots.emplace_back(env);
    roots.emplace_back("shards");
    roots.emplace_back("../shards");

    for (const auto& root : roots) {
        const std::string path = root + "/shard_" + id_ + ".bin";
        std::ifstream in(path, std::ios::binary);
        if (!in) continue;

        std::string data((std::istreambuf_iterator<char>(in)),
                         std::istreambuf_iterator<char>());
        const auto extra = data.size() % sizeof(Record);
        if (extra != 0) {
            data.resize(data.size() - extra);
            std::cerr << "[" << id_ << "] trimmed partial record bytes from "
                      << path << "\n";
        }
        std::cout << "[" << id_ << "] loaded "
                  << data.size() / sizeof(Record)
                  << " records from " << path << "\n";
        return data;
    }

    return {};
}

std::string TeamServiceImpl::buildFallbackPayload() const {
    std::string payload;
    payload.reserve(10 * sizeof(Record));

    for (int i = base_; i < base_ + 10; ++i) {
        Record r;
        r.unique_key   = static_cast<int32_t>(10000000 + i);
        r.latitude     = 40.7000f + static_cast<float>(i) * 0.001f;
        r.longitude    = -73.9000f - static_cast<float>(i) * 0.001f;
        r.incident_zip = static_cast<uint32_t>(10000 + (i % 200));
        r.created_year = static_cast<uint16_t>(2020 + (i % 5));
        r.status       = static_cast<uint8_t>(i % 4);
        r.borough      = static_cast<uint8_t>(i % 6);
        payload.append(reinterpret_cast<const char*>(&r), sizeof(r));
    }
    return payload;
}

grpc::Status TeamServiceImpl::Fetch(grpc::ServerContext* ctx,
                                    const ShardRequest*  req,
                                    ShardReply*          out) {
    NsCount t0 = now_ns();

    {
        auto* seg = out->add_segments();
        seg->set_payload(payload_);
        seg->set_last(false);
    }

    std::vector<ShardReply> child_replies(child_stubs_.size());
    std::vector<std::string> child_errors(child_stubs_.size());
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
                child_errors[i] = child_stubs_[i].id + ": " + status.error_message();
            }
        });
    }

    for (auto& t : workers) t.join();

    for (const auto& err : child_errors) {
        if (!err.empty())
            return grpc::Status(grpc::StatusCode::INTERNAL,
                                "child fetch failed: " + err);
    }

    for (auto& rep : child_replies) {
        for (const auto& s : rep.segments()) {
            *out->add_segments() = s;
        }
    }

    if (out->segments_size() > 0)
        out->mutable_segments(out->segments_size() - 1)->set_last(true);

    NsCount dt = elapsed_ns(t0);
    req_count_.fetch_add(1, std::memory_order_relaxed);
    total_ns_.fetch_add(dt, std::memory_order_relaxed);

    std::cout << "[" << id_ << "] Fetch"
              << " base=" << base_
              << " local_records=" << payload_.size() / sizeof(Record)
              << " segs=" << out->segments_size()
              << " dt=" << dt / 1000 << "us\n";

    return grpc::Status::OK;
}
