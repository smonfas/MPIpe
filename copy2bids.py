#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None

def find_file(source: Path, stem: str, ext: str) -> Optional[Path]:
    matches = list(source.rglob(f"{stem}{ext}"))
    return matches[0] if matches else None

def load_mapping(cfg_path: Path) -> Dict[str, Any]:
    text = cfg_path.read_text()
    if cfg_path.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            sys.exit("PyYAML is required to read YAML configs - install with `pip install pyyaml`.")
        return yaml.safe_load(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        sys.exit(f"Config file not valid JSON or YAML: {e}")

def copy_file(src: Path, dst: Path, method: str, dry: bool = False):
    if dry:
        print(f" [DRY] {method.upper():6} {src} -> {dst}")
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if method == "copy":
        shutil.copy2(src, dst)
    elif method == "link":
        if dst.exists():
            dst.unlink()
        os.link(src, dst)
    elif method == "symlink":
        if dst.exists():
            dst.unlink()
        rel = os.path.relpath(src, dst.parent)
        os.symlink(rel, dst)
    else:
        raise ValueError(f"Unknown method: {method}")

# -------- parsing utilities --------
EXT_STRIP = re.compile(r"\.(nii(\.gz)?|json)$", re.I)
LEADING_INDEX = re.compile(r"^[\s_-]*\d+[\s_-]*")  # fixed: drop leading digits + optional separators

def normalize_stem(stem: str) -> str:
    s = EXT_STRIP.sub("", stem)
    s = s.strip()
    s = LEADING_INDEX.sub("", s)
    return s.lower()

# Sequence detection (mutually exclusive — each pattern is independent)
SEQ_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("vaso",           re.compile(r"(?i)(?<![a-z0-9])vaso(?![a-z0-9])")),
    ("bssfp",          re.compile(r"(?i)(?<![a-z0-9])(3d)?bssfp(?![a-z0-9])")),
    ("ep2d_bold_2000", re.compile(r"(?i)(?<![a-z0-9])ep2d[^a-z0-9]*bold[^a-z0-9]*2000(?![a-z0-9])")),
    ("ep2d_bold_800",  re.compile(r"(?i)(?<![a-z0-9])ep2d[^a-z0-9]*bold[^a-z0-9]*800(?![a-z0-9])")),
    ("mprage",         re.compile(r"(?i)(?<![a-z0-9])mprage(?![a-z0-9])")),
]

# Modality detection: pick the first that appears; else fallback to "prep" in parse_modality()
MOD_PATTERNS: List[Tuple[str, re.Pattern]] = [
    ("task", re.compile(r"(?i)(?<![a-z0-9])task(?![a-z0-9])")),
    ("rs",   re.compile(r"(?i)(?<![a-z0-9])rs(?![a-z0-9])")),
    ("test", re.compile(r"(?i)(?<![a-z0-9])test(?![a-z0-9])")),
]
RUN_EXPLICIT_END = re.compile(r"(?:^|[_-])run[-_]?(\d{1,2})$", re.I)
RUN_ANY = re.compile(r"(?:^|[_-])run[-_]?(\d{1,2})\b", re.I)

def parse_sequence(name: str) -> str:
    matches = [label for label, pat in SEQ_PATTERNS if pat.search(name)]
    if not matches:
        return "unknownseq"
    if len(matches) > 1:
        print(f"⚠ Multiple sequence tokens in '{name}': {matches} → using '{matches[0]}'")
    return matches[0]
def parse_modality(name: str) -> str:
    for label, pat in MOD_PATTERNS:
        if pat.search(name):
            return label
    return "prep"


def parse_run(name: str) -> Optional[str]:
    m = RUN_EXPLICIT_END.search(name)
    if m:
        return f"run-{int(m.group(1)):02d}"
    matches = list(RUN_ANY.finditer(name))
    if matches:
        return f"run-{int(matches[-1].group(1)):02d}"
    return None

def build_custom_name(subject: str, session: str, src_stem: str, idx_for_fallback: int | None = None) -> str:
    n = normalize_stem(src_stem)
    seq = parse_sequence(n)
    mod = parse_modality(n)
    run = parse_run(n)
    if not run:
        run = f"run-{(idx_for_fallback or 1):02d}"
    return f"{subject}_{session}_{seq}_{mod}_{run}"

def build_bids_dest_name(subject: str, session: str, suffix: str, ext: str = ".nii.gz") -> str:
    return f"{subject}_{session}_{suffix}{ext}"

