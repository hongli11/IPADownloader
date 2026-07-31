#!/usr/bin/env python3
"""
IPADownloader — iOS App (ipa) Desktop GUI
调用 ipatool CLI 实现搜索、登录、下载，带图形界面，双击即用。
"""

import subprocess
import json
import os
import sys
import threading
import tempfile
import shutil

try:
    from tkinter import Tk, Label, Entry, Button, Listbox, Scrollbar, Frame, StringVar, IntVar, Toplevel, messagebox, filedialog
    from tkinter import font as tkfont
    TK_OK = True
except ImportError:
    TK_OK = False
    print("❌ 缺少 tkinter，请安装：sudo apt install python3-tk", file=sys.stderr)
    sys.exit(1)

# ── 配置 ──────────────────────────────────────────────
IPA_TOOL = "/usr/local/bin/ipatool"
DEFAULT_DOWNLOAD_DIR = os.path.expanduser("~/Downloads/IPADownloader")
REPO_DIR = os.path.dirname(os.path.abspath(__file__))
ICON_PATH = os.path.join(REPO_DIR, "icon_0.jpg")
MAX_SEARCH = 50
CMD_TIMEOUT = 180

# ── 颜色主题 ──────────────────────────────────────────
BG        = "#1a1a2e"
SURFACE   = "#16213e"
INPUT_BG  = "#0f3460"
ACCENT    = "#00b4d8"
ACCENT_DK = "#0077b6"
GREEN     = "#06d6a0"
RED       = "#ef476f"
YELLOW    = "#ffd166"
WHITE     = "#f0f0f0"
GREY      = "#888"
FONT_NAME = "Microsoft YaHei UI" if sys.platform == "win32" else "Noto Sans CJK SC"
FALLBACK  = "DejaVu Sans"

# ── 工具函数 ──────────────────────────────────────────

import re as _re
_ANSI = _re.compile(r"\x1b\[[0-9;]*[mK]")

def _strip_ansi(s: str) -> str:
    return _re.sub(r"\x1b\[[0-9;]*[mK]", "", s)


def _ensure_keyring() -> None:
    """启动 GNOME keyring，让 ipatool 有地方存凭证"""
    try:
        import subprocess as _sub
        if _sub.run(["pgrep", "-f", "gnome-keyring-daemon"],
                    capture_output=True).returncode != 0:
            _sub.run(["gnome-keyring-daemon", "--unlock",
                      "-p", "ipadownloader"],
                     capture_output=True, timeout=10)
    except Exception:
        pass  # keyring 失败也继续

def run_cmd(cmd: list[str], timeout: int = CMD_TIMEOUT) -> tuple[str, str, int]:
    """执行命令，返回 (stdout, stderr, returncode)，自动去 ANSI 转义"""
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout,
            env={**os.environ, "LC_ALL": "zh_CN.UTF-8"},
        )
        return _strip_ansi(r.stdout), _strip_ansi(r.stderr), r.returncode
    except subprocess.TimeoutExpired:
        return "", f"命令执行超时 ({timeout}s)", -1
    except FileNotFoundError:
        return "", f"未找到命令: {cmd[0]}", -2
    except Exception as e:
        return "", str(e), -3


def check_ipatool() -> tuple[bool, str]:
    """检查 ipatool 是否可用，返回 (available, version_text)"""
    out, err, code = run_cmd([IPA_TOOL, "--version"])
    if code == 0:
        return True, out.strip()
    # 尝试常见路径
    for path in ["/opt/homebrew/bin/ipatool", "/homebrew/bin/ipatool",
                 shutil.which("ipatool")]:
        if path and os.path.isfile(path):
            out2, err2, code2 = run_cmd([path, "--version"])
            if code2 == 0:
                return True, out2.strip()
    return False, ""


def parse_search_results(text: str) -> list[tuple[str, str, str]]:
    """
    解析 ipatool search 输出，返回 [(name, bundle_id, subtitle), ...]
    """
    results = []
    try:
        # 新 ipatool 返回 JSON
        data = json.loads(text)
        for app in data:
            name = app.get("name", "")
            bundle = app.get("bundleIdentifier", "")
            subtitle = app.get("subtitle", "")
            if name and bundle:
                results.append((name, bundle, subtitle))
        return results
    except json.JSONDecodeError:
        # 老版本文本格式
        lines = text.strip().split("\n")
        for line in lines:
            # 格式: "Name  | Bundle ID"
            parts = line.split("|")
            if len(parts) >= 2:
                name = parts[0].strip()
                bundle = parts[1].strip()
                if name and bundle:
                    results.append((name, bundle, ""))
        return results


