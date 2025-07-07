# MPIpe: MRI Processing Pipeline for BIDS Conversion

A two-stage Python pipeline for converting neuroimaging data from NIfTI format to BIDS (Brain Imaging Data Structure) compliant organization. This tool is specifically designed for the MPI for Biological Cybernetics and provides intelligent heuristics for automatically detecting and organizing anatomical, functional, and fieldmap data.

## Overview

MPIpe currently consists of two main components:

1. **`generate_bids_config.py`** - Stage 1: Scans NIfTI files and generates a YAML mapping configuration
2. **`copy2bids.py`** - Stage 2: Uses the mapping to organize files into BIDS structure

## Features

- ✅ **Automatic Detection**: Intelligent heuristics for identifying anatomical (T1w), functional (BOLD), and fieldmap (GRE) sequences
- ✅ **Flexible Task Naming**: Force all BOLD runs to a specific task or use automatic task detection
- ✅ **Multiple Copy Methods**: Support for copying, hard-linking, or symlinking files
- ✅ **SBRef Support**: Automatically handles single-band reference images
- ✅ **Events Integration**: Optional copying of task events files
- ✅ **Dry Run Mode**: Preview changes before execution
- ✅ **Format Support**: Works with both `.nii` and `.nii.gz` files
- ✅ **Configuration Flexibility**: YAML or JSON configuration files

## Requirements

```bash
pip install pyyaml
```

## Quick Start

### 1. Generate Configuration

Scan your NIfTI directory and create a mapping configuration:

```bash
python generate_bids_config.py \
  --source /path/to/nifti/files \
  --out mapping.yaml
```

**Force all BOLD runs to a specific task:**
```bash
python generate_bids_config.py \
  --source /path/to/nifti/files \
  --force-task vision \
  --out mapping.yaml
```

### 2. Apply BIDS Conversion

Use the generated mapping to organize files in BIDS format:

```bash
python copy2bids.py \
  --source /path/to/nifti/files \
  --dest /path/to/bids/output \
  --config mapping.yaml \
  --method link
```

## Command Reference

### generate_bids_config.py

| Option | Description |
|--------|-------------|
| `--source` | Source directory containing NIfTI files (.nii/.nii.gz) and JSON sidecars |
| `--out` | Output YAML file (default: mapping.yaml) |
| `--force-task NAME` | Assign all BOLD series to specified task name |
| `--task-rename OLD=NEW` | Rename detected task (can be used multiple times) |
| `--no-prompt` | Skip confirmation prompt |

### copy2bids.py

| Option | Description |
|--------|-------------|
| `--source` | Source directory with NIfTI/JSON files |
| `--dest` | BIDS dataset root directory |
| `--config` | YAML/JSON mapping configuration file |
| `--subject` | Override subject ID (default: source directory name) |
| `--method` | Copy method: `copy`, `link`, or `symlink` (default: copy) |
| `--events-dir` | Directory containing `*_events.tsv` files |
| `--dry` | Dry run - show what would be done without executing |

## Configuration Format

The mapping file uses this structure:

```yaml
anat:
  T1w:
    - 0003_ADNI_192slices_64channel

func:
  vision:  # task name
    run-01:
      bold: 0005_cmrr_mbep2d_bold_64ch_MB2_GRAPPA2_2mm_PRG_TR2000
      sbref: 0004_cmrr_mbep2d_bold_64ch_MB2_GRAPPA2_2mm_PRG_TR2000_SBRef
    run-02:
      bold: 0007_cmrr_mbep2d_bold_64ch_MB2_GRAPPA2_2mm_PRG_TR2000

fmap:
  gre:
    magnitude1: 0016_gre_field_mapping_e1
    phase1: 0016_gre_field_mapping_e2
    phase2: 0017_gre_field_mapping_e2_ph
```

## Detection Heuristics

### Anatomical Data
- **T1w**: Matches patterns containing "T1", "ADNI", or "MPRAGE" (case-insensitive)

### Functional Data
- **BOLD**: Matches patterns containing "bold" (case-insensitive)
- **Task Detection**: Looks for "task-" prefix in filename, otherwise uses preceding token
- **SBRef**: Automatically detected and associated with corresponding BOLD runs

### Fieldmaps
- **GRE**: Matches patterns containing "field" or "gre"
- **Components**: Automatically categorizes as magnitude1, phase1, or phase2 based on filename patterns

### Exclusions
- Files matching "localizer" or "scout" patterns are automatically skipped

## Example Workflows

### Multi-Task Study
```bash
# Generate mapping with automatic task detection
python generate_bids_config.py --source /data/subject001 --out mapping.yaml

# Review and edit mapping.yaml if needed
# Then convert to BIDS
python copy2bids.py \
  --source /data/subject001 \
  --dest /data/bids_dataset \
  --config mapping.yaml \
  --events-dir /data/events \
  --method link
```

### Single Task Study
```bash
# Force all BOLD to 'motor' task
python generate_bids_config.py \
  --source /data/subject001 \
  --force-task motor \
  --no-prompt \
  --out mapping.yaml

# Convert with dry run first
python copy2bids.py \
  --source /data/subject001 \
  --dest /data/bids_dataset \
  --config mapping.yaml \
  --dry

# Execute actual conversion
python copy2bids.py \
  --source /data/subject001 \
  --dest /data/bids_dataset \
  --config mapping.yaml \
  --method symlink
```

## Output Structure

The pipeline creates a BIDS-compliant directory structure:

```
bids_dataset/
└── sub-{subject}/
    └── ses-01/
        ├── anat/
        │   ├── sub-{subject}_ses-01_T1w.nii.gz
        │   └── sub-{subject}_ses-01_T1w.json
        ├── func/
        │   ├── sub-{subject}_ses-01_task-{task}_run-01_bold.nii.gz
        │   ├── sub-{subject}_ses-01_task-{task}_run-01_bold.json
        │   ├── sub-{subject}_ses-01_task-{task}_run-01_sbref.nii.gz
        │   ├── sub-{subject}_ses-01_task-{task}_run-01_sbref.json
        │   └── sub-{subject}_ses-01_task-{task}_run-01_events.tsv
        └── fmap/
            ├── sub-{subject}_ses-01_magnitude1.nii.gz
            ├── sub-{subject}_ses-01_phase1.nii.gz
            └── sub-{subject}_ses-01_phase2.nii.gz
```

## Notes

- **Single Session**: Currently designed for single-session datasets (hardcoded as `ses-01`)
- **File Pairing**: Each NIfTI file should have a corresponding JSON sidecar
- **Natural Sorting**: Files are processed in natural alphanumeric order
- **Subject ID**: Defaults to the source directory name but can be overridden

## Contributing

This pipeline can be extended to support:
- Multi-session datasets
- Additional data types (DWI, perfusion, etc.)
- Custom naming conventions
- Advanced task detection heuristics

