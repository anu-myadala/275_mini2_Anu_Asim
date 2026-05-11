#!/usr/bin/env python3
from pathlib import Path

import matplotlib.pyplot as plt
from docx import Document
from docx.shared import Inches, Pt
from docx.enum.text import WD_ALIGN_PARAGRAPH
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN
from pptx.dml.color import RGBColor
from pptx.util import Inches as PptInches, Pt as PptPt


ROOT = Path(__file__).resolve().parents[1]
CHUNKS = [2000, 8000, 32000, 128000, 512000]
TOTAL_US = [337844, 91303, 45748, 47482, 44046]
MEDIAN_US = [345594, 85771, 39882, 28276, 25782]
P90_US = [391651, 105447, 61045, 115303, 110104]
CV = [0.14, 0.16, 0.26, 0.74, 0.80]


def rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return RGBColor(int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16))


def add_heading(doc, text, level=1):
    p = doc.add_heading(text, level=level)
    for run in p.runs:
        run.font.name = "Aptos Display"
    return p


def add_para(doc, text, bold_prefix=None):
    p = doc.add_paragraph()
    if bold_prefix and text.startswith(bold_prefix):
        r = p.add_run(bold_prefix)
        r.bold = True
        p.add_run(text[len(bold_prefix):])
    else:
        p.add_run(text)
    return p


