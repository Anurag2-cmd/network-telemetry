from pptx import Presentation
from pptx.util import Inches, Pt
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.enum.shapes import MSO_SHAPE

NAVY = RGBColor(0x1F, 0x38, 0x64)
ACCENT = RGBColor(0x2E, 0x74, 0xB5)
LIGHT = RGBColor(0xDE, 0xEA, 0xF6)
GRAY = RGBColor(0x33, 0x33, 0x33)
MIDGRAY = RGBColor(0x66, 0x66, 0x66)
CODEBG = RGBColor(0xF2, 0xF2, 0xF2)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)

BODY = "Calibri"
MONO = "Consolas"

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def style_run(run, size=16, bold=False, color=GRAY, font=BODY, italic=False):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.italic = italic
    run.font.color.rgb = color
    run.font.name = font


def add_box(slide, left, top, width, height):
    tb = slide.shapes.add_textbox(left, top, width, height)
    tf = tb.text_frame
    tf.word_wrap = True
    tf.margin_left = 0
    tf.margin_right = 0
    tf.margin_top = 0
    tf.margin_bottom = 0
    return tb, tf


def add_footer(slide, num):
    _, tf = add_box(slide, Inches(0.6), Inches(7.08), Inches(9), Inches(0.3))
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = "Network Telemetry — Major Project Synopsis"
    style_run(r, 10, color=MIDGRAY)
    _, tf2 = add_box(slide, Inches(12.2), Inches(7.08), Inches(0.6), Inches(0.3))
    p2 = tf2.paragraphs[0]
    p2.alignment = PP_ALIGN.RIGHT
    r2 = p2.add_run()
    r2.text = str(num)
    style_run(r2, 10, color=MIDGRAY)


def add_title(slide, kicker, title):
    _, tf = add_box(slide, Inches(0.6), Inches(0.42), Inches(12.1), Inches(0.4))
    p = tf.paragraphs[0]
    r = p.add_run()
    r.text = kicker
    style_run(r, 12, bold=True, color=ACCENT)
    _, tf2 = add_box(slide, Inches(0.6), Inches(0.82), Inches(12.1), Inches(0.9))
    p2 = tf2.paragraphs[0]
    r2 = p2.add_run()
    r2.text = title
    style_run(r2, 30, bold=True, color=NAVY)
    bar = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, Inches(0.62), Inches(1.62), Inches(1.4), Inches(0.045)
    )
    bar.fill.solid()
    bar.fill.fore_color.rgb = ACCENT
    bar.line.fill.background()
    bar.shadow.inherit = False


def add_bullets(slide, items, left=Inches(0.6), top=Inches(1.95),
                width=Inches(12.1), height=Inches(4.9), size=16, gap=8):
    _, tf = add_box(slide, left, top, width, height)
    first = True
    for item in items:
        level = item.get("level", 0)
        text = item.get("text", "")
        bold = item.get("bold", False)
        color = item.get("color", GRAY)
        italic = item.get("italic", False)
        mono = item.get("mono", False)
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.level = level
        p.space_after = Pt(item.get("gap", gap))
        p.line_spacing = 1.08
        prefix = "\u2022  " if level == 0 else "\u2013  "
        r = p.add_run()
        r.text = prefix
        style_run(r, size if level == 0 else size - 1, bold=bold,
                  color=ACCENT if level == 0 else MIDGRAY)
        r2 = p.add_run()
        r2.text = text
        style_run(r2, size if level == 0 else size - 1, bold=bold, color=color,
                  font=MONO if mono else BODY, italic=italic)


