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
        port = int(port_text)

    return ServerProfile(
        name=name,
        server=server,
        server_port=int(port),
        password=password,
        method=method,
        plugin=plugin,
        plugin_opts=plugin_opts,
    )


def build_ss_url(profile: ServerProfile) -> str:
    credentials = _b64encode(f"{profile.method}:{profile.password}")
    base = f"ss://{credentials}@{profile.server}:{profile.server_port}"
    if profile.plugin:
        plugin = profile.plugin
        if profile.plugin_opts:
            plugin += ";" + profile.plugin_opts
        base += "/?plugin=" + quote(plugin, safe="")
    return base + "#" + quote(profile.name)
