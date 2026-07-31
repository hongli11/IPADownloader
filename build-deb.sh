#!/usr/bin/env bash
# build-deb.sh — 打包 IPADownloader 为 .deb 安装文件
set -euo pipefail

PKG="ipadownloader"
VERSION="${1:-1.0.0}"
ARCH="all"
SCRIPT_NAME="ipadownloader.py"
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
STAGING="/tmp/ipadownloader-deb-stage"
OUTPUT="${REPO_DIR}/${PKG}_${VERSION}_${ARCH}.deb"

echo "=== IPADownloader .deb 打包 ==="
echo "  包名: ${PKG}"
echo "  版本: ${VERSION}"
echo ""

# ── 依赖检查 ───────────────────────────────────────────
command -v dpkg-deb >/dev/null || { echo "❌ 缺少 dpkg-deb"; exit 1; }
[ -f "${REPO_DIR}/${SCRIPT_NAME}" ] || { echo "❌ ${SCRIPT_NAME} 不存在"; exit 1; }
[ -f "${REPO_DIR}/icon.png" ] && ICON_SRC="${REPO_DIR}/icon.png" || ICON_SRC="${REPO_DIR}/icon_0.jpg"

# ── 清理旧 staging ────────────────────────────────────
rm -rf "${STAGING}"
mkdir -p "${STAGING}/${PKG}/${VERSION}"

# ── 安装路径布局 ──────────────────────────────────────
mkdir -p "${STAGING}/${PKG}/${VERSION}/usr/bin"
mkdir -p "${STAGING}/${PKG}/${VERSION}/usr/share/${PKG}"
mkdir -p "${STAGING}/${PKG}/${VERSION}/usr/share/applications"
mkdir -p "${STAGING}/${PKG}/${VERSION}/usr/share/icons/hicolor/256x256/apps"
mkdir -p "${STAGING}/${PKG}/${VERSION}/usr/share/man/man1"
mkdir -p "${STAGING}/${PKG}/${VERSION}/DEBIAN"

# ── 主程序 ─────────────────────────────────────────────
cp "${REPO_DIR}/${SCRIPT_NAME}" "${STAGING}/${PKG}/${VERSION}/usr/share/${PKG}/"
cat > "${STAGING}/${PKG}/${VERSION}/usr/bin/ipadownloader" << 'LAUNCHER'
#!/usr/bin/env bash
# 统一入口：无论安装到哪个路径都能正确找到主程序
SCRIPT_PATH="$(dirname "$(readlink -f "$0")")/../share/ipadownloader/ipadownloader.py"
exec python3 "${SCRIPT_PATH}" "$@"
LAUNCHER
chmod +x "${STAGING}/${PKG}/${VERSION}/usr/bin/ipadownloader"

# ── 图标 ───────────────────────────────────────────────
# .desktop 文件必须用 PNG
ICON_OUT="${STAGING}/${PKG}/${VERSION}/usr/share/icons/hicolor/256x256/apps/${PKG}.png"
if [ -f "${ICON_SRC}" ] && file -b "${ICON_SRC}" | grep -q JPEG; then
    python3 -c "
from PIL import Image
Image.open('${ICON_SRC}').convert('RGB').resize((256,256)).save('${ICON_OUT}','PNG')
" 2>/dev/null || cp "${ICON_SRC}" "${ICON_OUT%.png}.jpg" 2>/dev/null || true
else
    cp "${ICON_SRC}" "${ICON_OUT}"
fi

# ── .desktop ───────────────────────────────────────────
cat > "${STAGING}/${PKG}/${VERSION}/usr/share/applications/${PKG}.desktop" << DESKTOP
[Desktop Entry]
Version=1.0
Type=Application
Name=IPADownloader
Name[zh_CN]=IPADownloader iOS 应用下载器
Comment=Download iOS Apps (ipa) from App Store
Comment[zh_CN]=从 App Store 下载 iOS 应用 (IPA)
Exec=env LANG=zh_CN.UTF-8 /usr/bin/ipadownloader
Icon=ipadownloader
Terminal=false
Categories=Utility;Network;
Keywords=ios;ipa;app;download;apple;
DESKTOP

