from __future__ import annotations

import socket
import time
import urllib.request

from .config import AppConfig, ServerProfile


def tcp_latency(profile: ServerProfile, timeout: float = 3.0) -> float:
    start = time.perf_counter()
    with socket.create_connection((profile.server, profile.server_port), timeout=timeout):
        pass
    return (time.perf_counter() - start) * 1000


def test_http_proxy(config: AppConfig, timeout: float = 8.0) -> tuple[int, float]:
    proxy_url = f"http://127.0.0.1:{config.http_port}"
    opener = urllib.request.build_opener(
        urllib.request.ProxyHandler({"http": proxy_url, "https": proxy_url})
    )
    request = urllib.request.Request(
        "https://www.google.com/generate_204",
        headers={"User-Agent": "LibreWing/0.2"},
    )
    start = time.perf_counter()
    with opener.open(request, timeout=timeout) as response:
        status = response.status
        response.read(1)
    return status, (time.perf_counter() - start) * 1000
