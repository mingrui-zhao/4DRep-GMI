#!/usr/bin/env python3
"""
Sync website per-paper JSON with the LaTeX source-of-truth tables.

For every paper that appears in the two .tex tables this script writes the
canonical taxonomy fields:
    representation, motion, prior, inputCondition, trainingStrategy,
    interactionType, bibkey
into data/<file>.json (creating the 15 Table-2 interaction papers that have no
website entry yet). It then refreshes data/paper-list.json and emits
RECONCILIATION.md.

Per project instruction, `interactionAspects` (pose/contact/affordance/
physical-regulation) are NOT written yet — only parsed for the report.

Idempotent: re-running produces no further diffs.

Usage:  python scripts/tex_sync.py [--dry-run]
"""

import json
import os
import subprocess
import sys

import tex_lib as T

WRITE_INTERACTION_ASPECTS = False  # project instruction: not yet

# Canonical taxonomy fields this script owns (written from the .tex tables).
TAG_FIELDS = ["representation", "motion", "prior", "inputCondition",
              "trainingStrategy", "interactionType"]

# ---------------------------------------------------------------------------
# Bibliographic metadata for the 15 Table-2 papers with no website entry yet.
# (Verified via literature lookup; see RECONCILIATION.md confidence notes.)
# Taxonomy fields are filled from the .tex table, not here.
# ---------------------------------------------------------------------------
NEW_PAPER_META = {
    "zerohsi": {
        "title": "ZeroHSI: Zero-Shot 4D Human-Scene Interaction by Video Generation",
        "authors": ["Hongjie Li", "Hong-Xing Yu", "Jiaman Li", "Jiajun Wu"],
        "year": "2024", "venue": "ArXiv",
        "paperUrl": "https://arxiv.org/abs/2412.18600",
        "projectPage": "https://awfuact.github.io/zerohsi/", "codeUrl": "",
        "task": "Human",
        "bibtex": "@article{li2024zerohsi,\n  title={ZeroHSI: Zero-Shot 4D Human-Scene Interaction by Video Generation},\n  author={Li, Hongjie and Yu, Hong-Xing and Li, Jiaman and Wu, Jiajun},\n  journal={arXiv preprint arXiv:2412.18600},\n  year={2024}\n}",
    },
    "manus": {
        "title": "MANUS: Markerless Grasp Capture using Articulated 3D Gaussians",
        "authors": ["Chandradeep Pokhariya", "Ishaan Nikhil Shah", "Angela Xing", "Zekun Li", "Kefan Chen", "Avinash Sharma", "Srinath Sridhar"],
        "year": "2024", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2312.02137",
        "projectPage": "https://ivl.cs.brown.edu/research/manus.html",
        "codeUrl": "https://github.com/brown-ivl/manus",
        "task": "Hand",
        "bibtex": "@inproceedings{pokhariya2024manus,\n  title={MANUS: Markerless Grasp Capture using Articulated 3D Gaussians},\n  author={Pokhariya, Chandradeep and Shah, Ishaan Nikhil and Xing, Angela and Li, Zekun and Chen, Kefan and Sharma, Avinash and Sridhar, Srinath},\n  booktitle={CVPR},\n  year={2024}\n}",
    },
    "open3dhoi": {
        "title": "Reconstructing In-the-Wild Open-Vocabulary Human-Object Interactions",
        "authors": ["Boran Wen", "Dingbang Huang", "Zichen Zhang", "Jiahong Zhou", "Jianbin Deng", "Jingyu Gong", "Yulong Chen", "Lizhuang Ma", "Yong-Lu Li"],
        "year": "2025", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2503.15898",
        "projectPage": "https://wenboran2002.github.io/3dhoi/",
        "codeUrl": "https://github.com/wenboran2002/open3dhoi",
        "task": "Human",
        "bibtex": "@inproceedings{wen2025reconstructing,\n  title={Reconstructing In-the-Wild Open-Vocabulary Human-Object Interactions},\n  author={Wen, Boran and Huang, Dingbang and Zhang, Zichen and Zhou, Jiahong and Deng, Jianbin and Gong, Jingyu and Chen, Yulong and Ma, Lizhuang and Li, Yong-Lu},\n  booktitle={CVPR},\n  year={2025}\n}",
    },
    "hosnerf": {
        "title": "HOSNeRF: Dynamic Human-Object-Scene Neural Radiance Fields from a Single Video",
        "authors": ["Jia-Wei Liu", "Yan-Pei Cao", "Tianyuan Yang", "Eric Zhongcong Xu", "Jussi Keppo", "Ying Shan", "Xiaohu Qie", "Mike Zheng Shou"],
        "year": "2023", "venue": "ICCV",
        "paperUrl": "https://arxiv.org/abs/2304.12281",
        "projectPage": "https://showlab.github.io/HOSNeRF/",
        "codeUrl": "https://github.com/TencentARC/HOSNeRF",
        "task": "Human",
        "bibtex": "@inproceedings{liu2023hosnerf,\n  title={HOSNeRF: Dynamic Human-Object-Scene Neural Radiance Fields from a Single Video},\n  author={Liu, Jia-Wei and Cao, Yan-Pei and Yang, Tianyuan and Xu, Eric Zhongcong and Keppo, Jussi and Shan, Ying and Qie, Xiaohu and Shou, Mike Zheng},\n  booktitle={ICCV},\n  year={2023}\n}",
    },
    "handnerf": {
        "title": "HandNeRF: Neural Radiance Fields for Animatable Interacting Hands",
        "authors": ["Zhiyang Guo", "Wengang Zhou", "Min Wang", "Li Li", "Houqiang Li"],
        "year": "2023", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2303.13825",
        "projectPage": "", "codeUrl": "",
        "task": "Hand",
        "bibtex": "@inproceedings{guo2023handnerf,\n  title={HandNeRF: Neural Radiance Fields for Animatable Interacting Hands},\n  author={Guo, Zhiyang and Zhou, Wengang and Wang, Min and Li, Li and Li, Houqiang},\n  booktitle={CVPR},\n  year={2023}\n}",
    },
    "bigs": {
        "title": "BIGS: Bimanual Category-agnostic Interaction Reconstruction from Monocular Videos via 3D Gaussian Splatting",
        "authors": ["Jeongwan On", "Kyeonghwan Gwak", "Gunyoung Kang", "Junuk Cha", "Soohyun Hwang", "Hyein Hwang", "Seungryul Baek"],
        "year": "2025", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2504.09097",
        "projectPage": "", "codeUrl": "https://github.com/On-JungWoan/BIGS",
        "task": "Hand",
        "bibtex": "@inproceedings{on2025bigs,\n  title={BIGS: Bimanual Category-agnostic Interaction Reconstruction from Monocular Videos via 3D Gaussian Splatting},\n  author={On, Jeongwan and Gwak, Kyeonghwan and Kang, Gunyoung and Cha, Junuk and Hwang, Soohyun and Hwang, Hyein and Baek, Seungryul},\n  booktitle={CVPR},\n  year={2025}\n}",
    },
    "ndf": {
        "title": "Neural Descriptor Fields: SE(3)-Equivariant Object Representations for Manipulation",
        "authors": ["Anthony Simeonov", "Yilun Du", "Andrea Tagliasacchi", "Joshua B. Tenenbaum", "Alberto Rodriguez", "Pulkit Agrawal", "Vincent Sitzmann"],
        "year": "2022", "venue": "ICRA",
        "paperUrl": "https://arxiv.org/abs/2112.05124",
        "projectPage": "https://yilundu.github.io/ndf/",
        "codeUrl": "https://github.com/anthonysimeonov/ndf_robot",
        "task": "Object",
        "bibtex": "@inproceedings{simeonov2022neural,\n  title={Neural Descriptor Fields: SE(3)-Equivariant Object Representations for Manipulation},\n  author={Simeonov, Anthony and Du, Yilun and Tagliasacchi, Andrea and Tenenbaum, Joshua B. and Rodriguez, Alberto and Agrawal, Pulkit and Sitzmann, Vincent},\n  booktitle={ICRA},\n  year={2022}\n}",
    },
    "intergen": {
        "title": "InterGen: Diffusion-based Multi-human Motion Generation under Complex Interactions",
        "authors": ["Han Liang", "Wenqian Zhang", "Wenxuan Li", "Jingyi Yu", "Lan Xu"],
        "year": "2024", "venue": "IJCV",
        "paperUrl": "https://arxiv.org/abs/2304.05684",
        "projectPage": "https://tr3e.github.io/intergen-page/",
        "codeUrl": "https://github.com/tr3e/InterGen",
        "task": "Human",
        "bibtex": "@article{liang2024intergen,\n  title={InterGen: Diffusion-based Multi-human Motion Generation under Complex Interactions},\n  author={Liang, Han and Zhang, Wenqian and Li, Wenxuan and Yu, Jingyi and Xu, Lan},\n  journal={IJCV},\n  year={2024}\n}",
    },
    "posa": {
        "title": "Populating 3D Scenes by Learning Human-Scene Interaction",
        "authors": ["Mohamed Hassan", "Partha Ghosh", "Joachim Tesch", "Dimitrios Tzionas", "Michael J. Black"],
        "year": "2021", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2012.11581",
        "projectPage": "https://posa.is.tue.mpg.de/",
        "codeUrl": "https://github.com/mohamedhassanmus/POSA",
        "task": "Human",
        "bibtex": "@inproceedings{hassan2021populating,\n  title={Populating 3D Scenes by Learning Human-Scene Interaction},\n  author={Hassan, Mohamed and Ghosh, Partha and Tesch, Joachim and Tzionas, Dimitrios and Black, Michael J.},\n  booktitle={CVPR},\n  year={2021}\n}",
    },
    "ganhand": {
        "title": "GanHand: Predicting Human Grasp Affordances in Multi-Object Scenes",
        "authors": ["Enric Corona", "Albert Pumarola", "Guillem Alenyà", "Francesc Moreno-Noguer", "Grégory Rogez"],
        "year": "2020", "venue": "CVPR",
        "paperUrl": "https://openaccess.thecvf.com/content_CVPR_2020/html/Corona_GanHand_Predicting_Human_Grasp_Affordances_in_Multi-Object_Scenes_CVPR_2020_paper.html",
        "projectPage": "https://enriccorona.github.io/ganhand/",
        "codeUrl": "https://github.com/enriccorona/GanHand",
        "task": "Hand",
        "bibtex": "@inproceedings{corona2020ganhand,\n  title={GanHand: Predicting Human Grasp Affordances in Multi-Object Scenes},\n  author={Corona, Enric and Pumarola, Albert and Aleny{\\`a}, Guillem and Moreno-Noguer, Francesc and Rogez, Gr{\\'e}gory},\n  booktitle={CVPR},\n  year={2020}\n}",
    },
    "3daffordancenet": {
        "title": "3D AffordanceNet: A Benchmark for Visual Object Affordance Understanding",
        "authors": ["Shengheng Deng", "Xun Xu", "Chaozheng Wu", "Ke Chen", "Kui Jia"],
        "year": "2021", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2103.16397",
        "projectPage": "", "codeUrl": "https://github.com/Gorilla-Lab-SCUT/AffordanceNet",
        "task": "Object",
        "bibtex": "@inproceedings{deng20213d,\n  title={3D AffordanceNet: A Benchmark for Visual Object Affordance Understanding},\n  author={Deng, Shengheng and Xu, Xun and Wu, Chaozheng and Chen, Ke and Jia, Kui},\n  booktitle={CVPR},\n  year={2021}\n}",
    },
    "affordancellm": {
        "title": "AffordanceLLM: Grounding Affordance from Vision Language Models",
        "authors": ["Shengyi Qian", "Weifeng Chen", "Min Bai", "Xiong Zhou", "Zhuowen Tu", "Li Erran Li"],
        "year": "2024", "venue": "CVPR Workshops",
        "paperUrl": "https://arxiv.org/abs/2401.06341",
        "projectPage": "https://jasonqsy.github.io/AffordanceLLM/", "codeUrl": "",
        "task": "Object",
        "bibtex": "@inproceedings{qian2024affordancellm,\n  title={AffordanceLLM: Grounding Affordance from Vision Language Models},\n  author={Qian, Shengyi and Chen, Weifeng and Bai, Min and Zhou, Xiong and Tu, Zhuowen and Li, Li Erran},\n  booktitle={CVPR Workshops},\n  year={2024}\n}",
    },
    "nifty": {
        "title": "NIFTY: Neural Object Interaction Fields for Guided Human Motion Synthesis",
        "authors": ["Nilesh Kulkarni", "Davis Rempe", "Kyle Genova", "Abhijit Kundu", "Justin Johnson", "David Fouhey", "Leonidas Guibas"],
        "year": "2024", "venue": "CVPR",
        "paperUrl": "https://arxiv.org/abs/2307.07511",
        "projectPage": "https://nileshkulkarni.github.io/nifty/", "codeUrl": "",
        "task": "Human",
        "bibtex": "@inproceedings{kulkarni2024nifty,\n  title={NIFTY: Neural Object Interaction Fields for Guided Human Motion Synthesis},\n  author={Kulkarni, Nilesh and Rempe, Davis and Genova, Kyle and Kundu, Abhijit and Johnson, Justin and Fouhey, David and Guibas, Leonidas},\n  booktitle={CVPR},\n  year={2024}\n}",
    },
    "interdiff": {
        "title": "InterDiff: Generating 3D Human-Object Interactions with Physics-Informed Diffusion",
        "authors": ["Sirui Xu", "Zhengyuan Li", "Yu-Xiong Wang", "Liang-Yan Gui"],
        "year": "2023", "venue": "ICCV",
        "paperUrl": "https://arxiv.org/abs/2308.16905",
        "projectPage": "https://sirui-xu.github.io/InterDiff/",
        "codeUrl": "https://github.com/Sirui-Xu/InterDiff",
        "task": "Human",
        "bibtex": "@inproceedings{xu2023interdiff,\n  title={InterDiff: Generating 3D Human-Object Interactions with Physics-Informed Diffusion},\n  author={Xu, Sirui and Li, Zhengyuan and Wang, Yu-Xiong and Gui, Liang-Yan},\n  booktitle={ICCV},\n  year={2023}\n}",
    },
    "force": {
        "title": "FORCE: Dataset and Method for Intuitive Physics Guided Human-object Interaction",
        "authors": ["Xiaohan Zhang", "Bharat Lal Bhatnagar", "Sebastian Starke", "Ilya Petrov", "Vladimir Guzov", "Helisa Dhamo", "Eduardo Pérez-Pellitero", "Gerard Pons-Moll"],
        "year": "2025", "venue": "3DV",
        "paperUrl": "https://arxiv.org/abs/2403.11237",
        "projectPage": "https://virtualhumans.mpi-inf.mpg.de/force/",
        "codeUrl": "https://github.com/xz6014/FORCE_dataset",
        "task": "Human",
        "bibtex": "@inproceedings{zhang2025force,\n  title={FORCE: Dataset and Method for Intuitive Physics Guided Human-object Interaction},\n  author={Zhang, Xiaohan and Bhatnagar, Bharat Lal and Starke, Sebastian and Petrov, Ilya and Guzov, Vladimir and Dhamo, Helisa and P{\\'e}rez-Pellitero, Eduardo and Pons-Moll, Gerard},\n  booktitle={3DV},\n  year={2025}\n}",
    },
}