# ── MAN 页 ─────────────────────────────────────────────
cat > "${STAGING}/${PKG}/${VERSION}/usr/share/man/man1/ipadownloader.1" << 'MAN'
.TH IPADOWNLOADER 1 "2026-08-01" "IPADownloader 1.0" "User Commands"
.SH NAME
ipadownloader \- Download iOS Apps (ipa) from App Store with a GUI
.SH SYNOPSIS
.B ipadownloader
.SH DESCRIPTION
IPADownloader 是一个 iOS App 下载工具的桌面 GUI 版本。
基于 ipatool CLI 实现，支持搜索、登录、下载功能。
.SH REQUIREMENTS
.TP
.B ipatool
.BR 安装方法: brew install majd/repo/ipatool
.TP
.B python3-tk
.BR 安装方法: sudo apt install python3-tk
.SH USAGE
1. 先安装 ipatool
2. 运行 ipadownloader 启动 GUI
3. 登录 Apple ID
4. 搜索并下载 iOS App (ipa)
.SH SEE ALSO
.BR ipatool (1)
.SH AUTHOR
IPADownloader Team
MAN

# ── DEBIAN/control ────────────────────────────────────
cat > "${STAGING}/${PKG}/${VERSION}/DEBIAN/control" << CONTROL
Package: ${PKG}
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: ${ARCH}
Depends: python3-tk
Recommends: ipatool
Maintainer: hongli11 <hongli11@users.noreply.github.com>
Description: iOS App (ipa) download tool with GUI
 IPADownloader wraps ipatool CLI in a desktop GUI,
 providing search, login, and one-click download of iOS
 apps (ipa) from the App Store.
 .
 Features:
  - Search App Store by keyword
  - Built-in Apple ID login dialog
  - One-click download to custom directory
  - Dark theme with CJK font support
CONTROL

# ── DEBIAN/postinst ───────────────────────────────────
cat > "${STAGING}/${PKG}/${VERSION}/DEBIAN/postinst" << 'POSTINST'
#!/usr/bin/env bash
set -e
update-icon-caches 2>/dev/null || true
echo "
IPADownloader 安装完成!

依赖检查:
  - ipatool:    $(command -v ipatool >/dev/null 2>&1 && echo '✅ 已安装' || echo '❌ 需要安装: brew install majd/repo/ipatool')
  - python3-tk: $(command -v python3 >/dev/null 2>&1 && python3 -c 'import tkinter' 2>/dev/null && echo '✅ 已安装' || echo '❌ 需要安装: sudo apt install python3-tk')

启动方式:
  命令行: ipadownloader
  桌面菜单: 搜索 "IPADownloader"
"
POSTINST
chmod +x "${STAGING}/${PKG}/${VERSION}/DEBIAN/postinst"

# ── DEBIAN/postrm ─────────────────────────────────────
cat > "${STAGING}/${PKG}/${VERSION}/DEBIAN/postrm" << 'POSTRM'
#!/usr/bin/env bash
set -e
case "$1" in
    remove|purge)
        update-icon-caches 2>/dev/null || true
        update-desktop-database 2>/dev/null || true
        ;;
esac
POSTRM
chmod +x "${STAGING}/${PKG}/${VERSION}/DEBIAN/postrm"

# ── 打包 ──────────────────────────────────────────────
echo "  构建 .deb ..."
( cd "${STAGING}" && dpkg-deb --build --root-owner-group "${PKG}/${VERSION}" )
mv "${STAGING}/${PKG}/${VERSION}.deb" "${OUTPUT}"

# ── 输出 ───────────────────────────────────────────────
echo ""
echo "✅ .deb 已生成:"
ls -lh "${OUTPUT}"
echo ""
echo "  安装: sudo dpkg -i ${OUTPUT}"
echo "  启动: ipadownloader"