def search_apps(query: str) -> tuple[list[tuple[str, str, str]], str]:
    out, err, code = run_cmd([IPA_TOOL, "search", "--limit", str(MAX_SEARCH), query])
    if code != 0:
        return [], err.strip() or out.strip() or "未知错误"
    results = parse_search_results(out)
    if not results:
        return [], "未找到结果"
    return results, ""


def download_app(bundle_id: str, dest_dir: str) -> tuple[str, str]:
    """下载 ipa，返回 (result_msg, error_msg)"""
    os.makedirs(dest_dir, exist_ok=True)
    out, err, code = run_cmd([IPA_TOOL, "download", "-b", bundle_id, "--output", dest_dir])
    if code == 0:
        return "下载成功", ""
    return "", err.strip() or out.strip()


def login_apple(email: str, password: str, auth_code: str = "") -> tuple[bool, str]:
    """登录 Apple ID，先启动 gnome-keyring 以兼容 ipatool 存凭证"""
    _ensure_keyring()
    cmd = [IPA_TOOL, "auth", "login",
           "--email", email, "--password", password,
           "--keychain-passphrase", "ipadownloader"]
    if auth_code:
        cmd.extend(["--auth-code", auth_code])
    out, err, code = run_cmd(cmd)
    if code == 0:
        return True, out.strip() or "登录成功"
    run_cmd([IPA_TOOL, "auth", "revoke"], timeout=30)
    return False, err.strip() or out.strip()


def logout_apple() -> tuple[bool, str]:
    out, err, code = run_cmd([IPA_TOOL, "auth", "logout"])
    if code == 0:
        return True, "已登出"
    return False, err.strip()


def check_auth() -> tuple[bool, str]:
    out, err, code = run_cmd([IPA_TOOL, "auth", "status"])
    if code == 0 and "authenticated" in out.lower():
        return True, out.strip()
    return False, out.strip() or err.strip()


# ── 主窗口 ─────────────────────────────────────────────

