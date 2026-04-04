#include "shell.h"
#include "utils.h"
#include <windows.h>
#include <cstdio>

Shell::Shell() {
    char buf[MAX_PATH];
    GetCurrentDirectoryA(MAX_PATH, buf);
    cwd = buf;
}

std::string Shell::execute(const std::string& command) {
    // Handle 'cd' specially (change working directory)
    std::string cmd_lower = to_lower(command);
    if (cmd_lower.substr(0, 3) == "cd " || cmd_lower.substr(0, 3) == "cd\t") {
        std::string target = command.substr(3);
        // Trim whitespace
        size_t start = target.find_first_not_of(" \t");
        if (start != std::string::npos) target = target.substr(start);
        size_t end = target.find_last_not_of(" \t\r\n");
        if (end != std::string::npos) target = target.substr(0, end + 1);
        
        // Resolve relative paths
        char resolved[MAX_PATH];
        if (SetCurrentDirectoryA(target.c_str())) {
            GetCurrentDirectoryA(MAX_PATH, resolved);
            cwd = resolved;
            return "Changed directory to: " + cwd;
        } else {
            // Try from current cwd
            std::string full = cwd + "\\" + target;
            if (SetCurrentDirectoryA(full.c_str())) {
                GetCurrentDirectoryA(MAX_PATH, resolved);
                cwd = resolved;
                return "Changed directory to: " + cwd;
            }
            return "cd: No such directory: " + target;
        }
    }
    
    // Set working directory before executing
    SetCurrentDirectoryA(cwd.c_str());
    
    // Build command: cmd.exe /c "command"
    std::string full_cmd = "cmd.exe /c " + command;
    
    // Create pipes for stdout/stderr
    SECURITY_ATTRIBUTES sa = { sizeof(sa), nullptr, TRUE };
    HANDLE hReadPipe, hWritePipe;
    if (!CreatePipe(&hReadPipe, &hWritePipe, &sa, 0)) {
        return "Error: Failed to create pipe.";
    }
    SetHandleInformation(hReadPipe, HANDLE_FLAG_INHERIT, 0);
    
    // Create process
    STARTUPINFOA si = {};
    si.cb = sizeof(si);
    si.dwFlags = STARTF_USESTDHANDLES | STARTF_USESHOWWINDOW;
    si.hStdOutput = hWritePipe;
    si.hStdError = hWritePipe;
    si.wShowWindow = SW_HIDE;
    
    PROCESS_INFORMATION pi = {};
    
    if (!CreateProcessA(nullptr, (LPSTR)full_cmd.c_str(), nullptr, nullptr,
                        TRUE, CREATE_NO_WINDOW, nullptr, cwd.c_str(), &si, &pi)) {
        CloseHandle(hReadPipe);
        CloseHandle(hWritePipe);
        return "Error: Failed to execute command.";
    }
    
    CloseHandle(hWritePipe); // Close write end in parent
    
    // Read output
    std::string output;
    char buf[4096];
    DWORD bytesRead;
    while (ReadFile(hReadPipe, buf, sizeof(buf) - 1, &bytesRead, nullptr) && bytesRead > 0) {
        buf[bytesRead] = '\0';
        output += buf;
    }
    
    WaitForSingleObject(pi.hProcess, 30000); // 30s timeout
    
    CloseHandle(hReadPipe);
    CloseHandle(pi.hProcess);
    CloseHandle(pi.hThread);
    
    // Trim trailing whitespace
    while (!output.empty() && (output.back() == '\n' || output.back() == '\r' || output.back() == ' '))
        output.pop_back();
    
    return output.empty() ? "(no output)" : output;
}
