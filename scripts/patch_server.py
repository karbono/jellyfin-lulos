#!/usr/bin/env python3
"""Patch Jellyfin Android MainViewModel.kt to preconfigure the default Jellyfin server."""

import os
import re
import sys
from pathlib import Path

DEFAULT_URL = os.environ.get("SERVER_URL", "https://tv.karbono.es").strip().rstrip("/")


def patch_main_viewmodel(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")

    pattern = re.compile(
        r"(    init \{\n"
        r"        viewModelScope\.launch \{\n"
        r"            refreshServer\(\)\n)"
        r"(            refreshUser\(\)\n"
        r"        \}\n"
        r"    \}\n)"
    )

    replacement = (
        r"\1"
        f"            if (_serverState.value is ServerState.Unset) {{\n"
        f'                apiClientController.setupServer("{DEFAULT_URL}")\n'
        f"                refreshServer()\n"
        f"            }}\n"
        r"\2"
    )

    patched, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        sys.stderr.write(
            f"ERROR: Could not find expected init block in {path} (matches={count}).\n"
            "Upstream MainViewModel.kt likely changed; update scripts/patch_server.py.\n"
        )
        sys.exit(1)

    if DEFAULT_URL not in patched:
        sys.stderr.write("ERROR: Patched file does not contain expected server URL.\n")
        sys.exit(1)

    path.write_text(patched.replace("\n", eol), encoding="utf-8")
    print(f"OK: Patched {path} with default server {DEFAULT_URL}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: patch_server.py <path/to/MainViewModel.kt>\n")
        sys.exit(2)
    patch_main_viewmodel(Path(sys.argv[1]))