def add_code(slide, lines, left=Inches(0.6), top=Inches(1.95),
             width=Inches(12.1), height=None):
    if height is None:
        height = Inches(0.32 * len(lines) + 0.3)
    box = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, left, top, width, height
    )
    box.fill.solid()
    box.fill.fore_color.rgb = CODEBG
    box.line.color.rgb = RGBColor(0xCC, 0xCC, 0xCC)
    box.line.width = Pt(0.75)
    box.shadow.inherit = False
    tf = box.text_frame
    tf.word_wrap = True
    tf.margin_left = Inches(0.18)
    tf.margin_right = Inches(0.18)
    tf.margin_top = Inches(0.1)
    tf.margin_bottom = Inches(0.1)
    tf.vertical_anchor = MSO_ANCHOR.TOP
    first = True
    for ln in lines:
        p = tf.paragraphs[0] if first else tf.add_paragraph()
        first = False
        p.space_after = Pt(1)
        r = p.add_run()
        r.text = ln
        style_run(r, 12, color=NAVY, font=MONO)


def add_table(slide, headers, rows, left=Inches(0.6), top=Inches(1.95),
              width=Inches(12.1), col_widths=None, font_size=13,
              header_size=13):
    n_rows = len(rows) + 1
    n_cols = len(headers)
    tbl_shape = slide.shapes.add_table(n_rows, n_cols, left, top, width,
                                       Inches(0.34 * n_rows + 0.12))
    tbl = tbl_shape.table
    tbl.first_row = False
    tbl.horz_banding = False
    if col_widths:
        total = sum(col_widths)
        for i, w in enumerate(col_widths):
            tbl.columns[i].width = int(width * w / total)
    for c, h in enumerate(headers):
        cell = tbl.cell(0, c)
        cell.fill.solid()
        cell.fill.fore_color.rgb = NAVY
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        p = cell.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = h
        style_run(r, header_size, bold=True, color=WHITE)
    for ri, row in enumerate(rows):
        for ci, val in enumerate(row):
            cell = tbl.cell(ri + 1, ci)
            cell.fill.solid()
            cell.fill.fore_color.rgb = LIGHT if ri % 2 == 0 else WHITE
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            tf = cell.text_frame
            tf.word_wrap = True
            p = tf.paragraphs[0]
            r = p.add_run()
            r.text = val
            style_run(r, font_size, bold=(ci == 0), color=GRAY)


def new_slide(num):
    slide = prs.slides.add_slide(BLANK)
    add_footer(slide, num)
    return slide


def title_slide():
    slide = prs.slides.add_slide(BLANK)
    band = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, 0, prs.slide_width, Inches(0.18)
    )
    band.fill.solid()
    band.fill.fore_color.rgb = NAVY
    band.line.fill.background()
    band.shadow.inherit = False
    band2 = slide.shapes.add_shape(
        MSO_SHAPE.RECTANGLE, 0, Inches(7.32), prs.slide_width, Inches(0.18)
    )
    band2.fill.solid()
    band2.fill.fore_color.rgb = ACCENT
    band2.line.fill.background()
    band2.shadow.inherit = False
    _, tf = add_box(slide, Inches(1.0), Inches(1.9), Inches(11.3), Inches(2.2))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "MAJOR PROJECT SYNOPSIS"
    style_run(r, 18, bold=True, color=ACCENT)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    p2.space_before = Pt(10)
    r2 = p2.add_run()
    r2.text = "NETWORK TELEMETRY"
    style_run(r2, 44, bold=True, color=NAVY)
    p3 = tf.add_paragraph()
    p3.alignment = PP_ALIGN.CENTER
    p3.space_before = Pt(6)
    r3 = p3.add_run()
    r3.text = "A Six-Protocol Emulated Monitoring Stack — SNMP, NetFlow v5, sFlow, IPFIX, gNMI, INT"
    style_run(r3, 18, color=GRAY)
    _, tf2 = add_box(slide, Inches(1.0), Inches(4.55), Inches(11.3), Inches(2.2))
    p4 = tf2.paragraphs[0]
    p4.alignment = PP_ALIGN.CENTER
    r4 = p4.add_run()
    r4.text = "Master of Computer Applications (AI & DS)"
    style_run(r4, 16, color=GRAY)
    p5 = tf2.add_paragraph()
    p5.alignment = PP_ALIGN.CENTER
    p5.space_before = Pt(4)
    r5 = p5.add_run()
    r5.text = "Department of Computer Science and Engineering, School of Engineering and Technology"
    style_run(r5, 13, color=MIDGRAY)
    p6 = tf2.add_paragraph()
    p6.alignment = PP_ALIGN.CENTER
    p6.space_before = Pt(10)
    r6 = p6.add_run()
    r6.text = "By: Anurag Ramola (2501560023)"
    style_run(r6, 15, bold=True, color=NAVY)
    p7 = tf2.add_paragraph()
    p7.alignment = PP_ALIGN.CENTER
    p7.space_before = Pt(2)
    r7 = p7.add_run()
    r7.text = "Projexa Team ID: 2604057"
    style_run(r7, 13, color=GRAY)
    p8 = tf2.add_paragraph()
    p8.alignment = PP_ALIGN.CENTER
    p8.space_before = Pt(2)
    r8 = p8.add_run()
    r8.text = "Under the supervision of Mr. Amit Kumar Singh"
    style_run(r8, 13, color=GRAY)
    p9 = tf2.add_paragraph()
    p9.alignment = PP_ALIGN.CENTER
    p9.space_before = Pt(2)
    r9 = p9.add_run()
    r9.text = "K.R Mangalam University, Gurugram — August 2026"
    style_run(r9, 13, color=MIDGRAY)


