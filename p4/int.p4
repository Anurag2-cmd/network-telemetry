/* P4-16 INT program for BMv2 (v1model).
 *
 * INT over UDP mode:
 * - The sender (h1) sends UDP packets to dst port 4000 whose payload begins
 *   with an INT header (count=0, length=0). See tools/int_sender.py.
 * - Every switch on the path appends one 12-byte INT metadata stack entry
 *   (in the egress pipeline, where BMv2's enq_qdepth is readable):
 *   {switch_id, ingress_ts, enq_qdepth, padding} and bumps
 *   count/length, ipv4.totalLen, udp.length, disables the UDP checksum.
 * - The receiver (h2) sniffs udp/4000 and parses the INT stack
 *   (see tools/int_receiver.py).
 */

#include <core.p4>
#include <v1model.p4>

const bit<16> INT_UDP_PORT = 4000;
const bit<8>   MAX_HOPS    = 4;

/* ---- headers ---- */
header ethernet_t {
    bit<48> dstAddr;
    bit<48> srcAddr;
    bit<16> etherType;
}

header ipv4_t {
    bit<4>  version;
    bit<4>  ihl;
    bit<8>  diffserv;
    bit<16> totalLen;
    bit<16> identification;
    bit<3>  flags;
    bit<13> fragOffset;
    bit<8>  ttl;
    bit<8>  protocol;
    bit<16> hdrChecksum;
    bit<32> srcAddr;
    bit<32> dstAddr;
}

header udp_t {
    bit<16> srcPort;
    bit<16> dstPort;
    bit<16> length;
    bit<16> checksum;
}

/* INT v0.5 base header (32 bits). Sender initializes count=0, length=0. */
header int_header_t {
    bit<4> ver;
    bit<2> rep;
    bit<1> c;
    bit<1> reserved1;
    bit<8> count;
    bit<8> length;
    bit<8> ins;
}

/* One 12-byte stack entry appended by each INT-capable switch:
 * {switch_id, ingress_ts, enq_qdepth, padding}. ingress_ts is the
 * switch's ingress_global_timestamp in µs (BMv2: per-switch clock
 * since switch start — clocks are NOT synchronized, so the receiver
 * calibrates the constant offset from the first packet's deltas). */
header int_metadata_t {
    bit<32> switch_id;
    bit<32> ingress_ts;
    bit<16> enq_qdepth;
    bit<16> padding;
}

struct headers_t {
    ethernet_t      ethernet;
    ipv4_t          ipv4;
    udp_t           udp;
    int_header_t    int_hdr;
    int_metadata_t  int_meta[MAX_HOPS];
}

struct metadata_t {
    bit<32> swid;
    bit<8>  remain;
}

/* Per-port traffic counters (index = port). The gNMI agent (task 09)
   maps these onto OpenConfig interface counters: port_counters_in is
   indexed by ingress_port (packets received on the port), port_counters_out
   by egress_port (packets forwarded out of the port). */
counter(1024, CounterType.packets_and_bytes) port_counters_in;
counter(1024, CounterType.packets_and_bytes) port_counters_out;

/* ---- parser ---- */
parser MyParser(packet_in b, out headers_t hdr, inout metadata_t meta,
                inout standard_metadata_t sm) {
    state start {
        b.extract(hdr.ethernet);
        transition select(hdr.ethernet.etherType) {
            0x0800: parse_ipv4;
            default: accept;
        }
    }
    state parse_ipv4 {
        b.extract(hdr.ipv4);
        transition select(hdr.ipv4.protocol) {
            17: parse_udp;
            default: accept;
        }
    }
    state parse_udp {
        b.extract(hdr.udp);
        transition select(hdr.udp.dstPort) {
            INT_UDP_PORT: parse_int;
            default: accept;
        }
    }
    state parse_int {
        b.extract(hdr.int_hdr);
        meta.remain = hdr.int_hdr.count;
        transition select(meta.remain) {
            0: accept;
            default: parse_int_meta;
        }
    }
    /* parse exactly `count` stack entries; BMv2 drops packets whose
       parser extracts past the end of the buffer */
    state parse_int_meta {
        b.extract(hdr.int_meta.next);
        meta.remain = meta.remain - 1;
        transition select(meta.remain) {
            0: accept;
            default: parse_int_meta;
        }
    }
}

