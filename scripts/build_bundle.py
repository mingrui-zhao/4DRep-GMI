#!/usr/bin/env python3
"""
Compile the per-paper data/*.json files into a single consolidated bundle
data/papers.json so the website loads everything in ONE request instead of
~80 sequential fetches.

Also:
  * validates each paper against a schema (required fields + controlled
    vocabularies for representation / motion / prior / training / interaction);
  * stamps a content-hash version into data/papers.json and into index.html
    (the `DATA_VERSION` constant) for cache-busting.

The per-paper JSON files remain the editable source of truth; papers.json is a
generated artifact. Run this after editing any data/*.json or after
process_submission.py / tex_sync.py.

Usage:
  python scripts/build_bundle.py            # build + stamp
  python scripts/build_bundle.py --check    # validate only, no writes (CI)
"""

import glob
import hashlib
import json
import os
import re
import sys

import tex_lib as T

EXCLUDE = {"paper-list.json", "papers.json", "template_paper.json"}

REQUIRED_FIELDS = ["title"]
# Fields that, if present, must be drawn from a controlled vocabulary.
LIST_VOCAB = {
    "representation": set(T.GEOMETRY_VOCAB),
    "motion": set(T.MOTION_VOCAB),
}
PRIOR_TOKENS = set(T.PRIOR_VOCAB)
TRAINING_TOKENS = set(T.TRAINING_VOCAB)
INTERACTION_TYPES = set(T.INTERACTION_TYPE_VOCAB)


def as_list(v):
    if v is None or v == "":
        return []
    return v if isinstance(v, list) else [v]


def validate(stem, p):
    """Return list of human-readable problems for one paper."""
    errs = []
    for f in REQUIRED_FIELDS:
        if not p.get(f):
            errs.append(f"missing required field '{f}'")
    # Method papers (not a survey/dataset) must carry a geometry.
    if not p.get("survey") and not p.get("dataset") and not p.get("representation"):
        errs.append("method paper missing 'representation'")
    for field, vocab in LIST_VOCAB.items():
        for tok in as_list(p.get(field)):
            if tok not in vocab:
                errs.append(f"{field} value '{tok}' not in controlled vocabulary")
    # prior: '+'-separated tokens from PRIOR_VOCAB
    prior = (p.get("prior") or "").strip()
    if prior:
        for tok in re.split(r"\+", prior):
            if tok.strip() and tok.strip() not in PRIOR_TOKENS:
                errs.append(f"prior token '{tok.strip()}' not in controlled vocabulary")
    train = (p.get("trainingStrategy") or "").strip()
    if train and train not in TRAINING_TOKENS:
        errs.append(f"trainingStrategy '{train}' not in controlled vocabulary")
    itype = (p.get("interactionType") or "").strip()
    if itype and itype not in INTERACTION_TYPES:
        errs.append(f"interactionType '{itype}' not in controlled vocabulary")
    if p.get("year") and not re.fullmatch(r"\d{4}", str(p["year"])):
        errs.append(f"year '{p['year']}' is not a 4-digit string")
    return errs


def load_papers():
    papers, problems = [], {}
    for path in sorted(glob.glob(os.path.join(T.DATA_DIR, "*.json"))):
        name = os.path.basename(path)
        if name in EXCLUDE:
            continue
        with open(path, encoding="utf-8") as fh:
            try:
                p = json.load(fh)
            except json.JSONDecodeError as e:
                problems[name] = [f"invalid JSON: {e}"]
                continue
        stem = name[:-5]
        p.setdefault("filename", name)
        # Derive the teaser path at build time, preferring the optimized WebP,
        # then a submitted png/jpg, else default to .webp.
        if not p.get("thumbnailUrl"):
            for ext in (".webp", ".png", ".jpg", ".jpeg"):
                if os.path.exists(os.path.join(T.REPO, "images", stem + ext)):
                    p["thumbnailUrl"] = f"images/{stem}{ext}"
                    break
            else:
                p["thumbnailUrl"] = f"images/{stem}.webp"
        errs = validate(stem, p)
        if errs:
            problems[name] = errs
        papers.append(p)
    return papers, problems


def stamp_index(version):
    """Rewrite the DATA_VERSION constant in index.html."""
    idx = os.path.join(T.REPO, "index.html")
    with open(idx, encoding="utf-8") as fh:
        html = fh.read()
    new = re.sub(r'(const\s+DATA_VERSION\s*=\s*")[^"]*(")',
                 rf'\g<1>{version}\g<2>', html)
    if new != html:
        with open(idx, "w", encoding="utf-8") as fh:
            fh.write(new)
        return True
    return False


def main():
    check_only = "--check" in sys.argv
    papers, problems = load_papers()

    if problems:
        print("Schema validation problems:")
        for name, errs in sorted(problems.items()):
            for e in errs:
                print(f"  {name}: {e}")
        if check_only:
            sys.exit(1)
        print("(continuing build; fix the above before deploying)\n")

    # Stable order: newest first, then title.
    papers.sort(key=lambda p: (-int(p.get("year") or 0),
                               str(p.get("title", "")).lower()))

    payload = {"count": len(papers), "papers": papers}
    body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    version = hashlib.sha1(body.encode("utf-8")).hexdigest()[:10]
    payload = {"version": version, "count": len(papers), "papers": papers}

    out = os.path.join(T.DATA_DIR, "papers.json")
    if check_only:
        print(f"[check] {len(papers)} papers OK; would-be version {version}")
        return
    with open(out, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
    stamped = stamp_index(version)
    print(f"Wrote {out} ({len(papers)} papers), version={version}"
          f"{' + stamped index.html' if stamped else ''}")


if __name__ == "__main__":
    main()
