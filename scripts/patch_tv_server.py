#!/usr/bin/env python3
"""Patch Jellyfin Android TV ServerRepository.kt to seed the default Jellyfin server on first launch."""

import os
import re
import sys
from pathlib import Path

DEFAULT_URL = os.environ.get("SERVER_URL", "https://jelly.lulospi.party").strip().rstrip("/")


def patch_server_repository(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")

    pattern = re.compile(
        r"(\t// Loading data\n"
        r"\toverride suspend fun loadStoredServers\(\) \{\n)"
        r"(\t\tauthenticationStore\.getServers\(\)\n)"
    )

    replacement = (
        f"\tprivate var defaultServerSeeded = false\n\n"
        r"\1"
        f"\t\tif (!defaultServerSeeded && authenticationStore.getServers().isEmpty()) {{\n"
        f"\t\t\tdefaultServerSeeded = true\n"
        f"\t\t\trunCatching {{\n"
        f'\t\t\t\taddServer("{DEFAULT_URL}").collect {{}}\n'
        f"\t\t\t}}\n"
        f"\t\t}}\n"
        r"\2"
    )

    patched, count = pattern.subn(replacement, text, count=1)
    if count != 1:
        sys.stderr.write(
            f"ERROR: Could not find expected loadStoredServers() block in {path} (matches={count}).\n"
            "Upstream ServerRepository.kt likely changed; update scripts/patch_tv_server.py.\n"
        )
        sys.exit(1)

    if DEFAULT_URL not in patched:
        sys.stderr.write("ERROR: Patched file does not contain expected server URL.\n")
        sys.exit(1)

    path.write_text(patched.replace("\n", eol), encoding="utf-8")
    print(f"OK: Patched {path} with default TV server {DEFAULT_URL}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: patch_tv_server.py <path/to/ServerRepository.kt>\n")
        sys.exit(2)
    patch_server_repository(Path(sys.argv[1]))