def s_overview():
    s = new_slide(1)
    add_title(s, "SECTION 01", "Project Overview")
    add_bullets(s, [
        {"text": "A complete, runnable miniature of modern network telemetry: an emulated network "
                 "(Mininet + P4/BMv2 + Open vSwitch) exports six telemetry technologies — SNMP, NetFlow v5, "
                 "sFlow, IPFIX, gNMI and In-band Network Telemetry (INT)."},
        {"text": "All six protocols are funneled into a single SQLite database and visualized on a real-time "
                 "Flask dashboard — one tab per protocol, side by side on the same traffic and timeline."},
        {"text": "Covers all four generations of telemetry evolution: pull-based SNMP (G1), flow-based "
                 "NetFlow/sFlow/IPFIX (G2), streaming model-driven gNMI over gRPC (G3), and in-band INT with "
                 "P4 (G4) — where each switch stamps packets in flight with switch ID, ingress timestamp and "
                 "egress queue depth."},
        {"text": "Proven with real measured data: a 1000-packet microburst builds a queue 43–45 packets deep "
                 "on switch 2 in under a second — invisible to a 5 s SNMP poll, recorded packet-by-packet by "
                 "INT with ~22 ms per-hop queueing delay."},
    ], top=Inches(1.95), height=Inches(4.5), size=16)
    add_bullets(s, [
        {"text": "KEYWORDS:  Network Telemetry · SNMP · NetFlow · sFlow · IPFIX · gNMI · INT · P4 · Mininet · SDN",
         "bold": True, "color": ACCENT},
    ], top=Inches(6.45), height=Inches(0.5), size=13)


def s_objectives():
    s = new_slide(2)
    add_title(s, "SECTION 02", "Specific Objectives")
    add_bullets(s, [
        {"text": "Design and build an emulated network (Mininet + P4/BMv2 + Open vSwitch) serving as a realistic "
                 "telemetry data source for six protocols: SNMP, NetFlow v5, sFlow, IPFIX, gNMI and INT."},
        {"text": "Write a P4-16 INT program (compiled with p4c for BMv2) that stamps every packet with a per-hop "
                 "metadata entry — switch ID, ingress timestamp, egress queue depth (enq_qdepth) — with zero "
                 "additional monitoring traffic."},
        {"text": "Implement Python collectors for each protocol — UDP collectors (sFlow 6343, NetFlow v5 9995, "
                 "IPFIX 9996), an SNMPv2c poller (5 s), a pygnmi pull client (2 s), and a scapy INT receiver "
                 "computing per-hop latency and jitter — all storing into one shared SQLite database (WAL mode)."},
        {"text": "Build a real-time Flask dashboard with a tab per protocol, live green/red liveness badges "
                 "(24 h liveness window) and 5 s auto-refreshing Chart.js graphs, reachable at localhost:5000."},
        {"text": "Run an end-to-end test (one command: run_all.sh) proving every one of the six database tables "
                 "receives live data, and demonstrate a microburst that SNMP cannot see but INT records "
                 "packet-by-packet (queue depth 43–45, ~22 ms queueing delay)."},
    ], top=Inches(1.95), height=Inches(4.9), size=15, gap=11)