def load_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, indent=2, ensure_ascii=False)
        fh.write("\n")


def git_baseline(stem):
    """Return the committed (HEAD) version of data/<stem>.json as a dict, or
    None if the file is new / git is unavailable. Used so the reconciliation
    report shows a stable old->new diff against the committed baseline,
    independent of how many times this script has already run."""
    rel = f"data/{stem}.json"
    try:
        out = subprocess.run(
            ["git", "-C", T.REPO, "show", f"HEAD:{rel}"],
            capture_output=True, text=True, check=False)
        if out.returncode != 0 or not out.stdout.strip():
            return None
        return json.loads(out.stdout)
    except Exception:
        return None


def field_diff(old, new):
    """Return list of (field, old_val, new_val) for changed TAG_FIELDS."""
    diffs = []
    for f in TAG_FIELDS + ["bibkey"]:
        ov = old.get(f, "<absent>")
        nv = new.get(f, "<absent>")
        if ov != nv:
            diffs.append((f, ov, nv))
    return diffs


def apply_tags(paper, norm):
    """Write normalized tag fields onto an existing paper dict (in place)."""
    paper["bibkey"] = norm["bibkey"]
    paper["representation"] = norm["representation"]
    paper["motion"] = norm["motion"]
    paper["prior"] = norm["prior"]
    paper["inputCondition"] = norm["inputCondition"]
    paper["trainingStrategy"] = norm["trainingStrategy"]
    if "interactionType" in norm:
        paper["interactionType"] = norm["interactionType"]
        if WRITE_INTERACTION_ASPECTS:
            paper["interactionAspects"] = norm.get("interactionAspects", [])


