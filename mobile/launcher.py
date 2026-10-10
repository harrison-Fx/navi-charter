"""Kuching Trip Advisor - phone app launcher.

One window to get the Expo app onto your phone:
  1. checks Node.js, the app's packages and the tunnel helper (installs them if missing)
  2. lets you pick how the phone connects: same Wi-Fi, or a tunnel that works on any network
  3. starts the app server and shows the QR code to scan with Expo Go

Run with OPEN-LAUNCHER.bat (Windows) or:  python launcher.py
Needs: Python 3.9+, customtkinter, qrcode, pillow (the .bat installs them).
"""
import json
import os
import platform
import queue
import re
import shutil
import socket
import subprocess
import threading
import time
import tkinter as tk

import customtkinter as ctk
import qrcode
from PIL import Image

APP_DIR = os.path.dirname(os.path.abspath(__file__))
IS_WIN = platform.system() == "Windows"
NO_WINDOW = 0x08000000 if IS_WIN else 0
EXPO_GO_URL = "https://play.google.com/store/apps/details?id=host.exp.exponent"
ANSI = re.compile(r"\x1b\[[0-9;?]*[ -/]*[@-~]")
VIRTUAL = re.compile(r"vEthernet|WSL|VirtualBox|VMware|Hyper-V|Loopback|Bluetooth|Tailscale|ZeroTier|VPN|TAP", re.I)

ACCENT = ("#2B5FAD", "#78A6EC")
OK = ("#2E7D4F", "#6FCB94")
WARN = ("#B35A00", "#F0A050")
BAD = ("#B03030", "#F07B7B")
MUTED = ("#5B6058", "#A3AA9F")


# ---------------------------------------------------------------- system helpers
def refresh_path():
    """Pick up PATH changes (e.g. right after installing Node.js) without restarting."""
    if not IS_WIN:
        return
    try:
        import winreg
        parts = []
        for root, key in ((winreg.HKEY_LOCAL_MACHINE, r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
                          (winreg.HKEY_CURRENT_USER, r"Environment")):
            try:
                with winreg.OpenKey(root, key) as k:
                    parts.append(os.path.expandvars(winreg.QueryValueEx(k, "Path")[0]))
            except OSError:
                pass
        if parts:
            os.environ["PATH"] = ";".join(parts + [os.environ.get("PATH", "")])
    except Exception:
        pass


def cmd(args):
    """npm/npx are .cmd files on Windows; run them through cmd /c."""
    return (["cmd", "/c"] + args) if IS_WIN else args


def quick(args, timeout=20):
    try:
        r = subprocess.run(cmd(args), capture_output=True, text=True, timeout=timeout, cwd=APP_DIR, creationflags=NO_WINDOW)
        return r.returncode, (r.stdout or "").strip()
    except Exception as e:
        return 1, str(e)


def lan_addresses():
    """[(ip, label)] with the address used for the internet first."""
    primary = None
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))  # no packet is sent; just asks which interface would be used
        primary = s.getsockname()[0]
        s.close()
    except Exception:
        pass
    found = []
    if IS_WIN:
        try:
            out = subprocess.run(["ipconfig"], capture_output=True, text=True, creationflags=NO_WINDOW).stdout
            adapter = ""
            for line in out.splitlines():
                if line and not line.startswith(" "):
                    adapter = line.strip().rstrip(":")
                m = re.search(r"IPv4[^:]*:\s*([\d.]+)", line)
                if m:
                    found.append((m.group(1), adapter))
        except Exception:
            pass
    if primary and primary not in [ip for ip, _ in found]:
        found.insert(0, (primary, "used for internet"))
    found = [(ip, lab) for ip, lab in found if not ip.startswith(("127.", "169.254."))]
    found.sort(key=lambda x: (x[0] != primary, bool(VIRTUAL.search(x[1]))))
    return [(ip, f"{ip}  ({lab}{', probably not your Wi-Fi' if VIRTUAL.search(lab) else ''})") for ip, lab in found] or [("127.0.0.1", "127.0.0.1 (no network found)")]


def packages_ok():
    """Every dependency in package.json has a folder in node_modules (catches newly added ones)."""
    try:
        with open(os.path.join(APP_DIR, "package.json")) as f:
            deps = json.load(f).get("dependencies", {})
        return all(os.path.isdir(os.path.join(APP_DIR, "node_modules", *d.split("/"))) for d in deps)
    except Exception:
        return False


