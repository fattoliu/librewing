from __future__ import annotations

import locale
import os

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
    "Server Settings": "服务器设置",
    "Scan QR Code on Screen": "扫描屏幕上的二维码",
    "Import Server URL…": "导入服务器URL...",
    "Import Server URLs From Clipboard": "从剪贴板导入服务器配置链接",
    "Share Server Configuration…": "分享服务器配置...",
    "Preferences…": "偏好设置...",
    "Preferences": "偏好设置",
    "Copy Terminal Proxy Command": "复制终端代理命令",
    "Update PAC from GFWList": "从 GFW List 更新PAC",
    "Edit PAC User Rules…": "编辑PAC用户自定规则...",
    "View Logs…": "显示日志...",
    "Export Diagnostics…": "导出诊断信息...",
    "Check for Updates…": "检查更新...",
    "Help": "帮助",
    "About": "关于",
    "Quit": "退出",
    "Name": "名称",
    "Server": "服务器",
    "Server port": "服务器端口",
    "Password": "密码",
    "Cipher": "加密方式",
    "Plugin": "插件",
    "Plugin options": "插件参数",
    "Local SOCKS port": "本地 SOCKS 端口",
    "Add server": "添加服务器",
    "Remove selected server": "删除选中的服务器",
    "Tip: select a server on the left to edit it. Add or remove multiple profiles before saving.": "提示：在左侧选择服务器后进行编辑，可在保存前添加或删除多个服务器配置。",
    "At least one server profile must remain.": "至少需要保留一个服务器配置。",
    "PAC Rules": "PAC 规则",
    "Use GFWList": "使用 GFWList",
    "GFWList URL": "GFWList URL",
    "One rule per line. Adblock/GFWList syntax is supported; @@ rules are DIRECT.": "每行一条规则。支持 Adblock/GFWList 语法；@@ 规则表示直连。",
    "Start ShadowsocksX-NG Linux after login": "登录时自动启动 ShadowsocksX-NG Linux",
    "PAC server port": "PAC 服务端口",
    "HTTP proxy port": "HTTP 代理端口",
    "ABP PAC engine URL": "ABP PAC 引擎 URL",
    "Proxy Logs": "代理日志",
    "Clear": "清空",
    "No proxy log entries yet.": "暂时没有代理日志。",
    "Import Server": "导入服务器",
    "Paste an ss:// URL": "粘贴 ss:// URL",
    "Terminal proxy command copied to clipboard.": "终端代理命令已复制至剪贴板。",
    "Current server URL copied to clipboard.": "当前服务器 URL 已复制至剪贴板。",
    "No new valid ss:// server links found in the clipboard.": "剪贴板中没有找到新的有效 ss:// 服务器链接。",
    "No Shadowsocks QR code was found on the screen.": "屏幕上没有找到有效的 Shadowsocks 二维码。",
    "Imported {count} server(s).": "已导入 {count} 个服务器配置。",
    "Diagnostics exported.": "诊断信息已导出。",
    "Save Diagnosis to File": "保存诊断信息到文件",
    "Help text": "选择代理模式和服务器即可使用。出现问题时可查看日志或导出诊断信息。",
    "PAC rules saved. Changes are effective immediately.": "PAC 规则已保存并立即生效。",
    "GFWList update started in the background.": "正在后台更新 GFWList。",
    "GFWList updated: {count} domains.": "已经使用最新的 GFW List 更新PAC，共 {count} 个域名。",
    "Export Command Copied.": "Export 命令已复制至剪贴板",
}

_ZH_TW = {
    **_ZH_CN,
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
    "Server Settings": "伺服器設定",
    "Scan QR Code on Screen": "掃描螢幕上的 QR Code",
    "Import Server URL…": "匯入伺服器 URL…",
    "Import Server URLs From Clipboard": "從剪貼簿匯入伺服器設定連結",
    "Share Server Configuration…": "分享伺服器設定…",
    "Preferences…": "偏好設定…",
    "Preferences": "偏好設定",
    "Copy Terminal Proxy Command": "複製終端機代理命令",
    "Update PAC from GFWList": "從 GFWList 更新 PAC",
    "Edit PAC User Rules…": "編輯 PAC 使用者規則…",
    "View Logs…": "檢視日誌…",
    "Export Diagnostics…": "匯出診斷資訊…",
    "Check for Updates…": "檢查更新…",
    "Help": "說明",
    "About": "關於",
    "Quit": "結束",
    "Name": "名稱",
    "Server": "伺服器",
    "Server port": "伺服器連接埠",
    "Password": "密碼",
    "Cipher": "加密方式",
    "Plugin": "外掛",
    "Plugin options": "外掛參數",
    "Local SOCKS port": "本機 SOCKS 連接埠",
    "Add server": "新增伺服器",
    "Remove selected server": "刪除選取的伺服器",
    "At least one server profile must remain.": "至少需要保留一個伺服器設定。",
    "Start ShadowsocksX-NG Linux after login": "登入時自動啟動 ShadowsocksX-NG Linux",
    "PAC server port": "PAC 服務連接埠",
    "HTTP proxy port": "HTTP 代理連接埠",
    "Proxy Logs": "代理日誌",
    "Clear": "清除",
    "Import Server": "匯入伺服器",
    "Paste an ss:// URL": "貼上 ss:// URL",
    "Terminal proxy command copied to clipboard.": "終端機代理命令已複製到剪貼簿。",
    "Current server URL copied to clipboard.": "目前伺服器 URL 已複製到剪貼簿。",
    "No new valid ss:// server links found in the clipboard.": "剪貼簿中沒有找到新的有效 ss:// 伺服器連結。",
    "No Shadowsocks QR code was found on the screen.": "螢幕上沒有找到有效的 Shadowsocks QR Code。",
    "Imported {count} server(s).": "已匯入 {count} 個伺服器設定。",
    "Diagnostics exported.": "診斷資訊已匯出。",
    "Save Diagnosis to File": "儲存診斷資訊到檔案",
    "Help text": "選擇代理模式和伺服器即可使用。發生問題時可檢視日誌或匯出診斷資訊。",
}


def system_language() -> str:
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


def tr(text: str, **kwargs) -> str:
    language = system_language()
    if language == "zh_CN":
        value = _ZH_CN.get(text, text)
    elif language == "zh_TW":
        value = _ZH_TW.get(text, text)
    else:
        value = text
    return value.format(**kwargs) if kwargs else value
