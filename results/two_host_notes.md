# Two-Host Notes

Date: 2026-05-08 to 2026-05-09
Git commit at run time: c3e3784 plus local runbook/config/doc edits

host1:
- owner: Anu
- model: Mac laptop
- OS: macOS 14.3
- CPU: Apple M3
- RAM: 8 GB
- IP: 192.168.1.139
- role: A, B, C, D, E, F, client

host2:
- owner: Sasank
- model: MacBook Air
- OS: macOS
- CPU: Apple Silicon
- RAM:
- IP: 192.168.1.118
- role: G, H, I

Network:
- same Wi-Fi? yes
- VPN off? yes
- plugged in? yes
- anything unusual: ping was reliable but variable, with 0% packet loss and
  observed times from about 6.5 ms to 151.7 ms.

Smoke test:
- command: `build/client config/nodes.yaml two_host_smoke 32000 0`
- records: 80000
- chunks: 50
- total_us: 220511

Chunk sweep:
- runs per chunk size: 30
- result file: `results/chunk_sweep_2host_30runs.tsv`
- fastest chunk size by avg total_us: 512000 bytes, 44046 us
- slowest chunk size by avg total_us: 2000 bytes, 337844 us
- outliers noticed: several first/cold or Wi-Fi-spike RPCs exceeded 70 ms; max
  observed RPC was 151171 us.

Fairness:
- result file: `results/fairness_2host.txt`
- fastest client: cli4, 116823 us
- slowest client: cli3, 121798 us
- did every client get same chunks? yes, all received 50 chunks

Failure:
- result file: `results/failure_h_down_2host.txt`
- exact error: `child fetch failed: H: failed to connect to all addresses`
- did it return partial data? no, the request failed clearly

What we learned:
- Two-host results were slower and noisier than loopback, but chunk count still
  dominated total time.
- Large chunks reduced round trips, but 32 KB, 128 KB, and 512 KB were close
  because Wi-Fi outliers flattened the curve.
- The failure path is now visible to the client instead of returning partial
  data that looks successful.
- Deployment details mattered: Python environment, shard placement, and SSH
  setup all affected whether the measurement was trustworthy.
