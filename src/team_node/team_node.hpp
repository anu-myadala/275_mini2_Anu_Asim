#pragma once
#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "../common/config.hpp"
#include <atomic>
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

static_assert(sizeof(Record) == 20, "Record size must be 20 bytes");

static constexpr int MIN_CHUNK_BYTES = static_cast<int>(sizeof(Record));
static constexpr int MAX_CHUNK_BYTES = 1048576;

class TeamServiceImpl final : public TeamService::Service {
public:
    TeamServiceImpl(ClusterConfig& cfg, const std::string& my_id);

    grpc::Status Fetch(grpc::ServerContext* ctx,
                       const ShardRequest*  req,
                       ShardReply*          out) override;

    long long total_requests()   const { return req_count_.load(std::memory_order_relaxed); }
    long long total_ns_serving() const { return total_ns_.load(std::memory_order_relaxed); }

private:
    std::string loadShardPayload() const;
    std::string buildFallbackPayload() const;

    ClusterConfig& config_;
    std::string    id_;
    int            base_;
    std::string    payload_;

    struct ChildStub {
        std::string                         id;
        std::unique_ptr<TeamService::Stub>  stub;
    };
    std::vector<ChildStub> child_stubs_;

    std::atomic<long long> req_count_{0};
    std::atomic<long long> total_ns_{0};
};
