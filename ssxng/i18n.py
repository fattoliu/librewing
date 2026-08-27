from __future__ import annotations

import locale
import os

# Keep English keys as the source language. Missing translations intentionally
# fall back to the key so new UI never breaks because of localization.
# Simplified Chinese wording follows ShadowsocksX-NG's zh-Hans menu strings
# where an upstream equivalent exists.
_ZH_CN = {
    "Shadowsocks: On": "Shadowsocks：已开启",
    "Shadowsocks: Off": "Shadowsocks：已关闭",
    "Turn Off Shadowsocks": "关闭 Shadowsocks",
    "Turn On Shadowsocks": "开启 Shadowsocks",
    "PAC Auto Mode": "PAC自动模式",
    "Global Mode": "全局模式",
    "Manual Mode": "手动模式",
    "External PAC Auto Mode": "外部PAC自动模式",
    "Servers": "服务器",
    "Server Settings…": "服务器设置...",
    "Scan QR Code on Screen": "扫描屏幕上的二维码",
    "Import Server URL…": "导入服务器URL...",
    "Share Server Configuration…": "分享服务器配置...",
    "Preferences…": "偏好设置...",
    "Copy Terminal Proxy Command": "复制终端代理命令",
    "Update PAC from GFWList": "从 GFW List 更新PAC",
    "Edit PAC User Rules…": "编辑PAC用户自定规则...",
    "View Logs…": "显示日志...",
    "Export Diagnostics…": "导出诊断信息...",
    "Check for Updates…": "检查更新...",
    "Help": "帮助",
    "About": "关于",
    "Quit": "退出",
}

_ZH_TW = {
    "Shadowsocks: On": "Shadowsocks：已開啟",
    "Shadowsocks: Off": "Shadowsocks：已關閉",
    "Turn Off Shadowsocks": "關閉 Shadowsocks",
    "Turn On Shadowsocks": "開啟 Shadowsocks",
    "PAC Auto Mode": "PAC 自動模式",
    "Global Mode": "全域模式",
    "Manual Mode": "手動模式",
    "External PAC Auto Mode": "外部 PAC 自動模式",
    "Servers": "伺服器",
    "Server Settings…": "伺服器設定…",
    "Scan QR Code on Screen": "掃描螢幕上的 QR Code",
    "Import Server URL…": "匯入伺服器 URL…",
    "Share Server Configuration…": "分享伺服器設定…",
    "Preferences…": "偏好設定…",
    "Copy Terminal Proxy Command": "複製終端機代理命令",
    "Update PAC from GFWList": "從 GFWList 更新 PAC",
    "Edit PAC User Rules…": "編輯 PAC 使用者規則…",
    "View Logs…": "檢視日誌…",
    "Export Diagnostics…": "匯出診斷資訊…",
    "Check for Updates…": "檢查更新…",
    "Help": "說明",
    "About": "關於",
    "Quit": "結束",
}


def system_language() -> str:
    """Return our normalized UI language from the desktop/session locale."""
    # LANGUAGE is the strongest GNU desktop preference and may contain a
    # colon-separated fallback list. LC_ALL/LC_MESSAGES/LANG follow it.
    raw = (
        os.environ.get("LANGUAGE", "").split(":", 1)[0]
        or os.environ.get("LC_ALL", "")
        or os.environ.get("LC_MESSAGES", "")
        or os.environ.get("LANG", "")
    )
    if not raw:
        try:
            raw = locale.getlocale()[0] or ""
        except Exception:
            raw = ""

    value = raw.replace("-", "_").lower()
    if value.startswith(("zh_cn", "zh_sg", "zh_hans")):
        return "zh_CN"
    if value.startswith(("zh_tw", "zh_hk", "zh_mo", "zh_hant")):
        return "zh_TW"
    return "en"


def tr(text: str) -> str:
    language = system_language()
    if language == "zh_CN":
        return _ZH_CN.get(text, text)
    if language == "zh_TW":
        return _ZH_TW.get(text, text)
    return text