def s_key_features():
    s = new_slide(3)
    add_title(s, "SECTION 03", "Key Features")
    add_bullets(s, [
        {"text": "Six protocols in one environment — SNMP, NetFlow v5, sFlow, IPFIX, gNMI and INT compared on "
                 "the same traffic, same timeline, one dashboard."},
        {"text": "Per-hop visibility via P4 INT — every packet stamped in flight with {switch_id, ingress_ts, "
                 "enq_qdepth}; zero additional monitoring traffic."},
        {"text": "One shared SQLite database (WAL mode) with six tables — int_hops, sflow_samples, "
                 "netflow_flows, ipfix_flows, snmp_stats, gnmi_stats."},
        {"text": "Real-time Flask dashboard — one tab per protocol, live liveness badges (24 h liveness window), "
                 "5 s auto-refresh with Chart.js."},
        {"text": "Microburst evidence — queue spike to depth 43–45 and ~22 ms queueing delay, recorded "
                 "packet-by-packet where SNMP polling sees nothing."},
        {"text": "One-command end-to-end run — sudo bash run_all.sh executes the full stack and asserts all "
                 "six tables are non-empty."},
        {"text": "Every collector ships a --selftest mode — parsing and DB writes verified without Mininet."},
    ], top=Inches(1.95), height=Inches(4.9), size=15.5, gap=10)


def s_usecases():
    s = new_slide(4)
    add_title(s, "SECTION 04", "Project Usecases & Scope")
    add_table(s, ["Usecase", "How this project addresses it"],
              [
                  ["Cloud data centers", "Fine-grained feedback for load balancing and loss detection — INT queue depth per hop"],
                  ["SDN control plane", "Live data-plane state (counters, queue occupancy) to drive control decisions"],
                  ["5G / 6G & edge", "Sub-second visibility into queueing for strict latency budgets (URLLC)"],
                  ["IoT / large fleets", "Low-overhead streaming status collection for millions of devices"],
                  ["Teaching & research", "All four telemetry generations studied and compared on one reproducible lab"],
              ],
              top=Inches(1.9), width=Inches(12.1), col_widths=[3.2, 8.9], font_size=13)
    add_bullets(s, [
        {"text": "Scope", "bold": True, "color": NAVY},
        {"text": "Emulated environment (Mininet + P4/BMv2 + OVS on a single laptop) — ideal for teaching, "
                 "demonstration and protocol comparison; speeds, queue depths and latencies are emulation "
                 "artifacts, not production numbers.", "level": 1},
        {"text": "Out of scope: production deployment, hardware switches, large-scale traffic volumes.",
         "level": 1},
    ], top=Inches(4.85), height=Inches(2.0), size=14)