/* ---- deparser ---- */
control MyDeparser(packet_out b, in headers_t hdr) {
    apply {
        b.emit(hdr.ethernet);
        b.emit(hdr.ipv4);
        b.emit(hdr.udp);
        b.emit(hdr.int_hdr);
        b.emit(hdr.int_meta);
    }
}

/* ---- checksum verification/update ---- */
control MyVerifyChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply { }
}

control MyUpdateChecksum(inout headers_t hdr, inout metadata_t meta) {
    apply {
        update_checksum(
            hdr.ipv4.isValid(),
            { hdr.ipv4.version, hdr.ipv4.ihl, hdr.ipv4.diffserv,
              hdr.ipv4.totalLen, hdr.ipv4.identification, hdr.ipv4.flags,
              hdr.ipv4.fragOffset, hdr.ipv4.ttl, hdr.ipv4.protocol,
              hdr.ipv4.srcAddr, hdr.ipv4.dstAddr },
            hdr.ipv4.hdrChecksum,
            HashAlgorithm.csum16);
    }
}

/* ---- ingress ---- */
control MyIngress(inout headers_t hdr, inout metadata_t meta,
                  inout standard_metadata_t sm) {
    action set_swid(bit<32> swid) {
        meta.swid = swid;
    }
    table swid_table {
        key = { sm.ingress_port: exact; }
        actions = { set_swid; NoAction; }
        default_action = NoAction;
    }

    action set_egress_port(bit<9> port) {
        sm.egress_spec = port;
    }
    table ipv4_lpm {
        key = { hdr.ipv4.dstAddr: lpm; }
        actions = { set_egress_port; NoAction; }
        default_action = NoAction;
    }

    apply {
        swid_table.apply();
        if (hdr.ipv4.isValid()) {
            ipv4_lpm.apply();
            port_counters_in.count((bit<32>)sm.ingress_port);
        }
    }
}

/* ---- egress ---- */
control MyEgress(inout headers_t hdr, inout metadata_t meta,
                 inout standard_metadata_t sm) {
    /* INT metadata insertion must run in egress: BMv2 populates
       standard_metadata.enq_qdepth only at enqueue time (after the
       ingress pipeline), so it is readable in the egress pipeline. */
    action add_int_metadata() {
        bit<8> idx = hdr.int_hdr.count;
        if (idx < MAX_HOPS) {
            hdr.int_meta[idx].setValid();
            hdr.int_meta[idx].switch_id  = meta.swid;
            hdr.int_meta[idx].ingress_ts = (bit<32>)sm.ingress_global_timestamp;
            hdr.int_meta[idx].enq_qdepth = (bit<16>)sm.enq_qdepth;
            hdr.int_meta[idx].padding    = 0;
            hdr.int_hdr.count  = (bit<8>)(idx + 1);
            hdr.int_hdr.length = (bit<8>)(hdr.int_hdr.length + 12);
            hdr.ipv4.totalLen  = hdr.ipv4.totalLen + 12;
            hdr.udp.length     = hdr.udp.length + 12;
            /* payload+length changed; recompute not expressible over
               the wire bytes in v1model, so disable the UDP checksum
               (legal for IPv4: checksum 0 = no checksum) */
            hdr.udp.checksum   = 0;
        }
    }
    table int_table {
        key = { hdr.udp.dstPort: exact; }
        actions = { add_int_metadata; NoAction; }
        default_action = NoAction;
    }

    apply {
        port_counters_out.count((bit<32>)sm.egress_port);
        if (hdr.udp.isValid() && hdr.int_hdr.isValid()) {
            int_table.apply();
        }
    }
}

V1Switch(MyParser(), MyVerifyChecksum(), MyIngress(), MyEgress(),
         MyUpdateChecksum(), MyDeparser()) main;
