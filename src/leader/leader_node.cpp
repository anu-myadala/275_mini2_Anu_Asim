#include <grpcpp/grpcpp.h>
#include "cluster.grpc.pb.h"
#include "../common/config.hpp"
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <iostream>
#include <map>
#include <mutex>
#include <stdexcept>
#include <string>
#include <thread>
#include <vector>

using namespace mini2;

static constexpr int DEFAULT_CHUNK_BYTES = 128;
static constexpr int RECORD_SIZE         = 20;
static constexpr int MAX_CHUNK_BYTES     = 1048576;
static constexpr int CACHE_TTL_SEC       = 30;

class FairQueue {
    struct Ticket {
        int debt;
        int seq;
        bool operator<(const Ticket& o) const {
            if (debt != o.debt) return debt < o.debt;
            return seq < o.seq;
        }
    };

public:
    void acquire(const std::string& cli) {
        std::unique_lock<std::mutex> lk(mu_);
        Ticket me{ debt_.count(cli) ? debt_[cli] : 0, ++seq_ };
        waiting_[cli] = me;

        cv_.wait(lk, [&] {
            if (active_) return false;
            for (auto& [wid, wt] : waiting_)
                if (wid != cli && wt < me) return false;
            return true;
        });

        waiting_.erase(cli);
        active_ = true;
    }

    void release(const std::string& cli) {
        {
            std::lock_guard<std::mutex> lk(mu_);
            ++debt_[cli];
            active_ = false;
        }
        cv_.notify_all();
    }

    int debt(const std::string& cli) const {
        std::lock_guard<std::mutex> lk(mu_);
        auto it = debt_.find(cli);
        return (it != debt_.end()) ? it->second : 0;
    }

private:
    mutable std::mutex              mu_;
    std::condition_variable         cv_;
    bool                            active_ = false;
    int                             seq_    = 0;
    std::map<std::string, Ticket>   waiting_;
    std::map<std::string, int>      debt_;
};

struct CacheEntry {
    std::string       payload;
    Clock::time_point last_touched;
};

class LeaderServiceImpl final : public LeaderService::Service {
public:
    LeaderServiceImpl(ClusterConfig& cfg, const std::string& my_id)
        : config_(cfg), id_(my_id), shutdown_(false) {

        for (const std::string& cid : config_.getChildren(id_)) {
            NodeInfo ni = config_.getNode(cid);
            auto ch = grpc::CreateChannel(ni.endpoint(),
                                          grpc::InsecureChannelCredentials());
            child_stubs_.push_back({ cid, TeamService::NewStub(ch) });
            std::cerr << "[Leader " << id_ << "] child " << cid
                      << " -> " << ni.endpoint() << "\n";
        }

        reaper_ = std::thread([this] { reaperLoop(); });
    }

    ~LeaderServiceImpl() {
        shutdown_.store(true);
        if (reaper_.joinable()) reaper_.join();
    }

    grpc::Status QueryOnce(grpc::ServerContext* ctx,
                           const Query*         in,
                           AggregatedReply*     out) override {
        NsCount t0 = now_ns();

        const std::string req_id  = in->request_id();
        const std::string cli_id  = in->client_id();
        int chunk_sz = (in->chunk_size() > 0) ? in->chunk_size()
                                               : DEFAULT_CHUNK_BYTES;
        int offset   = in->offset();

        chunk_sz = std::max(RECORD_SIZE,
                   std::min(chunk_sz, MAX_CHUNK_BYTES));

        fq_.acquire(cli_id);

        if (ctx->IsCancelled()) {
            fq_.release(cli_id);
            return grpc::Status(grpc::StatusCode::CANCELLED, "client cancelled");
        }

        std::string full;
        try {
            full = fetchOrCache(req_id, in);
        } catch (const std::exception& ex) {
            fq_.release(cli_id);
            return grpc::Status(grpc::StatusCode::INTERNAL, ex.what());
        }

        int total = static_cast<int>(full.size());
        int start = offset;

        int raw_end = std::min(start + chunk_sz, total);
        int end     = raw_end;
        if (end < total) {
            int aligned = start + ((end - start) / RECORD_SIZE) * RECORD_SIZE;
            if (aligned > start) end = aligned;
        }

        if (start < total) {
            auto* seg = out->add_segments();
            seg->set_payload(full.substr(start, end - start));
            seg->set_last(end >= total);
        }

        bool more = (end < total);
        out->set_has_more(more);
        out->set_next_offset(more ? end : -1);
        out->set_complete(!more);

        NsCount dt = elapsed_ns(t0);
        ++total_requests_;
        total_ns_.fetch_add(dt, std::memory_order_relaxed);

        std::cout << "[Leader] cli=" << cli_id
                  << " debt=" << fq_.debt(cli_id)
                  << " off=" << offset
                  << " bytes=" << (end - start)
                  << " dt=" << dt / 1000 << "us"
                  << (more ? " [more]" : " [done]") << "\n";

        if (!more) evict(req_id);

        fq_.release(cli_id);
        return grpc::Status::OK;
    }