def s_architecture():
    s = new_slide(5)
    add_title(s, "SECTION 05", "Prototype / Project Flow / Architecture")
    add_code(s, [
        "         +-------- emulated network (Mininet, WSL) --------+",
        " INT     |  h1 -- s1 (P4) -- s2 (P4) -- h2                |",
        " path    |                                          h3    |",
        "         |                                          h4    |",
        "         +-----------------------------------------------+",
        "",
        " INT:     h1 --int_sender--> P4 switches add metadata --> int_receiver on h2",
        " sFlow:   OVS s1 samples every pkt --> 127.0.0.1:6343 --> sflow_collector",
        " NetFlow: softflowd(h1, v5) --> h4:9995 --------------> netflow_collector",
        " IPFIX:   softflowd(h3, v10) --> h4:9996 -------------> ipfix_collector",
        " SNMP:    snmpd(h4, agent) <-- 5 s poll <-- snmp_poller (root netns)",
        " gNMI:    gnmi_agent (emulated svc over P4Runtime counters) <-- 2 s <-- gnmi_client",
        "",
        "                    all -> db/telemetry.db (SQLite, WAL) -> dashboard/app.py",
        "                                                -> http://localhost:5000",
    ], top=Inches(1.85), width=Inches(12.1), height=Inches(4.45))
    _, tf = add_box(s, Inches(0.6), Inches(6.45), Inches(12.1), Inches(0.5))
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    r = p.add_run()
    r.text = "Project flow:  Traffic → Exporters (P4 switches / OVS / softflowd / snmpd / gNMI) → Collectors → SQLite → Dashboard → Operator"
    style_run(r, 14, bold=True, color=NAVY)
    p2 = tf.add_paragraph()
    p2.alignment = PP_ALIGN.CENTER
    p2.space_before = Pt(4)
    r2 = p2.add_run()
    r2.text = "Figure 1: Architectural diagram — six protocol paths, one shared database, one dashboard."
    style_run(r2, 12, italic=True, color=MIDGRAY)


def s_data_resources():
    s = new_slide(6)
    add_title(s, "SECTION 06", "Data & Resources")
    add_table(s, ["Resource", "Role in the project"],
              [
                  ["Python 3", "All collectors, pollers, P4 control helpers and the dashboard"],
                  ["P4-16 + p4c (1.2.5.15)", "Language + compiler for the INT data plane (int.p4 → int.json)"],
                  ["BMv2 1.15.4", "simple_switch runs INT switches; simple_switch_grpc adds P4Runtime (gNMI source)"],
                  ["Mininet", "Emulates hosts and switches (h1–h4, s1–s2)"],
                  ["Open vSwitch", "sFlow exporter (sampling=1, counter polls)"],
                  ["softflowd / snmpd", "NetFlow v5 (h1) + IPFIX v10 (h3) exporters; SNMP agent in h4"],
                  ["scapy / pysnmp", "INT packet sniffing & parsing; SNMPv2c polling"],
                  ["pygnmi + gRPC", "Emulated gNMI service and its pull client"],
                  ["Flask + Chart.js + SQLite (WAL)", "Dashboard backend/frontend; single shared DB"],
                  ["tcpdump, iperf3", "Capture FIFO for softflowd; traffic generation"],
                  ["Windows 11 + WSL2 (Ubuntu)", "Host environment — everything runs in WSL"],
              ],
              top=Inches(1.85), width=Inches(12.1), col_widths=[4.2, 7.9], font_size=11)
    add_bullets(s, [
        {"text": "Data: six protocol tables — int_hops (per-hop latency, jitter, queue occupancy) · "
                 "sflow_samples (5-tuples, counters, bandwidth) · netflow_flows & ipfix_flows (flow records) · "
                 "snmp_stats (CPU, memory, octets) · gnmi_stats (OpenConfig leaves).", "bold": True, "color": NAVY},
    ], top=Inches(6.15), height=Inches(0.8), size=12.5)


