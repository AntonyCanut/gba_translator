#!/usr/bin/env python3
import argparse
import os
import re
from itertools import zip_longest


def load_lines(path: str):
    with open(path, encoding="utf-8") as f:
        return f.read().splitlines()


def count_breaks(text: str):
    return text.count("\\p"), text.count("\\l")


def has_double_n(text: str):
    return "\\n\\n" in text


def visible_length(segment: str) -> int:
    """Compute visible length for a segment between control codes."""
    # Remove color tags ({COLOR}X)
    cleaned = re.sub(r"\{COLOR}.", "", segment)
    # Replace player/rival placeholders with length 7
    cleaned = cleaned.replace("{PLAYER}", "_______").replace("{RIVAL}", "_______")
    # Drop any other placeholder braces
    cleaned = re.sub(r"\{[^}]+}", "", cleaned)
    return len(cleaned)


def main():
    parser = argparse.ArgumentParser(
        description="Compare control breaks between an origin chunk and its translation."
    )
    parser.add_argument("--fr", required=True, help="Translated chunk path (fr_chunks).")
    parser.add_argument("--origin", required=True, help="Origin chunk path.")
    parser.add_argument(
        "--out-dir",
        default="quality_reports",
        help="Directory to write anomaly report files.",
    )
    args = parser.parse_args()

    fr_lines = load_lines(args.fr)
    origin_lines = load_lines(args.origin)

    os.makedirs(args.out_dir, exist_ok=True)
    report_name = os.path.splitext(os.path.basename(args.fr))[0] + "_breaks.txt"
    report_path = os.path.join(args.out_dir, report_name)

    anomalies = []

    if len(fr_lines) != len(origin_lines):
        anomalies.append(
            f"Line count mismatch: origin={len(origin_lines)} fr={len(fr_lines)}"
        )

    for idx, (o_line, f_line) in enumerate(
        zip_longest(origin_lines, fr_lines, fillvalue=None), start=1
    ):
        if o_line is None or f_line is None:
            anomalies.append(f"Line {idx}: missing counterpart (origin={o_line}, fr={f_line})")
            continue

        # Ignore offset prefix when checking lengths/breaks
        _, f_text = f_line.split(":", 1)
        _, o_text = o_line.split(":", 1)

        # If the translated line is identical to the origin, skip checks
        if f_text == o_text:
            continue

        o_p, o_l = count_breaks(o_line)
        f_p, f_l = count_breaks(f_line)

        if o_p != f_p:
            anomalies.append(
                f"Line {idx}: \\p count mismatch (origin={o_p}, fr={f_p})"
            )
        if o_l != f_l:
            anomalies.append(
                f"Line {idx}: \\l count mismatch (origin={o_l}, fr={f_l})"
            )

        if has_double_n(f_text) and not has_double_n(o_text):
            anomalies.append(f"Line {idx}: consecutive \\n found in fr, not in origin")

        # Check visible length between control codes (skip gibberish/unknown strings)
        if "{UNKNOWN_STR}" not in f_text:
            parts = re.split(r"(\\[pnl])", f_text)
            seg = ""
            for part in parts:
                if part in ("\\p", "\\n", "\\l"):
                    if seg:
                        seg_len = visible_length(seg)
                        if seg_len > 36:
                            anomalies.append(
                                f"Line {idx}: segment too long ({seg_len}>36) -> {seg}"
                            )
                        seg = ""
                else:
                    seg += part
            if seg:
                seg_len = visible_length(seg)
                if seg_len > 36:
                    anomalies.append(
                        f"Line {idx}: segment too long ({seg_len}>36) -> {seg}"
                    )

    with open(report_path, "w", encoding="utf-8") as out:
        if anomalies:
            out.write("\n".join(anomalies))
        else:
            out.write("No anomalies detected.\n")


if __name__ == "__main__":
    main()
