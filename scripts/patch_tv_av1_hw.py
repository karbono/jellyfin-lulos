#!/usr/bin/env python3
"""Patch Jellyfin Android TV MediaCodecQuery.kt so AV1 only counts hardware decoders.

Upstream treats any AV1 decoder (including software ones such as c2.android.av1-decoder,
dav1d or libgav1) as proof that the device can direct play AV1, and takes the maximum
resolution across all of them. On most TVs the software decoder cannot keep up with
4K AV1, so playback stops after a few seconds instead of letting the server transcode.

After this patch, AV1 decoders must be hardware accelerated (Android 10+: not
isSoftwareOnly and isHardwareAccelerated; older: name heuristic) regardless of the
"Use software codecs" preference; other codecs keep upstream behaviour.
"""

import re
import sys
from pathlib import Path

MARKER = "jellyfin-lulos: AV1 hardware only"

HELPERS = (
    "\t// " + MARKER + "\n"
    "\tprivate val MediaCodecInfo.looksLikeSoftwareCodec: Boolean\n"
    "\t\tget() {\n"
    "\t\t\tif (AndroidVersion.isAtLeastQ) return isSoftwareOnly || !isHardwareAccelerated\n"
    "\t\t\tval n = name.lowercase()\n"
    "\t\t\treturn n.startsWith(\"omx.google.\") || n.startsWith(\"c2.android.\") ||\n"
    "\t\t\t\tn.contains(\"dav1d\") || n.contains(\"gav1\") || n.contains(\"ffmpeg\")\n"
    "\t\t}\n"
    "\n"
    "\tprivate fun requiresHardware(mime: String?): Boolean =\n"
    "\t\tmime != null && mime.equals(MediaFormat.MIMETYPE_VIDEO_AV1, ignoreCase = true)\n"
    "\n"
)

OLD_DECODER_INFOS = (
    "\tprivate fun decoderInfos(): Sequence<MediaCodecInfo> =\n"
    "\t\tmediaCodecList.codecInfos.asSequence()\n"
    "\t\t\t.filter { !it.isEncoder }\n"
    "\t\t\t.filter { softwareCodecsEnabled || !it.isSoftwareCodec }\n"
)

NEW_DECODER_INFOS = (
    "\tprivate fun decoderInfos(mime: String? = null): Sequence<MediaCodecInfo> =\n"
    "\t\tmediaCodecList.codecInfos.asSequence()\n"
    "\t\t\t.filter { !it.isEncoder }\n"
    "\t\t\t.filter { softwareCodecsEnabled || !it.isSoftwareCodec }\n"
    "\t\t\t.filter { !requiresHardware(mime) || !it.looksLikeSoftwareCodec }\n"
)

# Public query functions that take `mime` and iterate decoderInfos().
EXPECTED_CALLS = 5


def patch(path: Path) -> None:
    with open(path, encoding="utf-8", newline="") as fh:
        raw = fh.read()
    eol = "\r\n" if "\r\n" in raw else "\n"
    text = raw.replace("\r\n", "\n")

    if MARKER in text:
        print(f"OK: {path} already patched")
        return

    if text.count(OLD_DECODER_INFOS) != 1:
        sys.stderr.write(
            f"ERROR: decoderInfos() definition not found as expected in {path}.\n"
            "Upstream MediaCodecQuery.kt changed; update scripts/patch_tv_av1_hw.py.\n"
        )
        sys.exit(1)
    if "import android.media.MediaFormat\n" not in text or "import org.jellyfin.androidtv.util.AndroidVersion\n" not in text:
        sys.stderr.write("ERROR: expected imports (MediaFormat, AndroidVersion) missing.\n")
        sys.exit(1)

    text = text.replace(OLD_DECODER_INFOS, HELPERS + NEW_DECODER_INFOS)

    # Every remaining call site lives in a function with a `mime: String` parameter.
    text, calls = re.subn(r"\bdecoderInfos\(\)(?=\s*\.|\))", "decoderInfos(mime)", text)
    if calls != EXPECTED_CALLS:
        sys.stderr.write(
            f"ERROR: expected {EXPECTED_CALLS} decoderInfos() call sites, found {calls}.\n"
            "Upstream MediaCodecQuery.kt changed; review scripts/patch_tv_av1_hw.py.\n"
        )
        sys.exit(1)

    # Sanity: each function that now calls decoderInfos(mime) must declare `mime`.
    for fn in re.finditer(r"\n\t(?:private )?fun (\w+)\(([^)]*)\)[^\n]*\n((?:\t\t[^\n]*\n|\n)*)", text):
        name, params, body = fn.group(1), fn.group(2), fn.group(3)
        if "decoderInfos(mime)" in body and "mime: String" not in params:
            sys.stderr.write(f"ERROR: {name}() calls decoderInfos(mime) without a mime parameter.\n")
            sys.exit(1)

    with open(path, "w", encoding="utf-8", newline="") as fh:
        fh.write(text.replace("\n", eol))
    print(f"OK: Patched {path} (AV1 hardware decoders only, {calls} call sites)")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.stderr.write("Usage: patch_tv_av1_hw.py <path/to/MediaCodecQuery.kt>\n")
        sys.exit(2)
    patch(Path(sys.argv[1]))