def port_free(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def kill_tree(proc):
    if not proc or proc.poll() is not None:
        return
    try:
        if IS_WIN:
            subprocess.run(["taskkill", "/T", "/F", "/PID", str(proc.pid)], capture_output=True, creationflags=NO_WINDOW)
        else:
            os.killpg(os.getpgid(proc.pid), 15)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass


def qr_image(text, size):
    q = qrcode.QRCode(border=2, box_size=10, error_correction=qrcode.constants.ERROR_CORRECT_M)
    q.add_data(text)
    q.make(fit=True)
    img = q.make_image(fill_color="black", back_color="white").convert("RGB")
    return ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))


# ---------------------------------------------------------------- window
class Launcher(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("system")
        self.title("Kuching Trip Advisor - phone app launcher")
        self.geometry("1000x800")
        self.minsize(900, 760)
        self.q = queue.Queue()
        self.proc = None
        self.busy = False
        self.mode = tk.StringVar(value="Same Wi-Fi")
        self.url = None
        self.hostname = None
        self.port = 8081
        self.ngrok_ok = None
        self.addresses = lan_addresses()

        self.grid_columnconfigure(0, weight=1, uniform="c")
        self.grid_columnconfigure(1, weight=1, uniform="c")
        self.grid_rowconfigure(1, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, columnspan=2, sticky="ew", padx=20, pady=(16, 6))
        ctk.CTkLabel(head, text="Kuching Trip Advisor", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w")
        ctk.CTkLabel(head, text="Get the app onto your phone: check, pick a connection, start, scan.", text_color=MUTED).pack(anchor="w")

        left = ctk.CTkFrame(self)
        left.grid(row=1, column=0, sticky="nsew", padx=(20, 10), pady=6)
        right = ctk.CTkFrame(self)
        right.grid(row=1, column=1, sticky="nsew", padx=(10, 20), pady=6)

        # 1. checks
        ctk.CTkLabel(left, text="1  Get ready", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(14, 6))
        self.rows = {}
        for key, label in (("node", "Node.js"), ("pkgs", "App packages"), ("ngrok", "Tunnel helper")):
            r = ctk.CTkFrame(left, fg_color="transparent")
            r.pack(fill="x", padx=16, pady=3)
            ctk.CTkLabel(r, text=label, width=130, anchor="w").pack(side="left")
            st = ctk.CTkLabel(r, text="checking…", text_color=MUTED, anchor="w")
            st.pack(side="left", fill="x", expand=True)
            b = ctk.CTkButton(r, text="Install", width=90, command=lambda k=key: self.install(k))
            b.pack(side="right")
            self.rows[key] = (st, b)

        # 2. connection
        ctk.CTkLabel(left, text="2  How should your phone connect?", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(18, 6))
        self.seg = ctk.CTkSegmentedButton(left, values=["Same Wi-Fi", "Tunnel (any network)"], variable=self.mode, command=lambda _v: self.on_mode())
        self.seg.pack(fill="x", padx=16)
        self.wifi_box = ctk.CTkFrame(left, fg_color="transparent")
        self.wifi_box.pack(fill="x", padx=16, pady=(8, 0))
        ctk.CTkLabel(self.wifi_box, text="This PC's address on your Wi-Fi", text_color=MUTED).pack(anchor="w")
        self.ip_menu = ctk.CTkOptionMenu(self.wifi_box, values=[lab for _, lab in self.addresses])
        self.ip_menu.pack(fill="x", pady=(2, 0))
        self.mode_hint = ctk.CTkLabel(left, text="", text_color=MUTED, wraplength=400, justify="left")
        self.mode_hint.pack(anchor="w", padx=16, pady=(6, 0))

        # 3. start
        ctk.CTkLabel(left, text="3  Start", font=ctk.CTkFont(size=16, weight="bold")).pack(anchor="w", padx=16, pady=(18, 6))
        br = ctk.CTkFrame(left, fg_color="transparent")
        br.pack(fill="x", padx=16)
        self.start_btn = ctk.CTkButton(br, text="Start app", height=44, font=ctk.CTkFont(size=16, weight="bold"), command=self.start)
        self.start_btn.pack(side="left", fill="x", expand=True)
        self.stop_btn = ctk.CTkButton(br, text="Stop", height=44, width=90, fg_color="transparent", border_width=2, text_color=ACCENT, command=self.stop, state="disabled")
        self.stop_btn.pack(side="left", padx=(8, 0))
        ctk.CTkButton(left, text="Build an installable APK (Expo cloud, free account)", fg_color="transparent", border_width=2, text_color=ACCENT, command=self.build_apk).pack(fill="x", padx=16, pady=(10, 0))
        if IS_WIN:
            ctk.CTkButton(left, text="Phone can't connect on Wi-Fi? Allow it through Windows Firewall", fg_color="transparent", text_color=ACCENT, hover=False, anchor="w", command=self.firewall).pack(fill="x", padx=8, pady=(8, 0))

        # QR side
        self.status = ctk.CTkLabel(right, text="Don't have Expo Go yet? Scan this with your phone camera to get it.", font=ctk.CTkFont(size=15, weight="bold"), wraplength=400, justify="left")
        self.status.pack(anchor="w", padx=16, pady=(14, 6))
        self.blank = ctk.CTkImage(light_image=Image.new("RGBA", (1, 1), (0, 0, 0, 0)), size=(1, 1))
        self.qr_img = qr_image(EXPO_GO_URL, 240)
        self.qr = ctk.CTkLabel(right, text="", image=self.qr_img)
        self.qr.pack(pady=6)
        self.url_lbl = ctk.CTkLabel(right, text="", text_color=MUTED, font=ctk.CTkFont(family="Consolas" if IS_WIN else "monospace", size=13))
        self.url_lbl.pack()
        rr = ctk.CTkFrame(right, fg_color="transparent")
        rr.pack(pady=4)
        self.copy_btn = ctk.CTkButton(rr, text="Copy link", width=110, command=self.copy, state="disabled")
        self.copy_btn.pack(side="left", padx=4)
        self.switch_btn = ctk.CTkButton(rr, text="Phone says 'Failed to download'? Use tunnel", fg_color="transparent", border_width=2, text_color=ACCENT, command=self.switch_to_tunnel)
        self.steps = ctk.CTkLabel(right, text="On your phone: open Expo Go → Scan QR code.\nThe first load takes up to a minute.", text_color=MUTED, justify="left", wraplength=400)
        self.steps.pack(anchor="w", padx=16, pady=(6, 10))

        # log
        logf = ctk.CTkFrame(self)
        logf.grid(row=2, column=0, columnspan=2, sticky="nsew", padx=20, pady=(6, 16))
        ctk.CTkLabel(logf, text="Details", text_color=MUTED).pack(anchor="w", padx=12, pady=(6, 0))
        self.log = ctk.CTkTextbox(logf, height=100, font=ctk.CTkFont(family="Consolas" if IS_WIN else "monospace", size=12))
        self.log.pack(fill="both", expand=True, padx=8, pady=(2, 8))

        self.on_mode()
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.pump)
        threading.Thread(target=self.check_all, daemon=True).start()

    # ---------------------------------------------------------------- checks
    def set_row(self, key, ok, text, can_install=True):
        st, b = self.rows[key]
        st.configure(text=("✓ " if ok else "✗ ") + text, text_color=OK if ok else (WARN if key == "ngrok" else BAD))
        b.configure(state="disabled" if ok or not can_install or self.busy else "normal", text="Done" if ok else "Install")

    def check_all(self):
        refresh_path()
        node = shutil.which("node")
        if node:
            _, v = quick(["node", "-v"])
            self.q.put(("row", "node", True, f"found {v}"))
        else:
            self.q.put(("row", "node", False, "not installed"))
        has_pkgs = packages_ok()
        self.q.put(("row", "pkgs", has_pkgs, "installed" if has_pkgs else "missing or out of date", bool(node)))
        if node:
            # Expo looks for the tunnel helper in the project first; that copy is the reliable one.
            self.ngrok_ok = os.path.isfile(os.path.join(APP_DIR, "node_modules", "@expo", "ngrok", "package.json"))
            self.q.put(("row", "ngrok", self.ngrok_ok, "installed" if self.ngrok_ok else "not installed (optional)", True))
        else:
            self.q.put(("row", "ngrok", False, "needs Node.js first", False))
        self.q.put(("ready",))

    def install(self, key):
        if self.busy:
            return
        if key == "node":
            if not IS_WIN:
                self.say("Install Node.js 20 or newer from nodejs.org, then press Check again.")
                return
            self.say("Installing Node.js with winget. Windows may ask for permission.")
            self.run_task(["winget", "install", "-e", "--id", "OpenJS.NodeJS.LTS", "--accept-source-agreements", "--accept-package-agreements"], "Node.js installed.", raw=True)
        elif key == "pkgs":
            self.run_task(["npm", "install", "--no-audit", "--no-fund"], "App packages installed.")
        elif key == "ngrok":
            self.run_task(["npm", "install", "--no-audit", "--no-fund", "@expo/ngrok@^4.1.0"], "Tunnel helper installed.")

    def run_task(self, args, done_msg, raw=False):
        self.busy = True
        self.start_btn.configure(state="disabled")
        for st, b in self.rows.values():
            b.configure(state="disabled")
        self.write(f"\n> {' '.join(args)}\n")

        def work():
            try:
                p = subprocess.Popen(args if raw else cmd(args), cwd=APP_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", creationflags=NO_WINDOW)
                for line in p.stdout:
                    self.q.put(("log", line))
                code = p.wait()
                self.q.put(("log", (done_msg if code == 0 else f"That step failed (code {code}). Check your internet connection and try again.") + "\n"))
            except FileNotFoundError:
                self.q.put(("log", "Couldn't run that command. Is it installed?\n"))
            self.q.put(("taskdone",))
        threading.Thread(target=work, daemon=True).start()

    # ---------------------------------------------------------------- start / stop
    def on_mode(self):
        wifi = self.mode.get() == "Same Wi-Fi"
        if wifi:
            self.wifi_box.pack(fill="x", padx=16, pady=(8, 0), after=self.seg)
            self.mode_hint.configure(text="Fastest. Your phone and this PC must be on the same Wi-Fi (a phone hotspot works too). Campus and hotel Wi-Fi often block this; use the tunnel there.")
        else:
            self.wifi_box.pack_forget()
            self.mode_hint.configure(text="Works on any network, including mobile data. A bit slower to start. Needs the tunnel helper (step 1).")

    def chosen_ip(self):
        lab = self.ip_menu.get()
        for ip, l in self.addresses:
            if l == lab:
                return ip
        return self.addresses[0][0]

    def start(self):
        if self.proc or self.busy:
            return
        tunnel = self.mode.get() != "Same Wi-Fi"
        if not shutil.which("node"):
            self.say("Install Node.js first (step 1).")
            return
        if not packages_ok():
            self.say("Install the app packages first (step 1).")
            return
        if tunnel and not self.ngrok_ok:
            self.say("Install the tunnel helper first (step 1), or use Same Wi-Fi.")
            return
        self.port = next((p for p in range(8081, 8091) if port_free(p)), 8081)
        env = dict(os.environ, CI="1", EXPO_NO_TELEMETRY="1", FORCE_COLOR="0")
        args = ["npx", "expo", "start", "--port", str(self.port)]
        if tunnel:
            args.append("--tunnel")
            env["DEBUG"] = "expo:start:server:ngrok"  # prints the tunnel hostname
        else:
            env["REACT_NATIVE_PACKAGER_HOSTNAME"] = self.chosen_ip()
        self.url = None
        self.hostname = None
        self.tunnel = tunnel
        self.write(f"\n> {' '.join(args)}\n")
        kw = dict(cwd=APP_DIR, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
        if IS_WIN:
            kw["creationflags"] = NO_WINDOW
        else:
            kw["start_new_session"] = True
        try:
            self.proc = subprocess.Popen(cmd(args), **kw)
        except Exception as e:
            self.say(f"Couldn't start: {e}")
            return
        self.start_btn.configure(state="disabled", text="Running…")
        self.stop_btn.configure(state="normal")
        self.seg.configure(state="disabled")
        self.show_status("Starting the app server…" + (" Connecting the tunnel can take 20–40 seconds." if tunnel else ""), MUTED)
        self.qr.configure(image=self.blank, text="⏳", font=ctk.CTkFont(size=40))
        self.url_lbl.configure(text="")
        self.copy_btn.configure(state="disabled")
        self.switch_btn.pack_forget()
        p = self.proc

        def read():
            for line in p.stdout:
                self.q.put(("srv", line))
            self.q.put(("exited", p))
        threading.Thread(target=read, daemon=True).start()

    def stop(self):
        kill_tree(self.proc)
        self.proc = None
        self.reset_idle("Stopped.")

    def switch_to_tunnel(self):
        self.stop()
        self.mode.set("Tunnel (any network)")
        self.on_mode()
        if self.ngrok_ok:
            self.start()
        else:
            self.say("Installing the tunnel helper first…")
            self.install("ngrok")
            self.pending_tunnel = True

    def reset_idle(self, msg):
        self.start_btn.configure(state="normal", text="Start app")
        self.stop_btn.configure(state="disabled")
        self.seg.configure(state="normal")
        self.show_status(msg, MUTED)

    def on_server_line(self, line):
        clean = ANSI.sub("", line).rstrip()
        if not clean:
            return
        self.write(clean + "\n")
        m = re.search(r"Hostname:\s*([\w.-]+\.exp\.direct)", clean)
        if m:
            self.hostname = m.group(1)
        if self.tunnel:
            if "Tunnel ready" in clean:
                host = self.hostname or self.guess_tunnel_host()
                if host:
                    self.ready(f"exp://{host}")
                else:
                    self.show_status("Tunnel is up but the address wasn't found. Look for exp:// in Details.", WARN)
            elif "CommandError" in clean or "NGROK_" in clean or "Tunnel connection has been closed" in clean:
                self.show_status("The tunnel couldn't connect. Press Stop and try again in a minute, or use a phone hotspot with Same Wi-Fi.", BAD)
        else:
            if "Waiting on http" in clean or "Logs for your project" in clean:
                self.ready(f"exp://{self.chosen_ip()}:{self.port}")
        if "port" in clean.lower() and "in use" in clean.lower():
            self.show_status("The app server's port is busy. Close other Expo windows and press Start again.", BAD)

    def guess_tunnel_host(self):
        """Expo names the tunnel <randomness>-<expo user or 'anonymous'>-<port>.exp.direct."""
        try:
            with open(os.path.join(APP_DIR, ".expo", "settings.json")) as f:
                rnd = json.load(f).get("urlRandomness")
            return f"{rnd}-anonymous-{self.port}.exp.direct" if rnd else None
        except Exception:
            return None

    def ready(self, url):
        if self.url == url:
            return
        self.url = url
        self.qr_img = qr_image(url, 260)  # keep a reference so Tk doesn't drop the image
        self.qr.configure(image=self.qr_img, text="")
        self.url_lbl.configure(text=url)
        self.copy_btn.configure(state="normal")
        self.show_status("Ready. Open Expo Go on your phone and scan this code.", OK)
        if not self.tunnel:
            self.switch_btn.pack(side="left", padx=4)

    # ---------------------------------------------------------------- misc
    def firewall(self):
        ps = ("Start-Process netsh -Verb RunAs -ArgumentList 'advfirewall firewall add rule name=\"Kuching Trip Advisor (Expo)\" "
              "dir=in action=allow protocol=TCP localport=8081-8090 profile=private,public'")
        try:
            subprocess.Popen(["powershell", "-NoProfile", "-Command", ps], creationflags=NO_WINDOW)
            self.say("Windows will ask for permission to add a firewall rule for ports 8081–8090. After that, press Start again.")
        except Exception as e:
            self.say(f"Couldn't open the firewall prompt: {e}")

    def build_apk(self):
        """Opens its own window, because signing in to Expo asks for your email and password."""
        bat = os.path.join(APP_DIR, "BUILD-APK.bat")
        try:
            if IS_WIN:
                subprocess.Popen(["cmd", "/c", "start", "", bat], cwd=APP_DIR)
            else:
                self.say("Run: npx eas-cli@latest build -p android --profile preview")
                return
            self.say("A new window opened for the APK build. Sign in to Expo there; the build takes about 10–20 minutes.")
        except Exception as e:
            self.say(f"Couldn't open the build window: {e}")

    def copy(self):
        if self.url:
            self.clipboard_clear()
            self.clipboard_append(self.url)
            self.say("Link copied. In Expo Go you can also paste it under 'Enter URL manually'.")

    def show_status(self, text, color):
        self.status.configure(text=text, text_color=color)

    def say(self, text):
        self.write(text + "\n")
        self.show_status(text, WARN)

    def write(self, text):
        self.log.insert("end", text)
        self.log.see("end")

    def pump(self):
        try:
            while True:
                msg = self.q.get_nowait()
                kind = msg[0]
                if kind == "row":
                    self.set_row(msg[1], msg[2], msg[3], *(msg[4:] or (True,)))
                elif kind == "ready":
                    pass
                elif kind == "start":
                    self.start()
                elif kind == "log":
                    self.write(ANSI.sub("", msg[1]))
                elif kind == "taskdone":
                    self.busy = False
                    self.start_btn.configure(state="normal")
                    threading.Thread(target=self.after_task, daemon=True).start()
                elif kind == "srv":
                    self.on_server_line(msg[1])
                elif kind == "exited":
                    if msg[1] is self.proc:
                        self.proc = None
                        self.reset_idle("The app server stopped. See Details below, then press Start again.")
                        self.qr.configure(image=self.blank, text="")
        except queue.Empty:
            pass
        self.after(100, self.pump)

    def after_task(self):  # runs in a worker thread; talk to the window only through the queue
        self.check_all()
        if getattr(self, "pending_tunnel", False) and self.ngrok_ok:
            self.pending_tunnel = False
            self.q.put(("start",))

    def on_close(self):
        kill_tree(self.proc)
        self.destroy()


if __name__ == "__main__":
    Launcher().mainloop()
