"""Reorder glyphs in an SFD file by their Unicode codepoint and renumber the
encoding slots sequentially.

Glyphs with unicode = -1 (e.g. .notdef, NULL, CR) are kept at the start in
their original order; all others are sorted ascending by Unicode value.
The `Encoding: <slot> <unicode> <pos>` line of every glyph is rewritten so
`<slot>` and `<pos>` match the new index. Line endings (CRLF) are preserved.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

SFD = Path(r"c:\Users\msi\Desktop\prog\ZamFonts\ZamIco.sfd")


def main(dry_run: bool = False) -> None:
    raw = SFD.read_bytes()
    # Detect line ending then operate on text with \n internally.
    eol = b"\r\n" if b"\r\n" in raw else b"\n"
    text = raw.decode("utf-8").replace("\r\n", "\n")
    lines = text.split("\n")

    # Locate the BeginChars / EndChars block.
    begin_idx = next(i for i, l in enumerate(lines) if l.startswith("BeginChars:"))
    end_idx = next(i for i, l in enumerate(lines) if l == "EndChars")

    header = lines[: begin_idx + 1]  # includes "BeginChars: ..."
    body = lines[begin_idx + 1 : end_idx]
    footer = lines[end_idx:]  # starts with "EndChars"

    # Split body into individual glyph blocks (StartChar..EndChar) and capture
    # the surrounding blank lines so we can restore the original spacing.
    blocks: list[tuple[str, int, list[str]]] = []  # (name, unicode, lines)
    i = 0
    while i < len(body):
        if body[i].startswith("StartChar:"):
            name = body[i].split(":", 1)[1].strip()
            j = i
            while j < len(body) and body[j] != "EndChar":
                j += 1
            assert j < len(body), "Unterminated glyph block"
            block = body[i : j + 1]
            # Find the Encoding line and read its <unicode> field.
            uni = -1
            for bl in block:
                m = re.match(r"^Encoding:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*$", bl)
                if m:
                    uni = int(m.group(2))
                    break
            blocks.append((name, uni, block))
            i = j + 1
        else:
            i += 1

    # Sort: unicode == -1 first (stable, original order), then ascending uni.
    indexed = list(enumerate(blocks))
    indexed.sort(key=lambda t: (0 if t[1][1] == -1 else 1, t[1][1], t[0]))
    sorted_blocks = [b for _, b in indexed]

    # Renumber encoding slots sequentially.
    new_body: list[str] = [""]  # blank line right after BeginChars (matches original)
    for new_slot, (name, uni, block) in enumerate(sorted_blocks):
        new_block: list[str] = []
        for bl in block:
            m = re.match(r"^Encoding:\s+(-?\d+)\s+(-?\d+)\s+(-?\d+)\s*$", bl)
            if m:
                new_block.append(f"Encoding: {new_slot} {uni} {new_slot}")
            else:
                new_block.append(bl)
        new_body.extend(new_block)
        new_body.append("")  # blank line between glyphs

    # Update BeginChars: <max_slot+1> <count>
    n = len(sorted_blocks)
    header[-1] = f"BeginChars: {n} {n}"

    out_lines = header + new_body + footer
    out_text = "\n".join(out_lines)
    out_bytes = out_text.encode("utf-8").replace(b"\n", eol)

    # Print summary so the change is auditable.
    print(f"Reordered {n} glyphs. New order:")
    for slot, (name, uni, _) in enumerate(sorted_blocks):
        hex_uni = f"U+{uni:04X}" if uni >= 0 else "  -1  "
        print(f"  slot {slot:>3}  {hex_uni:>8}  {name}")

    if dry_run:
        print("\n[dry run] file not written")
        return

    SFD.write_bytes(out_bytes)
    print(f"\nWrote {SFD}")


if __name__ == "__main__":
    main(dry_run="--dry-run" in sys.argv)
