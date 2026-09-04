#!/usr/bin/env python3
from __future__ import annotations

import binascii
import struct
import sys
import zlib
from pathlib import Path

PNG_SIG = b"\x89PNG\r\n\x1a\n"


def _paeth(a: int, b: int, c: int) -> int:
    p = a + b - c
    pa = abs(p - a)
    pb = abs(p - b)
    pc = abs(p - c)
    if pa <= pb and pa <= pc:
        return a
    if pb <= pc:
        return b
    return c


def _chunk(kind: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + kind
        + data
        + struct.pack(">I", binascii.crc32(kind + data) & 0xFFFFFFFF)
    )


def recolor_rgba_png(src: Path, dst: Path, rgb: tuple[int, int, int]) -> None:
    raw = src.read_bytes()
    if not raw.startswith(PNG_SIG):
        raise ValueError(f"Not a PNG: {src}")

    pos = len(PNG_SIG)
    ihdr = None
    idat_parts: list[bytes] = []
    while pos < len(raw):
        length = struct.unpack(">I", raw[pos : pos + 4])[0]
        kind = raw[pos + 4 : pos + 8]
        data = raw[pos + 8 : pos + 8 + length]
        pos += 12 + length
        if kind == b"IHDR":
            ihdr = data
        elif kind == b"IDAT":
            idat_parts.append(data)
        elif kind == b"IEND":
            break

    if ihdr is None:
        raise ValueError("PNG has no IHDR")

    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", ihdr
    )
    if bit_depth != 8 or color_type != 6 or interlace != 0:
        raise ValueError(
            "Expected non-interlaced 8-bit RGBA PNG; "
            f"got bit_depth={bit_depth}, color_type={color_type}, interlace={interlace}"
        )
    if compression != 0 or filtering != 0:
        raise ValueError("Unsupported PNG compression/filter method")

    bpp = 4
    stride = width * bpp
    data = zlib.decompress(b"".join(idat_parts))
    expected = height * (stride + 1)
    if len(data) != expected:
        raise ValueError(f"Unexpected decoded size: {len(data)} != {expected}")

    rows: list[bytearray] = []
    offset = 0
    prev = bytearray(stride)
    for _ in range(height):
        filter_type = data[offset]
        offset += 1
        scan = bytearray(data[offset : offset + stride])
        offset += stride
        recon = bytearray(stride)

        for i, value in enumerate(scan):
            left = recon[i - bpp] if i >= bpp else 0
            up = prev[i]
            up_left = prev[i - bpp] if i >= bpp else 0
            if filter_type == 0:
                recon[i] = value
            elif filter_type == 1:
                recon[i] = (value + left) & 0xFF
            elif filter_type == 2:
                recon[i] = (value + up) & 0xFF
            elif filter_type == 3:
                recon[i] = (value + ((left + up) // 2)) & 0xFF
            elif filter_type == 4:
                recon[i] = (value + _paeth(left, up, up_left)) & 0xFF
            else:
                raise ValueError(f"Unsupported PNG filter type: {filter_type}")

        for x in range(width):
            i = x * 4
            if recon[i + 3] != 0:
                recon[i], recon[i + 1], recon[i + 2] = rgb

        rows.append(recon)
        prev = recon

    # Re-encode with filter type 0. For these tiny tray icons this keeps the
    # implementation dependency-free and deterministic.
    packed = b"".join(b"\x00" + bytes(row) for row in rows)
    out = PNG_SIG + _chunk(b"IHDR", ihdr) + _chunk(b"IDAT", zlib.compress(packed, 9)) + _chunk(b"IEND", b"")
    dst.write_bytes(out)


def main() -> int:
    if len(sys.argv) != 6:
        print("usage: recolor-png.py SRC DST R G B", file=sys.stderr)
        return 2
    src = Path(sys.argv[1])
    dst = Path(sys.argv[2])
    rgb = tuple(int(v) for v in sys.argv[3:6])
    if any(v < 0 or v > 255 for v in rgb):
        raise ValueError("RGB values must be 0..255")
    recolor_rgba_png(src, dst, rgb)  # type: ignore[arg-type]
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