def make_docx():
    doc = Document()
    sec = doc.sections[0]
    sec.top_margin = Inches(0.7)
    sec.bottom_margin = Inches(0.7)
    sec.left_margin = Inches(0.8)
    sec.right_margin = Inches(0.8)

    title = doc.add_paragraph()
    title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = title.add_run("Mini 2: Distributed 311 Query Chunking")
    r.bold = True
    r.font.size = Pt(20)

    subtitle = doc.add_paragraph()
    subtitle.alignment = WD_ALIGN_PARAGRAPH.CENTER
    subtitle.add_run("Anukrithi Myadala, Asim Mohammed").italic = True

    add_heading(doc, "Research Question", 1)
    add_para(doc, "How does chunk size affect a distributed, sharded 311 result set when A is the only client-facing process?")

    add_heading(doc, "Mini 1 Takeaways Applied", 1)
    for item in [
        "Use typed fields instead of strings for everything.",
        "Avoid shared merge contention by gathering child replies into separate buffers.",
        "Reserve or reuse storage where possible.",
        "Report failures and limitations, not only successful timings.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    add_heading(doc, "Design", 1)
    add_para(doc, "The cluster uses a configured scatter-gather tree: A -> B,H,G,I; B -> C,D,E; E -> F. A is the only public entry point. B-I own typed binary shards, and I is implemented in Python.")
    add_para(doc, "The data source is NYC 311 Service Requests from 2020 to Present. We used a 90,000-row subset from the public CSV so the test was repeatable and the Canvas submission did not include the large dataset.")
    add_para(doc, "Each 311 row is stored as a compact 20-byte record: unique key, latitude, longitude, incident zip, created year, status code, and borough code.")
    add_para(doc, "The design uses unary gRPC calls with explicit offsets. A streaming prototype was dropped because the assignment required non-streaming gRPC and the explicit offsets made failure behavior easier to test.")

    add_heading(doc, "Course and Lab Ideas Used", 1)
    for item in [
        "The basic-grpc lab shaped the protobuf/service structure and unary call pattern.",
        "The leader-adv lab shaped A as the coordinator while B-I do shard work.",
        "The socket interoperability lab made us treat the C++/Python 20-byte record layout as a contract.",
        "Socket and messaging lectures motivated the chunk-size experiment.",
        "The sharding lecture motivated splitting the binary data across B-I.",
        "MPI round/baton-style labs influenced the fairness test.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    add_heading(doc, "Mini 2 Questions Answered", 1)
    questions = [
        ("Performance/resources", "30-run chunk sweep measured total time, chunk count, avg RPC time, min RPC time, and max RPC time."),
        ("Conserve memory", "20-byte typed records, explicit chunk offsets, and a 1 MB max chunk instead of unbounded responses."),
        ("Fairness/balance", "Four-client run showed equal chunk turns, but not identical finish times."),
        ("Flexible overlay", "Host/process/tree settings live in YAML; identity and config path are runtime arguments."),
        ("No flat shortcut", "Final tree uses A -> B,H,G,I; B -> C,D,E; E -> F."),
        ("Request failure/abandonment", "Fail-fast before gather; cache-complete behavior after gather; no speculative prefetching because it would increase A memory pressure."),
    ]
    table_q = doc.add_table(rows=1, cols=2)
    table_q.style = "Table Grid"
    table_q.rows[0].cells[0].text = "Prompt challenge"
    table_q.rows[0].cells[1].text = "Our answer"
    for left, right in questions:
        cells = table_q.add_row().cells
        cells[0].text = left
        cells[1].text = right

    add_heading(doc, "Measurement Plan", 1)
    add_para(doc, "The course notes recommend 15-30 runs to form an average and discard clear outliers. The final table below uses 30 runs per chunk size on two laptops.")

    add_heading(doc, "Two-Host Results", 1)
    table = doc.add_table(rows=1, cols=4)
    table.style = "Table Grid"
    hdr = table.rows[0].cells
    hdr[0].text = "Chunk bytes"
    hdr[1].text = "Avg total us"
    hdr[2].text = "Avg chunks"
    hdr[3].text = "Avg RPC us"
    rows = [
        (2000, 337844, 800, 422),
        (8000, 91303, 200, 456),
        (32000, 45748, 50, 914),
        (128000, 47482, 13, 3652),
        (512000, 44046, 4, 11011),
    ]
    for row in rows:
        cells = table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)

    add_para(doc, "Result: 512 KB chunks completed the same 80,000-record response about 7.7x faster than 2 KB chunks across two laptops because the client needed 4 chunks instead of 800. The more interesting result is the knee in the curve: 32 KB used 50 chunks and averaged 45.7 ms, while 512 KB used only 4 chunks and averaged 44.0 ms. That 1.7 ms difference means page count stopped being the only important cost after about 32 KB.")
    add_para(doc, "The accurate interpretation is that chunk size shifts cost between repeated paging overhead and a fixed gather/transfer floor. The first page triggers A to gather and cache the full 1.6 MB response from B-I. Later pages come from A's cache, so small chunks pay many local unary RPC/cache-copy steps. Once chunks are large enough, the remaining time is dominated by the one-time gather, payload movement, serialization/copying, and Wi-Fi tail spikes.")

    add_heading(doc, "Mean, Median, and Tail Behavior", 1)
    tail_table = doc.add_table(rows=1, cols=5)
    tail_table.style = "Table Grid"
    hdr = tail_table.rows[0].cells
    hdr[0].text = "Chunk bytes"
    hdr[1].text = "Mean ms"
    hdr[2].text = "Median ms"
    hdr[3].text = "P90 ms"
    hdr[4].text = "CV"
    rows_tail = [
        (2000, 337.8, 345.6, 391.7, 0.14),
        (8000, 91.3, 85.8, 105.4, 0.16),
        (32000, 45.7, 39.9, 61.0, 0.26),
        (128000, 47.5, 28.3, 115.3, 0.74),
        (512000, 44.0, 25.8, 110.1, 0.80),
    ]
    for row in rows_tail:
        cells = tail_table.add_row().cells
        for i, value in enumerate(row):
            cells[i].text = str(value)
    add_para(doc, "CV is the sample standard deviation divided by the mean across the 30 runs.")
    add_para(doc, "The medians show that large chunks were usually faster, but the high P90/CV values show why their means were not much better than 32 KB. With only 4-13 chunks, one slow remote gather or large response spike can dominate an entire run. A 32 KB chunk is therefore a good robust operating point for this setup: near-fastest mean, lower tail risk, and the fairness test was run at this size.")

    add_heading(doc, "Fairness Result", 1)
    add_para(doc, "Four clients at 32 KB chunks each completed 50 chunks. The slowest client was about 4.3% slower than the fastest, so the queue balances chunk turns but does not guarantee identical wall-clock finish times.")

    add_heading(doc, "Failures Found and Fixed", 1)
    failures = [
        "Early per-RPC channel/stub setup made the prototype measure setup overhead too much. Child stubs are now created once during startup.",
        "A streaming/async detour was abandoned because the final design needed unary gRPC and clearer failure behavior.",
        "Old processes were already bound to ports 50051, 50052, and 50058, causing the client to hit the wrong server.",
        "The first tree derivation only contacted B's subtree. The directed tree is now explicit in nodes.yaml.",
        "Partial child failures could be cached. Child fetch failures now fail the request.",
        "Client request ids were reused. They now include a per-run timestamp.",
        "Python and C++ initially had to be checked carefully for exact binary record size and field order. The final record is a validated 20-byte layout.",
        "The Python node failed under system Python without yaml. The launcher now uses venv/bin/python when available.",
        "Host2 Homebrew Python loaded macOS's older libexpat, which broke ensurepip. We used Python 3.12 with Homebrew's expat path.",
        "Node I initially used fallback sample data until we copied the real shards to host2 and restarted the node.",
        "The first benchmark included one-record chunks, which was too slow for normal iteration. Tiny chunks are now opt-in.",
        "Large requested chunks were clamped to 64 KB. The cap is now 1 MB.",
        "With H down before a new request, the client fails clearly. If H dies after A has cached the gathered result, that same request can still finish from cache.",
    ]
    for item in failures:
        doc.add_paragraph(item, style="List Bullet")

    add_heading(doc, "Conclusion", 1)
    add_para(doc, "The final result supports one focused conclusion: chunk size has a knee around 32 KB. Below 32 KB, repeated pages dominate. Above 32 KB, the fixed gather/transfer floor and tail variance dominate. If optimizing only for mean or median, 512 KB wins by a small amount. If optimizing for robustness, fairness, and tail behavior, 32 KB is the better operating point for this two-laptop setup. This conclusion only became trustworthy after we fixed port collisions, topology mistakes, cache behavior, the hidden chunk cap, Python setup problems, missing shard deployment, and binary-layout validation.")

    add_heading(doc, "Individual Contributions", 1)
    add_para(doc, "Anukrithi Myadala focused on Mini 1 feedback analysis, runbooks, two-computer setup, result collection, report, and presentation framing. Asim Mohammed contributed to the cluster/protobuf implementation and helped with final code cleanup and validation.")

    add_heading(doc, "References", 1)
    for item in [
        "NYC Open Data / Data.gov, 311 Service Requests from 2020 to Present: https://catalog.data.gov/dataset/311-service-requests-from-2010-to-present",
        "NYC Open Data, 311 Service Requests Updates: https://opendata.cityofnewyork.us/311-service-requests-from-2010-to-present-updates/",
        "gRPC, Performance Best Practices: https://grpc.io/docs/guides/performance/",
        "Protocol Buffers, Encoding: https://protobuf.dev/programming-guides/encoding/",
        "Protocol Buffers, Language Guide (proto3): https://protobuf.dev/programming-guides/proto3/",
        "Python struct documentation for the exact C++/Python binary record contract: https://docs.python.org/3/library/struct.html",
        "CMake add_custom_command documentation for generating protobuf/gRPC sources during the build: https://cmake.org/cmake/help/latest/command/add_custom_command.html",
        "gRPC C++ basics tutorial for protoc/grpc_cpp_plugin build pattern: https://grpc.io/docs/languages/cpp/basics/",
        "PyYAML documentation for loading YAML configuration on the Python node: https://pyyaml.org/wiki/PyYAMLDocumentation",
        "yaml-cpp project documentation for C++ YAML parsing: https://github.com/jbeder/yaml-cpp",
        "python-pptx documentation for generating the one-slide poster: https://python-pptx.readthedocs.io/",
        "Matplotlib barh documentation for the horizontal poster chart: https://matplotlib.org/stable/api/_as_gen/matplotlib.pyplot.barh.html",
        "AMD Vitis HLS Documentation, Data Structure Padding: https://docs.amd.com/r/2024.1-English/ug1399-vitis-hls/Data-Structure-Padding",
        "Course lectures on messaging/socket costs, sharding, parallelism, failure behavior, and benchmarking.",
        "Course labs covering basic gRPC, leader coordination, MPI round/baton behavior, and sockets.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.save(ROOT / "mini2-report.docx")


def make_poster_chart(path):
    labels = ["2 KB  | 800 pages", "8 KB  | 200 pages", "32 KB | 50 pages", "128 KB | 13 pages", "512 KB | 4 pages"]
    mean_ms = [v / 1000 for v in TOTAL_US]
    median_ms = [v / 1000 for v in MEDIAN_US]
    p90_ms = [v / 1000 for v in P90_US]
    colors = ["#fb7185", "#fbbf24", "#38bdf8", "#34d399", "#a78bfa"]

    plt.figure(figsize=(8.4, 4.9), facecolor="#111827")
    ax = plt.gca()
    ax.set_facecolor("#111827")
    bars = ax.barh(labels, mean_ms, color=colors, height=0.52, alpha=0.95, label="mean")
    ax.invert_yaxis()
    ax.set_xlim(0, 430)
    ax.set_xlabel("total request time, ms", color="#cbd5e1", labelpad=10)
    ax.tick_params(axis="x", colors="#94a3b8", labelsize=10)
    ax.tick_params(axis="y", colors="#f8fafc", labelsize=11.5)
    ax.grid(axis="x", color="#334155", linewidth=0.7, alpha=0.55)
    ax.set_axisbelow(True)
    for spine in ax.spines.values():
        spine.set_visible(False)
    for bar, value, med, p90 in zip(bars, mean_ms, median_ms, p90_ms):
        y = bar.get_y() + bar.get_height() / 2
        ax.plot(med, y, marker="o", markersize=7, color="#f8fafc", markeredgecolor="#111827", markeredgewidth=1.2)
        ax.plot([med, p90], [y, y], color="#e2e8f0", linewidth=1.2, alpha=0.45)
        ax.plot(p90, y, marker="|", markersize=15, color="#e2e8f0", alpha=0.85)
        ax.text(
            bar.get_width() + 7,
            y,
            f"mean {value:.0f}",
            va="center",
            ha="left",
            color="#f8fafc",
            fontsize=12,
            fontweight="bold",
        )
    ax.text(
        0,
        -0.92,
        "Mean bars, median dots, P90 ticks",
        color="#e2e8f0",
        fontsize=13,
        fontweight="bold",
    )
    ax.text(
        0,
        -0.55,
        "Knee near 32 KB: mean flattens after that, but tail risk grows.",
        color="#94a3b8",
        fontsize=10.5,
    )
    plt.tight_layout(pad=1.8)
    plt.savefig(path, dpi=220, facecolor="#111827")
    plt.close()


def make_poster():
    poster_chart = ROOT / "results" / "poster_chunk_chart.png"
    make_poster_chart(poster_chart)

    prs = Presentation()
    prs.slide_width = PptInches(13.333)
    prs.slide_height = PptInches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = rgb("#070b16")

    def add_box(x, y, w, h, fill, line="#1e293b", radius=True):
        kind = MSO_SHAPE.ROUNDED_RECTANGLE if radius else MSO_SHAPE.RECTANGLE
        shape = slide.shapes.add_shape(kind, x, y, w, h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = rgb(fill)
        shape.line.color.rgb = rgb(line)
        return shape

    def add_text(x, y, w, h, text, size, color="#f8fafc", bold=False, align=None):
        shape = slide.shapes.add_textbox(x, y, w, h)
        tf = shape.text_frame
        tf.clear()
        p = tf.paragraphs[0]
        p.text = text
        if align:
            p.alignment = align
        p.font.size = PptPt(size)
        p.font.bold = bold
        p.font.color.rgb = rgb(color)
        return shape

    add_box(PptInches(0), PptInches(0), PptInches(13.333), PptInches(0.12), "#f59e0b", "#f59e0b", False)
    add_text(PptInches(0.45), PptInches(0.31), PptInches(4.55), PptInches(0.48), "THE 32 KB KNEE", 34, "#facc15", True)
    add_text(
        PptInches(5.05),
        PptInches(0.35),
        PptInches(6.8),
        PptInches(0.5),
        "Repeated pages dominated until the gather/cache floor took over",
        16,
        "#e2e8f0",
        True,
    )
    add_text(PptInches(11.55), PptInches(0.35), PptInches(1.25), PptInches(0.3), "Anukrithi + Asim", 9.5, "#94a3b8", False, PP_ALIGN.RIGHT)
    add_text(
        PptInches(5.08),
        PptInches(0.78),
        PptInches(6.6),
        PptInches(0.22),
        "NYC 311 2020-present | 80k returned rows | 20-byte records | A-F host1, G/H/I host2 | 30 runs/size",
        9.5,
        "#94a3b8",
    )

    add_box(PptInches(0.45), PptInches(1.05), PptInches(7.65), PptInches(5.45), "#111827", "#334155")
    slide.shapes.add_picture(str(poster_chart), PptInches(0.72), PptInches(1.32), width=PptInches(7.12), height=PptInches(4.7))
    add_text(PptInches(0.82), PptInches(5.95), PptInches(6.9), PptInches(0.32), "30 runs per chunk size on two laptops over Wi-Fi", 11, "#cbd5e1", False, PP_ALIGN.CENTER)
    add_text(PptInches(0.82), PptInches(6.2), PptInches(6.9), PptInches(0.2), "keywords: page count | gather/cache floor | P90 tail | opportunity fairness | fail-fast", 8.8, "#94a3b8", False, PP_ALIGN.CENTER)

    add_box(PptInches(8.35), PptInches(1.05), PptInches(4.55), PptInches(1.45), "#172033", "#475569")
    add_text(PptInches(8.65), PptInches(1.2), PptInches(1.75), PptInches(0.55), "7.7x", 42, "#facc15", True)
    add_text(PptInches(10.35), PptInches(1.25), PptInches(2.15), PptInches(0.38), "faster total time", 15, "#f8fafc", True)
    add_text(PptInches(10.35), PptInches(1.66), PptInches(2.15), PptInches(0.48), "338 ms -> 44 ms", 20, "#38bdf8", True)
    add_text(PptInches(8.65), PptInches(2.12), PptInches(3.95), PptInches(0.25), "mean improvement from 2 KB to 512 KB", 10.5, "#94a3b8")

    add_box(PptInches(8.35), PptInches(2.75), PptInches(4.55), PptInches(1.0), "#101826", "#334155")
    add_text(PptInches(8.62), PptInches(2.9), PptInches(3.95), PptInches(0.25), "Why 50 pages ~= 4 pages", 14, "#f8fafc", True)
    add_text(PptInches(8.7), PptInches(3.23), PptInches(1.25), PptInches(0.35), "45.7", 23, "#38bdf8", True, PP_ALIGN.CENTER)
    add_text(PptInches(9.88), PptInches(3.29), PptInches(0.55), PptInches(0.25), "vs", 12, "#94a3b8", False, PP_ALIGN.CENTER)
    add_text(PptInches(10.45), PptInches(3.23), PptInches(1.2), PptInches(0.35), "44.0", 23, "#a78bfa", True, PP_ALIGN.CENTER)
    add_text(PptInches(11.55), PptInches(3.32), PptInches(0.7), PptInches(0.2), "ms mean", 9.5, "#cbd5e1")

    add_box(PptInches(8.35), PptInches(4.05), PptInches(4.55), PptInches(1.65), "#111827", "#334155")
    add_text(PptInches(8.65), PptInches(4.2), PptInches(3.95), PptInches(0.25), "The tradeoff after the knee", 14, "#f8fafc", True)
    add_text(PptInches(8.68), PptInches(4.62), PptInches(1.1), PptInches(0.28), "32 KB", 17, "#38bdf8", True, PP_ALIGN.CENTER)
    add_text(PptInches(9.85), PptInches(4.62), PptInches(1.1), PptInches(0.28), "512 KB", 17, "#a78bfa", True, PP_ALIGN.CENTER)
    add_text(PptInches(11.08), PptInches(4.62), PptInches(1.1), PptInches(0.28), "meaning", 12, "#cbd5e1", True, PP_ALIGN.CENTER)
    add_text(PptInches(8.67), PptInches(5.0), PptInches(1.1), PptInches(0.22), "P90 61 ms", 10, "#dbeafe", False, PP_ALIGN.CENTER)
    add_text(PptInches(9.85), PptInches(5.0), PptInches(1.1), PptInches(0.22), "P90 110 ms", 10, "#ede9fe", False, PP_ALIGN.CENTER)
    add_text(PptInches(11.04), PptInches(4.96), PptInches(1.3), PptInches(0.44), "larger chunks were faster typically, but spikier", 8.7, "#cbd5e1", False, PP_ALIGN.CENTER)

    add_box(PptInches(8.35), PptInches(5.98), PptInches(2.15), PptInches(0.75), "#13251f", "#34d399")
    add_text(PptInches(8.55), PptInches(6.1), PptInches(1.75), PptInches(0.2), "Robust point", 12, "#bbf7d0", True)
    add_text(PptInches(8.55), PptInches(6.36), PptInches(1.75), PptInches(0.2), "32 KB: near-fastest mean, lower tail", 8.8, "#dcfce7")

    add_box(PptInches(10.75), PptInches(5.98), PptInches(2.15), PptInches(0.75), "#2a1b13", "#f59e0b")
    add_text(PptInches(10.95), PptInches(6.1), PptInches(1.75), PptInches(0.2), "Validated first", 12, "#fde68a", True)
    add_text(PptInches(10.95), PptInches(6.36), PptInches(1.75), PptInches(0.2), "ports, tree, cache, cap, layout, shards", 8.5, "#ffedd5")

    add_text(
        PptInches(0.55),
        PptInches(6.85),
        PptInches(12.2),
        PptInches(0.28),
        "Takeaway: chunk size shifts cost from repeated paging to a fixed gather/transfer floor; 32 KB is the knee for this setup.",
        13,
        "#e2e8f0",
        True,
        PP_ALIGN.CENTER,
    )

    prs.save(ROOT / "mini2-poster.pptx")


def main():
    make_docx()
    make_poster()
    plt.figure(figsize=(8, 4.4))
    plt.bar([str(x) for x in CHUNKS], TOTAL_US, color="#50beaa")
    plt.title("Total Request Time vs. Chunk Size")
    plt.xlabel("Chunk bytes")
    plt.ylabel("Avg total us")
    plt.tight_layout()
    plt.savefig(ROOT / "results" / "chunk_sweep_chart.png", dpi=160)


if __name__ == "__main__":
    main()
