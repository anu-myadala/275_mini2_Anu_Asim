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
from pptx.dml.color import RGBColor
from pptx.util import Inches as PptInches, Pt as PptPt


ROOT = Path(__file__).resolve().parents[1]
CHUNKS = [2000, 8000, 32000, 128000, 512000]
TOTAL_US = [337844, 91303, 45748, 47482, 44046]


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
    add_para(doc, "Each 311 row is stored as a compact 20-byte record: unique key, latitude, longitude, incident zip, created year, status code, and borough code.")
    add_para(doc, "The design uses unary gRPC calls with explicit offsets. A streaming prototype was dropped because the assignment required non-streaming gRPC and the explicit offsets made failure behavior easier to test.")

    add_heading(doc, "Course and Lab Ideas Used", 1)
    for item in [
        "The basic gRPC lab shaped the protobuf/service structure.",
        "The leader labs shaped A as the only public coordinator.",
        "Socket and messaging lectures motivated the chunk-size experiment.",
        "The sharding lecture motivated splitting the binary data across B-I.",
        "MPI round/baton-style labs influenced the fairness test.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

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

    add_para(doc, "Result: 512 KB chunks completed the same 80,000-record response about 7.7x faster than 2 KB chunks across two laptops because the client needed 4 chunks instead of 800. The 32 KB, 128 KB, and 512 KB results were close because Wi-Fi introduced large outliers.")

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
    add_para(doc, "The final result supports one focused conclusion: chunk size changed total request time mainly by changing the number of client-leader round trips. The fastest result was useful, but it only became trustworthy after we fixed port collisions, topology mistakes, cache behavior, Python setup problems, missing shard deployment, and benchmark defaults.")

    add_heading(doc, "Individual Contributions", 1)
    add_para(doc, "Anukrithi Myadala focused on Mini 1 feedback analysis, runbooks, two-computer setup, result collection, report, and presentation framing. Asim Mohammed contributed to the cluster/protobuf implementation and helped with final code cleanup and validation.")

    add_heading(doc, "References", 1)
    for item in [
        "NYC Open Data 311 Service Requests dataset.",
        "Course lectures on messaging/socket costs, sharding, parallelism, failure behavior, and benchmarking.",
        "Course labs covering basic gRPC, leader coordination, MPI round/baton behavior, and sockets.",
        "gRPC and Protocol Buffers documentation for unary service structure and typed messages.",
        "Data structure alignment notes used after Mini 1 feedback.",
    ]:
        doc.add_paragraph(item, style="List Bullet")

    doc.save(ROOT / "mini2-report.docx")


def make_poster():
    prs = Presentation()
    prs.slide_width = PptInches(13.333)
    prs.slide_height = PptInches(7.5)
    slide = prs.slides.add_slide(prs.slide_layouts[6])

    bg = slide.background.fill
    bg.solid()
    bg.fore_color.rgb = RGBColor(12, 18, 28)

    def box(x, y, w, h, color, alpha=0):
        shape = slide.shapes.add_shape(MSO_SHAPE.ROUNDED_RECTANGLE, x, y, w, h)
        shape.fill.solid()
        shape.fill.fore_color.rgb = color
        shape.line.color.rgb = RGBColor(40, 54, 75)
        return shape

    title = slide.shapes.add_textbox(PptInches(0.45), PptInches(0.22), PptInches(9.6), PptInches(0.78))
    tf = title.text_frame
    tf.text = "The Fastest Curve Was Not Trustworthy Until We Broke It"
    p = tf.paragraphs[0]
    p.font.size = PptPt(30)
    p.font.bold = True
    p.font.color.rgb = RGBColor(245, 248, 255)

    sub = slide.shapes.add_textbox(PptInches(0.48), PptInches(0.92), PptInches(8.6), PptInches(0.35))
    sub.text_frame.text = "NYC 311 scatter-gather: chunk-size result plus the failures that validated it"
    sub.text_frame.paragraphs[0].font.size = PptPt(13)
    sub.text_frame.paragraphs[0].font.color.rgb = RGBColor(166, 178, 196)

    chart_data = CategoryChartData()
    chart_data.categories = ["2 KB", "8 KB", "32 KB", "128 KB", "512 KB"]
    chart_data.add_series("Avg total time (us)", TOTAL_US)
    chart = slide.shapes.add_chart(
        XL_CHART_TYPE.COLUMN_CLUSTERED,
        PptInches(0.55), PptInches(1.55), PptInches(7.0), PptInches(4.75),
        chart_data
    ).chart
    chart.has_legend = False
    chart.chart_title.has_text_frame = True
    chart.chart_title.text_frame.text = "Total Request Time vs. Chunk Size"
    chart.value_axis.tick_labels.font.size = PptPt(9)
    chart.category_axis.tick_labels.font.size = PptPt(10)
    chart.plots[0].has_data_labels = True
    chart.plots[0].data_labels.position = XL_LABEL_POSITION.OUTSIDE_END
    chart.plots[0].data_labels.font.size = PptPt(8)
    chart.series[0].format.fill.solid()
    chart.series[0].format.fill.fore_color.rgb = RGBColor(80, 190, 170)

    box(PptInches(8.05), PptInches(1.45), PptInches(4.8), PptInches(1.25), RGBColor(20, 31, 47))
    metric = slide.shapes.add_textbox(PptInches(8.35), PptInches(1.6), PptInches(4.2), PptInches(0.85))
    metric.text_frame.text = "7.7x faster"
    metric.text_frame.paragraphs[0].font.size = PptPt(38)
    metric.text_frame.paragraphs[0].font.bold = True
    metric.text_frame.paragraphs[0].font.color.rgb = RGBColor(255, 210, 92)

    note = slide.shapes.add_textbox(PptInches(8.35), PptInches(2.35), PptInches(4.2), PptInches(0.35))
    note.text_frame.text = "512 KB chunks vs. 2 KB chunks, two laptops, 80,000 records"
    note.text_frame.paragraphs[0].font.size = PptPt(11)
    note.text_frame.paragraphs[0].font.color.rgb = RGBColor(198, 208, 224)

    box(PptInches(8.05), PptInches(3.0), PptInches(4.8), PptInches(1.55), RGBColor(20, 31, 47))
    caveat = slide.shapes.add_textbox(PptInches(8.35), PptInches(3.16), PptInches(4.25), PptInches(1.16))
    caveat.text_frame.text = "Validation failures caught:\nport collision | partial tree | cached partial result | Python env | missing shards"
    for p in caveat.text_frame.paragraphs:
        p.font.size = PptPt(14)
        p.font.bold = True
        p.font.color.rgb = RGBColor(245, 248, 255)

    box(PptInches(8.05), PptInches(4.85), PptInches(4.8), PptInches(1.05), RGBColor(20, 31, 47))
    topo = slide.shapes.add_textbox(PptInches(8.35), PptInches(5.0), PptInches(4.25), PptInches(0.7))
    topo.text_frame.text = "client -> A -> B,H,G,I\nB -> C,D,E    E -> F"
    for p in topo.text_frame.paragraphs:
        p.font.size = PptPt(15)
        p.font.color.rgb = RGBColor(220, 230, 242)

    footer = slide.shapes.add_textbox(PptInches(0.55), PptInches(6.82), PptInches(12.2), PptInches(0.3))
    footer.text_frame.text = "Tradeoff: fewer round trips, larger buffers. Final two-computer run: 30 runs per chunk size."
    footer.text_frame.paragraphs[0].font.size = PptPt(11)
    footer.text_frame.paragraphs[0].font.color.rgb = RGBColor(166, 178, 196)

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
