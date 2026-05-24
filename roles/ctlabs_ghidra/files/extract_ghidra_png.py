#!/usr/bin/env python3
import struct, os, sys

ico_path = "/opt/ghidra_12.1_PUBLIC/support/ghidra.ico"
png_path = "/opt/ghidra_12.1_PUBLIC/support/ghidra.png"

with open(ico_path, "rb") as f:
    data = f.read()

count = struct.unpack_from("<H", data, 4)[0]
entries = []
offset = 6
for i in range(count):
    w, h, colors, reserved, planes, bpp, size, off = struct.unpack_from("<BBBBHHII", data, offset)
    entries.append((w or 256, h or 256, off, size))
    offset += 16

entries.sort(key=lambda x: x[0], reverse=True)
w, h, off, sz = entries[0]
png_data = data[off:off+sz]

if png_data[:4] == b"\x89PNG":
    with open(png_path, "wb") as out:
        out.write(png_data)
    print(f"OK {w}x{h}")
else:
    print("FAIL not PNG")
    sys.exit(1)