# -------- copy routines --------
def copy_section_list(stems: List[str], source: Path, dest: Path, subject: str, session: str,
                      method: str, dry: bool, filenaming: str, section: str, counters: Dict[str, int]):
    assert section in {"anat", "func", "fmap"}

    def bids_suffix_for(sec: str) -> str:
        if sec == "anat":
            return "T1w"
        if sec == "func":
            counters.setdefault("bids_func_idx", 0)
            counters["bids_func_idx"] += 1
            return f"task-unk_run-{counters['bids_func_idx']:02d}_bold"
        counters.setdefault("bids_fmap_idx", 0)
        counters["bids_fmap_idx"] += 1
        return f"fmap{counters['bids_fmap_idx']:02d}"

    for stem in stems:
        if not stem:
            continue

        # compute name stem once per series
        out_stem_custom: str | None = None
        out_suffix_bids: str | None = None

        if filenaming == "custom":
            n = normalize_stem(stem)
            seq = parse_sequence(n)

            # Only functional runs have a modality component
            mod = parse_modality(n) if section == "func" else None

            explicit_run = parse_run(n)
            if explicit_run is None:
                # run counter resets per (section, seq, mod)
                key = f"{section}:{seq}:{mod or 'none'}"
                counters.setdefault(key, 0)
                counters[key] += 1
                run = f"run-{counters[key]:02d}"
            else:
                run = explicit_run

            # Custom naming logic per section
            if section == "func":
                out_stem_custom = f"{subject}_{session}_{seq}_{mod}_{run}"
            elif section == "anat":
                out_stem_custom = f"{subject}_{session}_{seq}_{run}"
            elif section == "fmap":
                # fmap files always get '_revpe' at the end
                out_stem_custom = f"{subject}_{session}_{seq}_{run}_revpe"

        elif filenaming == "bids":
            out_suffix_bids = bids_suffix_for(section)

        # Copy .nii.gz and .json
        for ext in (".nii.gz", ".json"):
            src = find_file(source, stem, ext)
            if not src or not src.exists():
                print(f"WARNING - missing file {stem}{ext}")
                continue

            if filenaming == "preserve":
                out_name = src.name
            elif filenaming == "custom":
                out_name = f"{out_stem_custom}{ext}"
            elif filenaming == "bids":
                out_name = build_bids_dest_name(subject, session, out_suffix_bids, ext)
            else:
                raise ValueError("Invalid filenaming mode")

            dst = dest / f"{subject}" / f"{session}" / section / out_name
            copy_file(src, dst, method, dry)

def main():  # noqa: C901
    p = argparse.ArgumentParser(description="Copy/link NIfTI series into a flat-mapped BIDS tree (anat/func/fmap lists)")
    p.add_argument("--source", required=True, type=Path, help="Folder with *.nii(.gz) / *.json series")
    p.add_argument("--dest", required=True, type=Path, help="Root of BIDS dataset (created if needed)")
    p.add_argument("--config", required=True, type=Path, help="YAML or JSON mapping file (flat lists for anat/func/fmap)")
    p.add_argument("--subject", required=True, help="Subject ID (same for all files)")
    p.add_argument("--session", required=True, help="Session ID (same for all files)")
    p.add_argument("--method", choices=["copy", "link", "symlink"], default="copy", help="Copy method [copy]")
    p.add_argument("--dry", action="store_true", help="Dry-run - print actions only")
    p.add_argument(
        "--filenaming",
        choices=["preserve", "custom", "bids"],
        default="custom",
        help="Filename strategy: preserve original, custom (subject-session-sequence-modality-run), or simple bids-ish.",
    )
    args = p.parse_args()

    if not args.source.is_dir():
        sys.exit(f"Source directory not found: {args.source}")
    if not args.config.is_file():
        sys.exit(f"Config file not found: {args.config}")

    mapping = load_mapping(args.config)
    anat_list: List[str] = mapping.get("anat", []) or []
    func_list: List[str] = mapping.get("func", []) or []
    fmap_list: List[str] = mapping.get("fmap", []) or []

    counters: Dict[str, int] = {}

    copy_section_list(anat_list, args.source, args.dest, args.subject, args.session, args.method, args.dry, args.filenaming, "anat", counters)
    copy_section_list(func_list, args.source, args.dest, args.subject, args.session, args.method, args.dry, args.filenaming, "func", counters)
    copy_section_list(fmap_list, args.source, args.dest, args.subject, args.session, args.method, args.dry, args.filenaming, "fmap", counters)

    print("\n✔ Done (dry-run)" if args.dry else "\n✔ Finished copying/linking.")

if __name__ == "__main__":
    main()