    void printStats() const {
        long long reqs = total_requests_.load();
        long long ns   = total_ns_.load();
        long long avg  = reqs > 0 ? ns / reqs / 1000 : 0;
        std::cout << "[Leader] shutdown."
                  << " total_requests=" << reqs
                  << " avg_us=" << avg << "\n";
    }

private:
    std::string gatherFromChildren(const Query* in) {
        const size_t n = child_stubs_.size();
        std::vector<std::string> parts(n);
        std::vector<std::string> errors(n);
        std::vector<std::thread> threads;
        threads.reserve(n);

        for (size_t i = 0; i < n; ++i) {
            threads.emplace_back([&, i] {
                ShardRequest req;
                req.mutable_query()->CopyFrom(*in);
                ShardReply          rep;
                grpc::ClientContext ctx;

                auto status = child_stubs_[i].stub->Fetch(&ctx, req, &rep);
                if (!status.ok()) {
                    errors[i] = child_stubs_[i].id + ": " + status.error_message();
                    return;
                }
                for (const auto& s : rep.segments())
                    parts[i] += s.payload();
            });
        }
        for (auto& t : threads) t.join();

        for (const auto& err : errors) {
            if (!err.empty())
                throw std::runtime_error("child fetch failed: " + err);
        }

        std::string payload;
        for (auto& p : parts) payload += p;
        return payload;
    }

    std::string fetchOrCache(const std::string& req_id, const Query* in) {
        {
            std::lock_guard<std::mutex> lk(cache_mu_);
            auto it = cache_.find(req_id);
            if (it != cache_.end()) {
                it->second.last_touched = Clock::now();
                return it->second.payload;
            }
        }

        std::string payload = gatherFromChildren(in);

        std::lock_guard<std::mutex> lk(cache_mu_);
        cache_[req_id] = { payload, Clock::now() };
        return cache_[req_id].payload;
    }

    void evict(const std::string& req_id) {
        std::lock_guard<std::mutex> lk(cache_mu_);
        cache_.erase(req_id);
    }

    void reaperLoop() {
        while (!shutdown_.load()) {
            std::this_thread::sleep_for(std::chrono::seconds(5));
            auto now = Clock::now();
            std::lock_guard<std::mutex> lk(cache_mu_);
            for (auto it = cache_.begin(); it != cache_.end(); ) {
                auto age = std::chrono::duration_cast<std::chrono::seconds>(
                    now - it->second.last_touched).count();
                if (age > CACHE_TTL_SEC) {
                    std::cout << "[Leader] evicted abandoned req: "
                              << it->first << "\n";
                    it = cache_.erase(it);
                } else {
                    ++it;
                }
            }
        }
    }

    ClusterConfig& config_;
    std::string    id_;

    struct ChildStub {
        std::string                        id;
        std::unique_ptr<TeamService::Stub> stub;
    };
    std::vector<ChildStub> child_stubs_;

    FairQueue                              fq_;
    std::mutex                             cache_mu_;
    std::map<std::string, CacheEntry>      cache_;

    std::atomic<bool>      shutdown_;
    std::thread            reaper_;
    std::atomic<long long> total_requests_{0};
    std::atomic<long long> total_ns_{0};
};
