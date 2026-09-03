from __future__ import annotations

import base64
from urllib.parse import parse_qs, quote, unquote, urlparse

from .config import ServerProfile


def _b64decode(value: str) -> str:
    value = value.strip()
    value += "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value.encode()).decode("utf-8")


def _b64encode(value: str) -> str:
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _validate_profile(profile: ServerProfile) -> ServerProfile:
    if not profile.server.strip():
        raise ValueError("Shadowsocks server host is required")
    if not 1 <= int(profile.server_port) <= 65535:
        raise ValueError("Shadowsocks server port must be between 1 and 65535")
    if not profile.method:
        raise ValueError("Shadowsocks cipher method is required")
    if not profile.password:
        raise ValueError("Shadowsocks password is required")
    return profile


def parse_ss_url(url: str) -> ServerProfile:
    url = url.strip()
    if not url.startswith("ss://"):
        raise ValueError("Not a valid ss:// URL")

    parsed = urlparse(url)
    plugin = ""
    plugin_opts = ""
    name = unquote(parsed.fragment) or "Imported"

    if parsed.hostname and parsed.port:
        # SIP002 form: ss://BASE64(method:password)@host:port/?plugin=...
        userinfo = parsed.username or ""
        try:
            credentials = _b64decode(userinfo)
        except Exception:
            credentials = unquote(userinfo)
        if ":" not in credentials:
            raise ValueError("Invalid Shadowsocks credentials")
        method, password = credentials.split(":", 1)
        server = parsed.hostname
        port = parsed.port
        query = parse_qs(parsed.query)
        plugin_value = unquote(query.get("plugin", [""])[0])
        if plugin_value:
            parts = plugin_value.split(";", 1)
            plugin = parts[0]
            plugin_opts = parts[1] if len(parts) > 1 else ""
    else:
        # Legacy form: ss://BASE64(method:password@host:port)#name
        payload = parsed.netloc + parsed.path
        decoded = _b64decode(payload)
        credentials, endpoint = decoded.rsplit("@", 1)
        method, password = credentials.split(":", 1)
        server, port_text = endpoint.rsplit(":", 1)
        if server.startswith("[") and server.endswith("]"):
            server = server[1:-1]
        port = int(port_text)

    return _validate_profile(ServerProfile(
        name=name,
        server=server,
        server_port=int(port),
        password=password,
        method=method,
        plugin=plugin,
        plugin_opts=plugin_opts,
    ))


def build_ss_url(profile: ServerProfile) -> str:
    _validate_profile(profile)
    credentials = _b64encode(f"{profile.method}:{profile.password}")
    server = profile.server.strip()
    if ":" in server and not server.startswith("["):
        server = f"[{server}]"
    base = f"ss://{credentials}@{server}:{profile.server_port}"
    if profile.plugin:
        plugin = profile.plugin
        if profile.plugin_opts:
            plugin += ";" + profile.plugin_opts
        base += "/?plugin=" + quote(plugin, safe="")
    return base + "#" + quote(profile.name)
