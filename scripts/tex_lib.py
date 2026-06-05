#!/usr/bin/env python3
"""
Shared library for syncing the 4D-survey website JSON with the LaTeX
source-of-truth tables in the sibling repo `-CGF26-4DRepGMI`.

This module is the single place that knows how to:
  * parse the two summary tables (`paper_table_unstruc.tex`, `paper_table_interaction.tex`)
  * normalize LaTeX taxonomy vocabulary -> website display vocabulary
  * map a LaTeX \\cite{bibkey} to the website data/<file>.json

It is imported by:
  * tex_sync.py     - one-time/idempotent sync of tags into the per-paper JSON
  * check_drift.py  - reports drift between the .tex tables and the JSON
  * build_bundle.py - (indirectly, via the controlled vocabularies)
"""

import os
import re

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)                      # 4DRep-GMI (website repo)
DATA_DIR = os.path.join(REPO, "data")

# The LaTeX source-of-truth lives in a sibling repo. Allow override via env.
TEX_DIR = os.environ.get(
    "TEX_DIR",
    os.path.normpath(os.path.join(REPO, "..", "-CGF26-4DRepGMI", "tables")),
)
TABLE1 = os.path.join(TEX_DIR, "paper_table_unstruc.tex")
TABLE2 = os.path.join(TEX_DIR, "paper_table_interaction.tex")

# ---------------------------------------------------------------------------
# Controlled vocabularies (website display vocabulary)
# ---------------------------------------------------------------------------
GEOMETRY_VOCAB = [
    "Mesh", "Point Cloud", "NeRF", "Gaussian Splatting",
    "Template", "Part", "Graph", "Image", "Voxel",
]
MOTION_VOCAB = [
    "Articulation", "Deformation", "Tracking",
    "Space-Time", "Per frame", "Scene Graph",
]
PRIOR_VOCAB = ["FM", "TD", "Input", "LLM", "Human"]
TRAINING_VOCAB = ["Per-scene", "Feed-forward", "Hybrid"]
INTERACTION_ASPECT_VOCAB = ["pose", "contact", "affordance", "physical-regulation"]
INTERACTION_TYPE_VOCAB = [
    "HOI", "HSI", "HHI", "Hand-O", "Hand-Hand", "two-hand",
    "OOI", "HOI/HSI", "Affordance prediction",
]

# ---------------------------------------------------------------------------
# Normalization maps: LaTeX token -> website display token
# ---------------------------------------------------------------------------
_GEOM_MAP = {
    "mesh": "Mesh",
    "point cloud": "Point Cloud",
    "nerf": "NeRF",
    "gaussian primitive": "Gaussian Splatting",
    "gaussian primitives": "Gaussian Splatting",
    "gaussian splatting": "Gaussian Splatting",
    "template": "Template",
    "part": "Part",
    "graph": "Graph",
    "image": "Image",
    "voxel": "Voxel",
}
_MOTION_MAP = {
    "art": "Articulation",
    "df": "Deformation",
    "trk": "Tracking",
    "st": "Space-Time",
    "pf": "Per frame",
    "scene graph": "Scene Graph",
    "--": None,
    "-": None,
    "": None,
}
# Interaction icon macro -> structured aspect label
ICON_MAP = {
    "iPose": "pose",
    "iCont": "contact",
    "iAfd": "affordance",
    "iPReg": "physical-regulation",
}


def _split_compound(value):
    """Split a compound LaTeX cell like 'Template/Gaussian primitive' or
    'PF+TRK' on both '/' and '+', preserving order."""
    return [p.strip() for p in re.split(r"[/+]", value) if p.strip()]


def normalize_geometry(cell):
    """LaTeX Geometry cell -> ordered list of website geometry tokens."""
    out = []
    for tok in _split_compound(cell):
        mapped = _GEOM_MAP.get(tok.lower())
        if mapped is None:
            raise ValueError(f"Unknown geometry token: {tok!r} (cell={cell!r})")
        if mapped not in out:
            out.append(mapped)
    return out


