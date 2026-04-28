#pragma once
#include <string>

// --- Phase 9: Mirai-Inspired Scanner Module ---
// Lateral movement: scan local network for open ports and services

// Scan a single host on a specific port (TCP connect). Returns true if open.
bool scan_port(const std::string& host, int port, int timeout_ms = 1000);

// Scan a /24 subnet for open ports. Returns formatted results.
// Example: scan_subnet("192.168.1", "22,23,80,445,3389")
std::string scan_subnet(const std::string& subnet_prefix, const std::string& ports_csv);

// Quick LAN discovery — auto-detect local subnet and scan common ports
std::string scan_lan();