class MainApp(Tk):
    def __init__(self):
        super().__init__()
        self.title("IPADownloader")
        self.geometry("720x560")
        self.minsize(600, 400)
        self.configure(bg=BG)

        self.download_dir = DEFAULT_DOWNLOAD_DIR
        self.authenticated = False
        self.auth_name = ""
        self._stop_thread = False
        self._results: list[tuple[str, str, str]] = []

        self._build_ui()
        self._check_status()

        # 让图标显示（jpg）
        try:
            img = PhotoImage(file=ICON_PATH)
            self.iconphoto(True, img)
        except Exception:
            pass

    # ── 布局 ───────────────────────────────────────────

    def _build_ui(self):
        self._make_font()

        # === 顶部状态栏 ===
        status_bar = Frame(self, bg=SURFACE, padx=12, pady=6)
        status_bar.pack(fill="x")

        Label(status_bar, text="📱 IPADownloader", font=self.F16_B, fg=ACCENT, bg=SURFACE).pack(side="left")
        self.auth_label = Label(status_bar, text="⚠️  请先登录 Apple ID", font=self.F10, fg=YELLOW, bg=SURFACE)
        self.auth_label.pack(side="left", padx=10)

        self.status_var = StringVar(value="就绪")
        self.status_lbl = Label(status_bar, textvariable=self.status_var, font=self.F10, fg=GREY, bg=SURFACE)
        self.status_lbl.pack(side="right")

        # === 搜索区 ===
        search_f = Frame(self, bg=BG, padx=15, pady=8)
        search_f.pack(fill="x")

        self.query_var = StringVar()
        self.entry = Entry(search_f, textvariable=self.query_var,
                           font=self.F12, bg=INPUT_BG, fg=WHITE,
                           insertbackground=ACCENT, relief="flat")
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self.entry.bind("<Return>", lambda e: self._do_search())
        self.entry.insert(0, "输入关键词搜索...")
        self.entry.bind("<FocusIn>", lambda e: self.entry.delete(0, "end") if self.entry.get() == "输入关键词搜索..." else None)

        Button(search_f, text="🔍", command=self._do_search,
               font=("Arial", 16), bg=ACCENT, fg="white",
               activebackground=ACCENT_DK, relief="flat", padx=12).pack(side="left")

        Button(search_f, text="⬇️ 下载选中", command=self._do_download,
               font=self.F11, bg=GREEN, fg="white",
               activebackground="#05a77a", relief="flat", padx=10).pack(side="left", padx=(8, 0))

        # === 结果列表 ===
        list_f = Frame(self, bg=SURFACE, padx=10, pady=8)
        list_f.pack(fill="both", expand=True, padx=15, pady=5)

        self.lb = Listbox(list_f, font=self.F10, bg=BG, fg=WHITE,
                          selectbackground=ACCENT, selectforeground="white",
                          activestyle="none", relief="flat",
                          exportselection=False)
        lb_scroll = Scrollbar(list_f, orient="vertical", command=self.lb.yview, bg=SURFACE, troughcolor=SURFACE)
        lb_scroll.pack(side="right", fill="y")
        self.lb.configure(yscrollcommand=lb_scroll.set)
        self.lb.pack(side="left", fill="both", expand=True)
        self.lb.bind("<Double-Button-1>", lambda e: self._do_download())

        # === 底部 ===
        bottom = Frame(self, bg=BG, padx=15, pady=8)
        bottom.pack(fill="x")

        self.download_path_var = StringVar(value=self.download_dir)
        Label(bottom, text="📂 下载目录:", font=self.F10, fg=GREY, bg=BG).pack(side="left")
        Entry(bottom, textvariable=self.download_path_var, font=self.F10,
              bg=INPUT_BG, fg=WHITE, relief="flat", width=40).pack(side="left", padx=5, fill="x", expand=True)
        Button(bottom, text="... ", command=self._choose_dir,
               font=self.F10, bg=SURFACE, fg=WHITE, relief="flat").pack(side="left")

        Button(bottom, text="🔑 登录 Apple ID", command=self._login_dialog,
               font=self.F10, bg=SURFACE, fg=WHITE, relief="flat").pack(side="right")
        Button(bottom, text="↻ 检查状态", command=self._check_status,
               font=self.F10, bg=SURFACE, fg=WHITE, relief="flat").pack(side="right", padx=(0, 8))

    # ── 字体 ───────────────────────────────────────────

    def _make_font(self):
        f = tkfont.Font(family=FONT_NAME, size=10)
        try:
            f.actual()
        except Exception:
            f = tkfont.Font(family=FALLBACK, size=10)
        self.F10 = tkfont.Font(family=f.cget("family"), size=10)
        self.F11 = tkfont.Font(family=f.cget("family"), size=11)
        self.F12 = tkfont.Font(family=f.cget("family"), size=12)
        self.F14 = tkfont.Font(family=f.cget("family"), size=14)
        self.F16_B = tkfont.Font(family=f.cget("family"), size=14, weight="bold")
        self.F14_B = tkfont.Font(family=f.cget("family"), size=12, weight="bold")

    # ── 操作 ───────────────────────────────────────────

    def _set_status(self, msg: str):
        self.status_var.set(msg)
        self.update()

    def _check_status(self):
        self._set_status("检查中...")
        avail, ver = check_ipatool()
        if not avail:
            self.auth_label.configure(text="❌ ipatool 未安装", fg=RED)
            self._set_status("请先执行 setup.sh 或 brew install ipatool")
            return
        self.auth_label.configure(text=f"✓ ipatool {ver[:30]}", fg=GREEN)
        self.authenticated, msg = check_auth()
        if self.authenticated:
            self.auth_label.configure(text=f"✓ 已登录 Apple ID", fg=GREEN)
        else:
            self.auth_label.configure(text="⚠️  请先登录 Apple ID", fg=YELLOW)
        self._set_status("就绪")

    def _do_search(self):
        if not self.authenticated:
            messagebox.showwarning("提示", "请先登录 Apple ID")
            return
        q = self.query_var.get().strip()
        if not q:
            return
        self._set_status(f"搜索 '{q}' ...")
        threading.Thread(target=lambda: self._search_bg(q), daemon=True).start()

    def _search_bg(self, q: str):
        results, err = search_apps(q)
        self.after(0, lambda: self._search_done(results, err))

    def _search_done(self, results: list, err: str):
        self.lb.delete(0, "end")
        self._results = []
        if err:
            self._set_status(f"搜索失败: {err[:40]}")
            return
        for name, bundle, subtitle in results:
            display = f"{name}"
            if subtitle:
                display += f"  — {subtitle}"
            self.lb.insert("end", display)
            self._results.append((name, bundle, subtitle))
        self._set_status(f"找到 {len(results)} 个结果")

    def _do_download(self):
        if not self.authenticated:
            messagebox.showwarning("提示", "请先登录 Apple ID")
            return
        sel = self.lb.curselection()
        if not sel:
            self._set_status("请先从列表中选中一个 App")
            return
        idx = sel[0]
        name, bundle, _ = self._results[idx]
        dest = self.download_path_var.get().strip()
        if not dest:
            dest = self.download_dir

        self._set_status(f"正在下载 {name} ...")
        threading.Thread(target=lambda: self._download_bg(name, bundle, dest), daemon=True).start()

    def _download_bg(self, name: str, bundle: str, dest: str):
        result, err = download_app(bundle, dest)
        self.after(0, lambda: self._download_done(name, result, err))

    def _download_done(self, name: str, result: str, err: str):
        if result:
            self._set_status(f"✅ {name} 下载完成")
            messagebox.showinfo("下载完成", f"已保存到:\n{self.download_path_var.get()}")
        else:
            self._set_status(f"❌ 下载失败")
            messagebox.showerror("下载失败", err[:200])

    def _choose_dir(self):
        d = filedialog.askdirectory(title="选择下载目录")
        if d:
            self.download_path_var.set(d)
            self.download_dir = d

    def _login_dialog(self):
        self._set_status("打开登录窗口...")
        LoginDialog(self)