def normalize_motion(cell):
    """LaTeX Motion cell -> ordered list of website motion tokens (may be empty)."""
    cell = cell.strip()
    if cell in ("--", "-", ""):
        return []
    out = []
    for tok in _split_compound(cell):
        key = tok.lower()
        if key not in _MOTION_MAP:
            raise ValueError(f"Unknown motion token: {tok!r} (cell={cell!r})")
        mapped = _MOTION_MAP[key]
        if mapped and mapped not in out:
            out.append(mapped)
    return out


def normalize_training(cell):
    """Canonicalize training-strategy casing (e.g. 'Per-Scene' -> 'Per-scene')."""
    c = cell.strip()
    low = c.lower()
    canon = {"per-scene": "Per-scene", "feed-forward": "Feed-forward", "hybrid": "Hybrid"}
    return canon.get(low, c)


def normalize_prior(cell):
    """Prior cell kept verbatim (cascades like 'FM+TD' are meaningful)."""
    c = cell.strip()
    return "" if c in ("--", "-", "") else c


# Canonicalize input-condition variants that mean the same thing (case / hyphen /
# token order), so equivalent values don't appear as separate tags.
_INPUT_CANON = {
    "few image": "Few-Image",
    "few-image": "Few-Image",
    "image+text": "Text+Image",   # same modalities; canonical order Text+Image
}


def normalize_input(cell):
    """Input-condition cell, with equivalent variants deduplicated."""
    c = cell.strip()
    if c in ("--", "-", ""):
        return ""
    return _INPUT_CANON.get(c.lower(), c)


def parse_interaction_aspects(cell):
    """Parse the Interaction column (e.g. '\\iPose~\\iCont~\\iPReg') into
    structured aspect labels. (Currently informational only.)"""
    aspects = []
    for macro in re.findall(r"\\(\w+)", cell):
        if macro in ICON_MAP and ICON_MAP[macro] not in aspects:
            aspects.append(ICON_MAP[macro])
    return aspects


# ---------------------------------------------------------------------------
# Table parsing
# ---------------------------------------------------------------------------
_ROW_RE = re.compile(r"(.*?)~?\\cite\{([^}]+)\}\s*&(.*)")


def _parse_table(path, has_interaction):
    """Parse one summary table -> list of row dicts.

    Each row: {method, bibkey, geometry(raw), motion(raw), prior(raw),
               input(raw), training(raw), [interaction(raw), type(raw)]}
    """
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped.startswith("%") or "\\cite{" not in stripped:
                continue
            stripped = stripped.rstrip("\\").strip()
            m = _ROW_RE.match(stripped)
            if not m:
                continue
            method = m.group(1).strip()
            bibkey = m.group(2).strip()
            cells = [c.strip() for c in m.group(3).split("&")]
            # Table 1: Geometry, Motion, Prior, Input, Training  (5 cells)
            # Table 2: Geometry, Motion, Prior, Input, Training, Interaction, Type (7)
            row = {
                "method": method,
                "bibkey": bibkey,
                "geometry": cells[0] if len(cells) > 0 else "",
                "motion": cells[1] if len(cells) > 1 else "",
                "prior": cells[2] if len(cells) > 2 else "",
                "input": cells[3] if len(cells) > 3 else "",
                "training": cells[4] if len(cells) > 4 else "",
            }
            if has_interaction:
                row["interaction"] = cells[5] if len(cells) > 5 else ""
                row["type"] = cells[6] if len(cells) > 6 else ""
            rows.append(row)
    return rows


def parse_all_tables():
    """Return (table1_rows, table2_rows)."""
    return _parse_table(TABLE1, False), _parse_table(TABLE2, True)


def normalized_row(row):
    """Apply vocabulary normalization to a raw parsed row."""
    out = {
        "bibkey": row["bibkey"],
        "method": row["method"],
        "representation": normalize_geometry(row["geometry"]),
        "motion": normalize_motion(row["motion"]),
        "prior": normalize_prior(row["prior"]),
        "inputCondition": normalize_input(row["input"]),
        "trainingStrategy": normalize_training(row["training"]),
    }
    if "interaction" in row:
        out["interactionAspects"] = parse_interaction_aspects(row["interaction"])
        out["interactionType"] = row["type"].strip()
    return out


