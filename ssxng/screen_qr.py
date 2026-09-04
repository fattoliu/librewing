from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import threading
from pathlib import Path
from urllib.parse import unquote, urlparse

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio, GLib  # noqa: E402


class ScreenQrError(RuntimeError):
    pass


def _portal_capture(image: Path, timeout: float = 30.0) -> None:
    """Capture the desktop through xdg-desktop-portal.

    GNOME/Wayland intentionally blocks the old org.gnome.Shell.Screenshot D-Bus
    API for ordinary applications. The freedesktop Screenshot portal is the
    supported path and lets GNOME handle the required user permission/UI.
    """
    bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
    loop = GLib.MainLoop()
    state: dict[str, object] = {"request": None, "response": None, "results": None}

    def on_response(
        _connection,
        _sender_name,
        object_path,
        _interface_name,
        _signal_name,
        parameters,
        _user_data,
    ) -> None:
        request = state["request"]
        if request is not None and object_path != request:
            return
        response, results = parameters.unpack()
        state["response"] = int(response)
        state["results"] = results
        loop.quit()

    subscription = bus.signal_subscribe(
        "org.freedesktop.portal.Desktop",
        "org.freedesktop.portal.Request",
        "Response",
        None,
        None,
        Gio.DBusSignalFlags.NONE,
        on_response,
        None,
    )

    token = f"ssxng{os.getpid()}"
    options = {
        "handle_token": GLib.Variant("s", token),
        "interactive": GLib.Variant("b", False),
    }

    try:
        reply = bus.call_sync(
            "org.freedesktop.portal.Desktop",
            "/org/freedesktop/portal/desktop",
            "org.freedesktop.portal.Screenshot",
            "Screenshot",
            GLib.Variant("(sa{sv})", ("", options)),
            GLib.VariantType.new("(o)"),
            Gio.DBusCallFlags.NONE,
            5000,
            None,
        )
        state["request"] = reply.unpack()[0]

        timer = threading.Timer(timeout, loop.quit)
        timer.daemon = True
        timer.start()
        try:
            loop.run()
        finally:
            timer.cancel()
    except Exception as exc:
        raise ScreenQrError(f"无法调用系统截图服务：{exc}") from exc
    finally:
        bus.signal_unsubscribe(subscription)

    response = state["response"]
    results = state["results"]
    if response is None:
        raise ScreenQrError("等待系统截图授权超时")
    if response != 0:
        if response == 1:
            raise ScreenQrError("截图已取消")
        raise ScreenQrError("系统未允许截取屏幕")
    if not isinstance(results, dict) or not results.get("uri"):
        raise ScreenQrError("系统截图服务没有返回截图文件")

    parsed = urlparse(str(results["uri"]))
    source = Path(unquote(parsed.path))
    if not source.exists():
        raise ScreenQrError("系统返回的截图文件不存在")
    shutil.copyfile(source, image)


def _legacy_capture(image: Path) -> None:
    """Fallback for X11/older desktops where direct screenshot tools work."""
    screenshot = shutil.which("gnome-screenshot")
    if screenshot:
        result = subprocess.run(
            [screenshot, "-f", str(image)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if result.returncode == 0 and image.exists():
            return
        detail = (result.stderr or result.stdout or "screen capture failed").strip()
        if detail:
            raise ScreenQrError(detail)

    raise ScreenQrError("当前桌面环境没有可用的截图服务")


def _capture_screen(image: Path) -> None:
    """Capture the desktop using the supported API for the current session."""
    session_type = os.environ.get("XDG_SESSION_TYPE", "").lower()

    # On Wayland the portal is not optional: GNOME blocks the historical Shell
    # Screenshot D-Bus API with AccessDenied, exactly as Ubuntu 26 reports.
    if session_type == "wayland":
        _portal_capture(image)
        return

    # X11 still permits gnome-screenshot; prefer it because it is immediate and
    # does not need a permission portal. If unavailable, the portal still works.
    try:
        _legacy_capture(image)
    except ScreenQrError:
        _portal_capture(image)


def scan_screen_payloads() -> list[str]:
    """Capture the desktop and decode all QR payloads with zbarimg."""
    zbarimg = shutil.which("zbarimg")
    if not zbarimg:
        raise ScreenQrError("zbarimg is not installed")

    with tempfile.TemporaryDirectory(prefix="ssxng-qr-") as tmp:
        image = Path(tmp) / "screen.png"
        _capture_screen(image)

        decoded = subprocess.run(
            [zbarimg, "--quiet", "--raw", str(image)],
            capture_output=True,
            text=True,
            timeout=15,
            check=False,
        )
        if decoded.returncode not in (0, 4):
            detail = (decoded.stderr or "QR decoding failed").strip()
            raise ScreenQrError(detail)

        seen: set[str] = set()
        payloads: list[str] = []
        for line in decoded.stdout.splitlines():
            value = line.strip()
            if value and value not in seen:
                seen.add(value)
                payloads.append(value)
        return payloads
