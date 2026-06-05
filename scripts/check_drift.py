#!/usr/bin/env python3
"""
Flag drift between the LaTeX source-of-truth tables and the website JSON.

Re-parses the .tex tables and compares the canonical taxonomy fields
(representation, motion, prior, inputCondition, trainingStrategy,
interactionType) against each mapped data/<file>.json. Reports any mismatch
and any table row that has no website file.

Exit code 1 if drift is found (suitable for CI / pre-commit).

Usage:  python scripts/check_drift.py
"""

import json
import os
import sys

import tex_lib as T

FIELDS = ["representation", "motion", "prior", "inputCondition",
          "trainingStrategy", "interactionType"]


def main():
    t1, t2 = T.parse_all_tables()
    drift = []
    missing = []
    for raw in t1 + t2:
        norm = T.normalized_row(raw)
        stem = T.BIBKEY_TO_FILE.get(norm["bibkey"])
        if not stem:
            missing.append((norm["bibkey"], norm["method"]))
            continue
        path = T.data_path(stem)
        if not os.path.exists(path):
            missing.append((norm["bibkey"], norm["method"] + " (file absent)"))
            continue
        with open(path, encoding="utf-8") as fh:
            paper = json.load(fh)
        for f in FIELDS:
            if f not in norm:
                continue
            want = norm[f]
            got = paper.get(f, [] if isinstance(want, list) else "")
            if want != got:
                drift.append((stem, f, got, want))

    if missing:
        print("Table rows with no website file:")
        for bib, method in missing:
            print(f"  {bib}: {method}")
    if drift:
        print("Drift (file: field  json != tex):")
        for stem, f, got, want in drift:
            print(f"  {stem}: {f}  {got!r} != {want!r}")
    if not missing and not drift:
        print("No drift: website JSON matches the LaTeX tables.")
        return
    sys.exit(1)


if __name__ == "__main__":
    main()
