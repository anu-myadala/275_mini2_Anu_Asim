#pragma once
#include <yaml-cpp/yaml.h>
#include <chrono>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

// ── Timing utility ────────────────────────────────────────────────────────────
// All latency measurements in the codebase use these types for consistency.
// steady_clock is monotonic and unaffected by wall-clock adjustments.
using Clock   = std::chrono::steady_clock;
using NsCount = long long;

inline NsCount now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now().time_since_epoch()).count();
}

inline NsCount elapsed_ns(NsCount start_ns) { return now_ns() - start_ns; }

// ── Per-node address/port ─────────────────────────────────────────────────────
struct NodeInfo {
    std::string addr;
    int         port;
    std::string endpoint() const { return addr + ":" + std::to_string(port); }
};

// ── Cluster configuration loaded from nodes.yaml ─────────────────────────────
// Reads the overlay graph, derives the BFS spanning tree from the designated
// leader, and exposes per-node address info and child lists.
//
// Design: the overlay is undirected. BFS from the root imposes a tree
// direction (parent → children). This means the physical topology can be
// re-wired by editing nodes.yaml alone; no source change is needed.
// Node identity (the letter A–I) is also read at runtime, never hardcoded.
class ClusterConfig {
public:
    bool load(const std::string& path) {
        try {
            YAML::Node cfg = YAML::LoadFile(path);

            auto hosts = cfg["hosts"];
            auto ports = cfg["ports"];

            // 1. Build node-id -> {addr, port}
            for (auto h : hosts) {
                std::string addr = h.second["addr"].as<std::string>();
                for (auto p : h.second["procs"]) {
                    std::string nid = p.as<std::string>();
                    nodes_[nid] = { addr, ports[nid].as<int>() };
                }
            }

            // 2. Adjacency list (undirected) from overlay edges
            for (auto edge : cfg["overlay"]) {
                std::string a = edge[0].as<std::string>();
                std::string b = edge[1].as<std::string>();
                adj_[a].push_back(b);
                adj_[b].push_back(a);
            }

            // 3. Find designated root (leader)
            for (auto r : cfg["roles"]) {
                std::string nid  = r.first.as<std::string>();
                std::string role = r.second["role"].as<std::string>();
                if (role == "leader") { root_ = nid; break; }
            }
            if (root_.empty() && !nodes_.empty())
                root_ = nodes_.begin()->first;

            // 4. BFS to build parent→children directed tree
            buildTree();
            return true;
        } catch (...) {
            return false;
        }
    }

    NodeInfo getNode(const std::string& id) const {
        auto it = nodes_.find(id);
        if (it == nodes_.end())
            throw std::runtime_error("Unknown node id: " + id);
        return it->second;
    }

    std::vector<std::string> getChildren(const std::string& id) const {
        auto it = children_.find(id);
        if (it == children_.end()) return {};
        return it->second;
    }

    const std::string& root() const { return root_; }

    // Expose the full node map for benchmarking scripts that need to iterate.
    const std::map<std::string, NodeInfo>& nodes() const { return nodes_; }

private:
    void buildTree() {
        if (root_.empty()) return;
        std::map<std::string, bool> visited;
        std::vector<std::string>    q;
        visited[root_] = true;
        q.push_back(root_);
        for (size_t i = 0; i < q.size(); ++i) {
            const std::string& cur = q[i];
            auto it = adj_.find(cur);
            if (it == adj_.end()) continue;
            for (const std::string& nb : it->second) {
                if (!visited[nb]) {
                    visited[nb] = true;
                    children_[cur].push_back(nb);
                    q.push_back(nb);
                }
            }
        }
    }

    std::map<std::string, NodeInfo>                 nodes_;
    std::map<std::string, std::vector<std::string>> adj_;
    std::map<std::string, std::vector<std::string>> children_;
    std::string                                     root_;
};
