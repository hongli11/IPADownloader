# IPADownloader

**让下载 iOS IPA 变得更加方便** — 命令行 + 桌面 GUI 双模式。

感谢大神：[majd/ipatool](https://github.com/majd/ipatool)

![icon](icon_0.jpg)

---

## 安装

只需一步（安装 `ipatool`）：

```bash
# macOS
brew install majd/repo/ipatool

# Linux (Ubuntu/Debian) — 下载预编译二进制
# 见下方 Linux 安装说明
```

或执行：

```bash
chmod +x setup.sh && ./setup.sh
```

---

## 使用方式

### 🖥️ 桌面 GUI（推荐）

```bash
python3 ipadownloader.py
```

功能：
- 🔍 搜索 App（关键词搜索，50条结果）
- 📱 列表展示搜索结果
- ⬇️ 双击或选中后一键下载
- 🔑 图形界面登录 Apple ID
- 📂 自定义下载目录

首次使用需登录 Apple ID（窗口左下角按钮）。

---

### 🖥️ 命令行模式

```bash
# 登录
ipatool auth login --email xxx --password xxx

# 搜索
ipatool search "关键词"

# 下载
ipatool download -b com.example.app
```

或使用包装脚本：

```bash
chmod +x downloader.sh
./downloader.sh
```

---

## 登录 Apple ID

- 使用 GUI：点击左下角 **"🔑 登录 Apple ID"** 按钮
- 使用 CLI：`ipatool auth login --email xxx --password xxx`

如果密码被拒绝，请在你的 iOS 设备上登录一次该 App，然后再试。

---

## 常见问题

**下载失败：license is required**

```
ERR error="license is required"
```

解决方法：在 iPhone 上用该 Apple ID 在 App Store 点一下下载（不用下载完，点一下就行），然后再次用工具下载。

**搜不到想要的 App**

修改搜索数量（默认 50 条），或换个关键词。

**Linux 下缺少 tkinter**

```bash
sudo apt install python3-tk
```

---

## License

MIT