# ---------------------------------------------------------------------------
# bibkey -> website filename mapping (the one hand-authored artifact, since
# method display names differ between the two repos)
# ---------------------------------------------------------------------------
BIBKEY_TO_FILE = {
    # --- Table 1 (all already on the website) ---
    "TextMesh4D": "textmesh4d", "chen2025v2m4": "v2m4", "song2025puppeteer": "puppeteer",
    "wu2025animateanymesh": "animateanymesh", "Song_2025_CVPR": "magicarticulate",
    "li2024dreammesh4d": "dreammesh4d", "liu2025riganything": "riganything",
    "zheng2023neuralpci": "neuralpci", "cut3r": "cut3r", "zhang2024monst3r": "monst3r",
    "feng2025st4rtrack": "st4rtrack", "peng2024papr": "paprinmotion", "yan2020rpm": "rpmnet",
    "singer2023text": "mav3d", "bahmani20244dfy": "4d-fy", "jiang2023consistent4d": "consistent4D",
    "xie_sv4d_2024": "sv4d", "zheng_unified_2024": "dream-in-4d", "zhao2023animate124": "animate124",
    "zhang_4diffusion_2024": "4diffusion", "gan2023v4d": "v4d", "park2023temporal": "tempint",
    "yin_4dgen_2023": "4dgen", "duan20244d": "4drotor", "Wu_2024_CVPR": "4dgs",
    "luiten2024dynamic": "dyn3dgs", "wu2025cat4d": "cat4d", "ren2023dreamgaussian4d": "dg4d",
    "ma20254d": "4dlrm", "ren2024l4gm": "l4gm", "zeng2024stag4d": "stag4d",
    "zhao2024genxd": "genxd", "lei2024mosca": "mosca", "stearns2024dynamic": "gaussianmarble",
    "nag20252": "in24d", "liu2025free4d": "free4d", "sun_eg4d_2024": "eg4d",
    "huang2025mvtokenflow": "mvtokenflow", "yu_4real_2024": "4real", "wu_sc4d_2024": "sc4d",
    "PhysAavatar24": "physavatar", "liao2024tada": "tada", "gat2025anytop": "anytop",
    "chen2025human3r": "human3r", "taubner2025mvp4d": "mvp4d", "liu2025avatarartist": "avatarartist",
    "pang_disco4d_2024": "disco4d", "taubner2025cap4d": "cap4d", "guo2023vid2avatar": "vid2avatar",
    "liu2023paris": "paris", "guo2025articulatedgs": "articulatedgs", "liu2025artgs": "artgs",
    "zhang2025sp4d": "sp4d", "qiu2025articulate": "articulateanymesh", "liu2024singapo": "singapo",
    "goyal2025geopard": "geopard", "gao2025meshart": "meshart", "3DDSG": "3dsg",
    "4DPanoSceneGraph": "4dpsg", "wu2025learning": "psgllm",
    # --- Table 2 ---
    "cao_avatargo_2024": "avatargo",                 # already on the website
    "li2024zerohsi": "zerohsi", "pokhariya2024manus": "manus",
    "wen2025reconstructing": "open3dhoi", "liu2023hosnerf": "hosnerf",
    "guo2023handnerf": "handnerf", "on2025bigs": "bigs",
    "NeuralDescriptorFields": "ndf", "Intergen": "intergen", "POSA": "posa",
    "corona2020ganhand": "ganhand", "3DAffordanceNet": "3daffordancenet",
    "AffordanceLLM": "affordancellm", "kulkarni2024nifty": "nifty",
    "xu2023interdiff": "interdiff", "FORCEIntuitivePhysics": "force",
}


def data_path(stem):
    return os.path.join(DATA_DIR, stem + ".json")
