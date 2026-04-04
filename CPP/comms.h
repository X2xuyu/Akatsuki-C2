#pragma once
#include <string>

// --- HTTP Client using WinHTTP ---
std::string http_post_json(const std::string& path, const std::string& json_body);
std::string http_get(const std::string& path);

// --- Discord Webhook ---
bool discord_send(const std::string& text_content);
bool discord_upload_file(const std::string& filepath, const std::string& message);
