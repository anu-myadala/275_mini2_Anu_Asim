#pragma once
#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "../common/config.hpp"
#include <atomic>
#include <iostream>
#include <mutex>
#include <string>
#include <vector>

using namespace mini2;

// ── Packed record layout ─────────────────────────────────────────────────────
// int32_t  id      (4 bytes) – record identifier
// double   value   (8 bytes) – primary measurement
// int16_t  year    (2 bytes) – year, chosen over uint8 to hold 4-digit years
// uint8_t  flag    (1 byte)  – boolean attribute
// Total: 15 bytes with pragma pack(1)
//
// Without pack(1), a naive struct would be padded to 24 bytes due to the
// double's 8-byte alignment requirement. Pack(1) raises page density from
// ~341 records/8 KB page to ~546 – a 60% improvement, directly reducing
// cache-line misses during scatter-gather payload assembly.
#pragma pack(push, 1)
struct Record {
    int32_t  id;
    double   value;
    int16_t  year;
    uint8_t  flag;
};
#pragma pack(pop)

static_assert(sizeof(Record) == 15, "Record size must be 15 bytes");

static constexpr int MIN_CHUNK_BYTES = static_cast<int>(sizeof(Record));
static constexpr int MAX_CHUNK_BYTES = 65536;

// ── TeamServiceImpl ───────────────────────────────────────────────────────────
// Each team node owns a shard identified by its node id. On Fetch():
//   1. Serialises its own shard into typed, packed binary records.
//   2. Recursively contacts children in the overlay tree and appends replies.
//   3. Propagates upstream client cancellation immediately.
//
// Channels and stubs are created once at startup to avoid per-RPC TCP +
// HTTP/2 negotiation overhead (~1-5 ms per channel on a LAN).
class TeamServiceImpl final : public TeamService::Service {
public:
    TeamServiceImpl(ClusterConfig& cfg, const std::string& my_id);

    grpc::Status Fetch(grpc::ServerContext* ctx,
                       const ShardRequest*  req,
                       ShardReply*          out) override;

    long long total_requests()   const { return req_count_.load(std::memory_order_relaxed); }
    long long total_ns_serving() const { return total_ns_.load(std::memory_order_relaxed); }

private:
    std::string buildOwnPayload() const;

    ClusterConfig& config_;
    std::string    id_;
    int            base_;

    struct ChildStub {
        std::string                         id;
        std::unique_ptr<TeamService::Stub>  stub;
    };
    std::vector<ChildStub> child_stubs_;

    std::atomic<long long> req_count_{0};
    std::atomic<long long> total_ns_{0};
};