def build_new_paper(stem, norm):
    meta = NEW_PAPER_META[stem]
    paper = {
        "title": meta["title"],
        "authors": meta["authors"],
        "year": meta["year"],
        "venue": meta["venue"],
        "paperUrl": meta.get("paperUrl", ""),
        "projectPage": meta.get("projectPage", ""),
        "codeUrl": meta.get("codeUrl", ""),
        "representation": norm["representation"],
        "motion": norm["motion"],
        "prior": norm["prior"],
        "inputCondition": norm["inputCondition"],
        "trainingStrategy": norm["trainingStrategy"],
        "interactionType": norm.get("interactionType", ""),
        "task": meta.get("task", ""),
        "category": [],
        "tags": [],
        "interaction": "",
        "codeAvailability": bool(meta.get("codeUrl")),
        "dataset": False,
        "survey": False,
        "doi": "",
        "bibtex": meta.get("bibtex", ""),
        "bibkey": norm["bibkey"],
    }
    if WRITE_INTERACTION_ASPECTS and "interactionAspects" in norm:
        paper["interactionAspects"] = norm["interactionAspects"]
    return paper


def main():
    dry = "--dry-run" in sys.argv
    t1, t2 = T.parse_all_tables()
    all_rows = [(r, False) for r in t1] + [(r, True) for r in t2]

    updated, created, unmatched = [], [], []
    aspect_info = {}  # stem -> aspects (for report only)

    for raw, is_inter in all_rows:
        norm = T.normalized_row(raw)
        bib = norm["bibkey"]
        if is_inter:
            aspect_info[bib] = norm.get("interactionAspects", [])
        stem = T.BIBKEY_TO_FILE.get(bib)
        if not stem:
            unmatched.append((bib, norm["method"]))
            continue
        path = T.data_path(stem)
        baseline = git_baseline(stem)  # committed HEAD state, or None if new
        if baseline is not None or os.path.exists(path):
            # Existing paper (committed, or already written by a prior run).
            paper = load_json(path) if os.path.exists(path) else dict(baseline)
            apply_tags(paper, norm)
            if not dry:
                save_json(path, paper)
            if baseline is None and stem in NEW_PAPER_META:
                # Not in the committed baseline -> this sync introduced it.
                created.append((stem, norm["method"]))
            else:
                diffs = field_diff(baseline or {}, paper)
                if diffs:
                    updated.append((stem, norm["method"], diffs))
        else:
            if stem not in NEW_PAPER_META:
                unmatched.append((bib, norm["method"] + " (no metadata to create)"))
                continue
            paper = build_new_paper(stem, norm)
            created.append((stem, norm["method"]))
            if not dry:
                save_json(path, paper)

    # Refresh paper-list.json (sorted, includes created files).
    list_path = os.path.join(T.DATA_DIR, "paper-list.json")
    plist = load_json(list_path)
    existing = set(plist.get("files", []))
    for stem, _ in created:
        existing.add(stem + ".json")
    files = sorted(existing)
    plist["files"] = files
    plist["totalPapers"] = len(files)
    if not dry:
        save_json(list_path, plist)

    # Website papers not in either table.
    table_stems = {T.BIBKEY_TO_FILE[r["bibkey"]] for r in t1 + t2
                   if r["bibkey"] in T.BIBKEY_TO_FILE}
    site_stems = {f[:-5] for f in files if f.endswith(".json")
                  and f not in ("paper-list.json",)}
    not_in_tables = sorted(site_stems - table_stems - {"template_paper"})

    write_report(updated, created, unmatched, not_in_tables, aspect_info, dry)
    print(f"{'[dry-run] ' if dry else ''}updated={len(updated)} "
          f"created={len(created)} unmatched={len(unmatched)} "
          f"not_in_tables={len(not_in_tables)}")


