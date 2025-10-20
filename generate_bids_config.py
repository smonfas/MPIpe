#!/usr/bin/env python3
from __future__ import annotations

import argparse
import itertools
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

try:
    import yaml
except ImportError:  # pragma: no cover
    sys.exit("PyYAML is required - install with `pip install pyyaml`")

# Patterns (case-insensitive)
PAT_ANAT = re.compile(r"(?i)(T1|ADNI|MPRAGE|MP2RAGE|me4|greCAIPI)")
PAT_FUNC = re.compile(r"(?i)(bold|func|bssfp|vaso|bSSFP)")
PAT_FMAP = re.compile(r"(?i)(field|revpe)")
PAT_SKIP = re.compile(r"(?i)(localizer|scout|MPR_Range|intermediate|Start|GLM|Design|MoCo)")
PAT_SBREF = re.compile(r"SBRef", re.I)

def natural_sort_key(text: str):
    return [int("".join(g)) if k else "".join(g) for k, g in itertools.groupby(text, str.isdigit)]

def scan_source(source: Path) -> List[Path]:
    return sorted(
        itertools.chain(source.rglob("*.nii"), source.rglob("*.nii.gz")),
        key=lambda p: natural_sort_key(p.name),
    )

def series_id(p: Path) -> str:
    if p.suffix == ".gz" and p.name.endswith(".nii.gz"):
        return p.name[:-7]
    return p.stem

def categorise(fpaths: List[Path]) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {"anat": [], "func": [], "fmap": []}
    seen = set()
    for f in fpaths:
        fname = f.name
        sid = series_id(f)
        if sid in seen:
            continue
        seen.add(sid)
        match_text = f"{f.parent.name}_{fname}"

        if PAT_SKIP.search(match_text):
            continue
        if PAT_SBREF.search(match_text):
            continue

        # fmap has priority over func
        if PAT_FMAP.search(match_text):
            mapping["fmap"].append(sid)
            continue

        if PAT_ANAT.search(match_text):
            mapping["anat"].append(sid)
            continue

        if PAT_FUNC.search(match_text):
            mapping["func"].append(sid)
            continue

        # if nothing matched, leave it out silently (or add a bucket if you prefer)
    # deduplicate while preserving order (in case of odd paths)
    for k in ("anat", "func", "fmap"):
        seen_k = set()
        dedup = []
        for s in mapping[k]:
            if s not in seen_k:
                seen_k.add(s)
                dedup.append(s)
        mapping[k] = dedup
    # drop empty sections for a cleaner YAML
    return {k: v for k, v in mapping.items() if v}

def main():
    p = argparse.ArgumentParser(description="Generate flat YAML mapping (anat/func/fmap lists) for copy2bids.py")
    p.add_argument("--source", required=True, type=Path, help="Folder with NIfTI series (.nii / .nii.gz) + JSON sidecars")
    p.add_argument("--out", type=Path, default=Path("mapping.yaml"), help="YAML file to write [mapping.yaml]")
    p.add_argument("--no-prompt", action="store_true", help="Write without confirmation prompt")
    args = p.parse_args()

    if not args.source.is_dir():
        sys.exit(f"Source directory not found: {args.source}")

    mapping = categorise(scan_source(args.source))
    yaml_str = yaml.safe_dump(mapping, sort_keys=False)

    print("\nProposed mapping (edit later if needed):\n")
    print(yaml_str)

    if not args.no_prompt:
        ans = input(f"Write mapping to {args.out.resolve()}? [Y/n] ")
        if ans.strip().lower() not in ("", "y", "yes"):
            print("Aborted - no file written.")
            sys.exit(0)

    args.out.write_text(yaml_str)
    print(f"\n✔ Mapping saved to {args.out.resolve()}.\n")

if __name__ == "__main__":
    main()
