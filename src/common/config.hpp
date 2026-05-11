#pragma once
#include <yaml-cpp/yaml.h>
#include <chrono>
#include <map>
#include <stdexcept>
#include <string>
#include <vector>

using Clock   = std::chrono::steady_clock;
using NsCount = long long;

inline NsCount now_ns() {
    return std::chrono::duration_cast<std::chrono::nanoseconds>(
        Clock::now().time_since_epoch()).count();
}

inline NsCount elapsed_ns(NsCount start_ns) { return now_ns() - start_ns; }

struct NodeInfo {
    std::string addr;
    int         port;
    std::string endpoint() const { return addr + ":" + std::to_string(port); }
};

class ClusterConfig {
public:
    bool load(const std::string& path) {
        try {
            YAML::Node cfg = YAML::LoadFile(path);

            auto hosts = cfg["hosts"];
            auto ports = cfg["ports"];

            for (auto h : hosts) {
                std::string addr = h.second["addr"].as<std::string>();
                for (auto p : h.second["procs"]) {
                    std::string nid = p.as<std::string>();
                    nodes_[nid] = { addr, ports[nid].as<int>() };
                }
            }

            for (auto edge : cfg["overlay"]) {
                std::string a = edge[0].as<std::string>();
                std::string b = edge[1].as<std::string>();
                adj_[a].push_back(b);
                adj_[b].push_back(a);
            }

            for (auto r : cfg["roles"]) {
                std::string nid  = r.first.as<std::string>();
                std::string role = r.second["role"].as<std::string>();
                if (role == "leader") { root_ = nid; break; }
            }
            if (root_.empty() && !nodes_.empty())
                root_ = nodes_.begin()->first;

            // The explicit tree avoids ambiguous parents in the overlay.
            if (cfg["children"]) {
                for (auto item : cfg["children"]) {
                    std::string parent = item.first.as<std::string>();
                    for (auto child : item.second)
                        children_[parent].push_back(child.as<std::string>());
                }
            } else {
                buildTree();
            }
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
