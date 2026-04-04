#pragma once
#include <string>
#include <vector>
#include <utility>

// --- String Helpers ---
std::wstring to_wide(const std::string& s);
std::string  to_narrow(const std::wstring& ws);
std::string  to_lower(const std::string& s);

// --- JSON Helpers (minimal, no external lib) ---
std::string json_get(const std::string& json, const std::string& key);
std::string json_escape(const std::string& s);
std::vector<std::pair<std::string,std::string>> json_parse_tasks(const std::string& json);

// --- System Info ---
std::string get_os_info();

// --- Logging (only prints when TEST_MODE is true) ---
void log_msg(const std::string& msg);