def s_methodology():
    s = new_slide(7)
    add_title(s, "SECTION 07", "Methodology")
    add_bullets(s, [
        {"text": "INT data plane (P4)", "bold": True},
        {"text": "p4/int.p4 (P4-16 v1model): sender emits UDP/4000 packets with an INT header; each switch "
                 "appends a 12-byte stack entry {switch_id, ingress_ts, enq_qdepth} in the egress pipeline; "
                 "receiver calibrates boot offset (BMv2 clocks unsynchronized) and computes per-hop latency/jitter.", "level": 1},
        {"text": "Collectors & database", "bold": True},
        {"text": "UDP collectors (sFlow 6343, NetFlow v5 9995, IPFIX 9996 with dynamic templates incl. IPv6), "
                 "SNMPv2c poller (5 s), pygnmi pull (2 s), scapy INT receiver — all writing db/telemetry.db "
                 "(SQLite, WAL, 24 h cleanup) via db/telemetry.py.", "level": 1},
        {"text": "Dashboard", "bold": True},
        {"text": "/api/<source> returns last 200 rows; /api/status liveness badges (60 s); six tabs, "
                 "5 s auto-refresh, Chart.js.", "level": 1},
        {"text": "End-to-end verification", "bold": True},
        {"text": "run_all.sh runs INT demo → sFlow/NetFlow/IPFIX → SNMP → gNMI → dashboard, asserting every "
                 "table is non-empty; each collector also has a --selftest mode.", "level": 1},
    ], top=Inches(1.9), height=Inches(5.0), size=14.5)


def s_results():
    s = new_slide(8)
    add_title(s, "SECTION 08", "Expected Results & Impact")
    add_code(s, [
        "int_hops       460        sflow_samples  375251",
        "netflow_flows  6          ipfix_flows    11",
        "snmp_stats     10         gnmi_stats     540",
        "ALL 6 TABLES NON-EMPTY: PASS",
    ], top=Inches(1.85), width=Inches(12.1), height=Inches(1.45))
    add_bullets(s, [
        {"text": "Microburst detected: queue depth 43–45, ~22 ms per-hop queueing delay — recorded "
                 "packet-by-packet by INT while 5 s SNMP polling stays blind.", "bold": True, "color": NAVY},
        {"text": "Dashboard live at localhost:5000 — six tabs, liveness badges green while collectors write rows."},
        {"text": "Impact", "bold": True},
        {"text": "Demonstrates with real data why streaming and in-band telemetry outperform traditional "
                 "polling for transient events — the pull-vs-push argument, proven rather than asserted.", "level": 1},
        {"text": "Provides a unified, reproducible framework to study and compare all four generations of "
                 "telemetry — a teaching and research tool, not just a demo.", "level": 1},
    ], top=Inches(3.5), height=Inches(3.3), size=14.5)


def s_timeline():
    s = new_slide(9)
    add_title(s, "SECTION 09", "Project Timeline")
    add_table(s, ["Phase", "Period", "Key milestones"],
              [
                  ["1 · Literature review & gap analysis", "Week 1–2",
                   "RFC 1157/3954/7011/3176, INT spec, P4/Mininet research; problem statement"],
                  ["2 · Environment setup", "Week 3–4",
                   "WSL2 + Ubuntu; build p4c and BMv2 (tasks 01–02); Mininet, OVS, softflowd, snmpd"],
                  ["3 · Core implementation", "Week 5–8",
                   "P4 INT data plane (03) → Mininet topology (04) → INT receiver (05) → sFlow (06) → "
                   "NetFlow/IPFIX (07) → SNMP (08) → gNMI (09) → dashboard (10)"],
                  ["4 · End-to-end integration & verification", "Week 9–10",
                   "run_all.sh E2E runner; all six tables verified non-empty; microburst demo (task 11)"],
                  ["5 · Documentation & presentation", "Week 11–12",
                   "Written report (task 12), synopsis, defense presentation"],
              ],
              top=Inches(1.9), width=Inches(12.1), col_widths=[3.6, 1.4, 7.1], font_size=12.5)
    add_bullets(s, [
        {"text": "Status: implementation and E2E verification complete — all tasks 01–12 done; "
                 "this synopsis covers the finished project.", "bold": True, "color": ACCENT},
    ], top=Inches(6.0), height=Inches(0.9), size=14)


title_slide()
s_overview()
s_objectives()
s_key_features()
s_usecases()
s_architecture()
s_data_resources()
s_methodology()
s_results()
s_timeline()

OUT = "Network_Telemetry_PPT_v2.pptx"
prs.save(OUT)
print(f"Saved {OUT} with {len(prs.slides._sldIdLst)} slides")