# ── 登录弹窗 ───────────────────────────────────────────

class LoginDialog(Toplevel):
    def __init__(self, parent: MainApp):
        super().__init__()
        self.parent = parent
        self.title("登录 Apple ID")
        self.geometry("400x240")
        self.resizable(False, False)
        self.configure(bg=BG)
        self.transient(parent)
        self.grab_set()

        self._result: tuple[bool, str] | None = None

        self._build()

        Label(self, text="🔑 Apple ID 登录", font=("Microsoft YaHei UI", 14),
              fg=ACCENT, bg=BG).pack(pady=12)

        Label(self, text="Email", font=parent.F11, fg=WHITE, bg=BG).pack(anchor="w", padx=20)
        self.email_var = StringVar()
        Entry(self, textvariable=self.email_var, font=parent.F11,
              bg=INPUT_BG, fg=WHITE, relief="flat", width=35).pack(padx=20, pady=3)

        Label(self, text="Password", font=parent.F11, fg=WHITE, bg=BG).pack(anchor="w", padx=20, pady=(8, 0))
        self.pwd_var = StringVar()
        Entry(self, textvariable=self.pwd_var, font=parent.F11,
              bg=INPUT_BG, fg=WHITE, show="●", relief="flat", width=35).pack(padx=20, pady=3)

        Button(self, text="登录", command=self._submit,
               font=parent.F11, bg=ACCENT, fg="white", relief="flat").pack(pady=12)

        self.protocol("WM_DELETE_WINDOW", self._close)

    def _build(self):
        pass

    def _submit(self):
        email = self.email_var.get().strip()
        pwd = self.pwd_var.get()
        if not email or not pwd:
            messagebox.showwarning("提示", "请填写 Email 和密码")
            return
        self._email = email
        self._pwd = pwd
        threading.Thread(target=lambda: self._login_bg(email, pwd), daemon=True).start()

    def _login_bg(self, email: str, pwd: str, code: str = ""):
        ok, msg = login_apple(email, pwd, code)
        self.after(0, lambda: self._login_done(ok, msg))

    def _login_done(self, ok: bool, msg: str):
        if ok:
            self.parent.authenticated = True
            self.parent.auth_name = msg
            self.parent.auth_label.configure(text="✓ 已登录 Apple ID", fg=GREEN)
            self.parent._set_status("登录成功")
            self._result = (True, msg)
            self._close()
        elif "2FA" in msg or "auth code" in msg.lower() or "enter 2FA" in msg.lower():
            self._ask_2fa()
        else:
            self._result = (False, msg)
            messagebox.showerror("登录失败", msg[:200])

    def _ask_2fa(self):
        v = Toplevel(self)
        v.title("2FA 验证码")
        v.geometry("360x180")
        v.resizable(False, False)
        v.configure(bg=BG)
        v.transient(self)
        v.grab_set()

        Label(v, text="需要双重认证验证码", font=("Microsoft YaHei UI", 12),
              fg=ACCENT, bg=BG).pack(pady=10)
        Label(v, text="请在手机/受信任设备上查看 6 位验证码",
              font=self.parent.F11, fg=WHITE, bg=BG).pack(pady=2)
        cvar = StringVar()
        Entry(v, textvariable=cvar, font=self.parent.F11,
              bg=INPUT_BG, fg=WHITE, show="●", relief="flat", width=18).pack(pady=6)

        def _go():
            code = cvar.get().strip()
            if not code:
                return
            v.destroy()
            threading.Thread(
                target=lambda: self._login_bg(self._email, self._pwd, code), daemon=True).start()

        Button(v, text="验证", command=_go,
               font=self.parent.F11, bg=ACCENT, fg="white", relief="flat").pack(pady=8)

    def _close(self):
        self.destroy()
        # 登录完成后自动关闭窗口，主窗口会显示成功


# ── 入口 ───────────────────────────────────────────────

if __name__ == "__main__":
    MainApp().mainloop()