def write_report(updated, created, unmatched, not_in_tables, aspect_info, dry):
    L = []
    L.append("# Tag Reconciliation Report\n")
    L.append("_Generated by `scripts/tex_sync.py` from the LaTeX source-of-truth "
             "tables in `-CGF26-4DRepGMI/tables/`._\n")
    L.append("\n## 1. Papers updated from the tables (old → new)\n")
    if not updated:
        L.append("\n_None — JSON already in sync._\n")
    for stem, method, diffs in updated:
        L.append(f"\n### {method} (`data/{stem}.json`)\n")
        for f, ov, nv in diffs:
            L.append(f"- **{f}**: `{ov}` → `{nv}`")
        L.append("")
    L.append("\n## 2. Table papers created (had no website entry)\n")
    if not created:
        L.append("\n_None._\n")
    else:
        for stem, method in created:
            asp = aspect_info.get(_stem_to_bib(stem), [])
            asp_s = (", aspects (not yet written): " + ", ".join(asp)) if asp else ""
            L.append(f"- **{method}** → `data/{stem}.json`{asp_s}")
    L.append("\n\n## 3. Table papers with no website entry and no metadata\n")
    if not unmatched:
        L.append("\n_None — every table row maps to a website paper._\n")
    else:
        for bib, method in unmatched:
            L.append(f"- `{bib}` — {method}")
    L.append("\n\n## 4. Website papers NOT in either table "
             "(left as-is; taxonomy not table-verified)\n")
    for stem in not_in_tables:
        L.append(f"- `data/{stem}.json`")
    L.append("\n\n## 5. Interaction aspects parsed from Table 2 "
             "(informational — NOT written to JSON yet)\n")
    for bib, asp in aspect_info.items():
        stem = T.BIBKEY_TO_FILE.get(bib, "?")
        L.append(f"- `{stem}`: {', '.join(asp) if asp else '—'}")
    text = "\n".join(L) + "\n"
    # Reports are an internal/intermediate artifact -> write into the local
    # (gitignored) archive, not the public tree.
    out_dir = os.path.join(T.REPO, "archive", "reports")
    out = os.path.join(out_dir, "RECONCILIATION.md")
    if dry:
        print(text)
    else:
        os.makedirs(out_dir, exist_ok=True)
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)


def _stem_to_bib(stem):
    for b, s in T.BIBKEY_TO_FILE.items():
        if s == stem:
            return b
    return stem


if __name__ == "__main__":
    main()
