# CAVE Sensory Reweighting

> Analysis pipeline for the CAVE study — frequency response function (gain,
> phase, coherence) plus per-trial summary metrics (RMS, path length, mean
> velocity) for postural sway in response to a sum-of-sines visual
> perturbation.

Built for the CAVE Adult Stimulus Factor study: Control vs. Concussion, across
Acute / SubAcute / Chronic timepoints, in Standing and Walking conditions.

This pipeline continues the line of sensory-reweighting research developed by
the Jeka lab (Hwang et al. 2014) and extended in
[Vanderlinde dos Santos (2019)](#citation) and Dr. jaclyn Caccese on repetitive head impacts and
sensory reweighting, applied here to a longitudinal post-concussion design.

---

## What you can do with this

- Drop a folder of COP files into the UI, click **Run**, get plots and CSVs.
- See per-trial gain & phase as bar plots, or as Hwang-style recovery
  trajectories across timepoints — your choice.
- Get per-trial summary metrics (RMS, path length, mean velocity) plus a
  group × timepoint comparison plot.
- Re-run as new subjects come in: only new trials get processed.
- Run from the command line for batch / cron jobs.

**All analysis happens locally — your data never leaves your computer.**
This is by design. The pipeline is intended for biomedical research data
(concussion patient COP recordings) where uploading files to a hosted web
service would create IRB and data-governance issues. Local-only avoids all of
that.

---

## Installation

You need Python 3.10+ installed once. After that, the launcher script
handles everything (creates a project-local environment, installs
dependencies, runs the app).

### Quick install

1. Install Python 3.10+ if you don't already have it
   ([Anaconda](https://www.anaconda.com/download) is the easiest path on
   Mac, [python.org](https://www.python.org/downloads/) on Windows — be
   sure to check **"Add Python to PATH"** during the Windows install).
2. [Download this repo as a ZIP](#) (green Code button at top of GitHub
   page → Download ZIP) and unzip it.
3. Open a terminal in the unzipped folder and run the launcher:

   ```bash
   ./run.sh        # macOS / Linux
   run.bat         # Windows (or just double-click it)
   ```

The first run takes about a minute (installing dependencies); subsequent
runs start in seconds. Your browser opens at `http://localhost:8501`.

For step-by-step instructions with troubleshooting, see [INSTALL.md](INSTALL.md).

### Why a local install instead of a hosted web app?

This pipeline analyzes biomedical research data (concussion patient COP
recordings). Local-only avoids any data ever traversing third-party
servers — no IRB issues, no cloud-storage concerns, no privacy review
needed. The launcher script is the closest thing to "click and run" we
can offer while keeping data on your machine.

### Experimental: standalone executable

If installing Python is a hard blocker for some users, an experimental
standalone executable build is available — see
[`build/standalone/README.md`](build/standalone/README.md). **The Python
install path above is the supported one;** the standalone build is provided
as-is and may break in ways that are hard to debug.

---

## Data naming and folder layout

The pipeline finds and parses files **based on filename and folder location**,
so naming has to be exact. Anything unexpected gets skipped silently.

### Folder layout

```
COM Data/
  Standing/
    Control/
      Acute/
        CAVE_Control_001_Acute_6_-_COP.txt
        CAVE_Control_001_Acute_7_-_COP.txt
        ...
      SubAcute/
      Chronic/
    Concussion/
      Acute/
      SubAcute/
      Chronic/
  Walking/
    Control/
      Acute/
        CAVE_Control_001_Acute_1_-_COP.txt
        ...
      SubAcute/
      Chronic/
    Concussion/
      ...
```

The top-level folder can be named anything (`COM Data`, `MyStudy`, etc.) —
that's what you point the UI at. Inside, the structure must match the layout
above.

### Filename pattern

Each COP file must be named:

```
CAVE_<Group>_<###>_<Timepoint>_<TrialNumber>_-_COP.txt
```

Worked example: `CAVE_Concussion_023_SubAcute_4_-_COP.txt` is

| piece | meaning | allowed values |
|---|---|---|
| `CAVE_` | fixed prefix | exactly this |
| `Concussion` | group | `Control` or `Concussion` (case-sensitive) |
| `023` | subject ID | three digits, zero-padded |
| `SubAcute` | timepoint | `Acute`, `SubAcute`, or `Chronic` (also accepts `Subacute`) |
| `4` | trial number | 1–5 for walking, 6–8 for standing |
| `_-_COP.txt` | fixed suffix | exactly this — note the underscores around the dash |

### Common naming mistakes that cause silent skips

- Using a hyphen `-` instead of an underscore `_` between fields
- Subject ID with fewer than three digits (`CAVE_Control_1_…` won't match — needs `001`)
- Lowercased group (`control` instead of `Control`)
- Stray spaces in the filename
- A trial number outside 1–8

If files are present in the folder but the UI says it found 0 files, it's
almost always one of the above. Rename the files and re-run.

### File contents

Each COP file is the standard Vicon Nexus COP_Export text format:

- 9 lines of header (User ID, evaluation date, source filename, sampling
  rate, capture period, blank lines)
- Line 9: column header `Sample #\tCOP_X\tCOP_Y`
- Line 10 onward: data, three columns separated by tabs

Sampling rate is read from the header (typically 1000 Hz). The pipeline
expects 120 seconds of data per trial. Shorter files are zero-padded;
longer ones are truncated.

### Trial-order file

The trial-order text file maps each (subject × timepoint × trial-number) to
its amplitude. A version is bundled in this repo as
`Updated-_CAVE_Adult_Stimulus_Factor_Trial.txt`. If you collect new subjects
and need to add them, follow this format:

```
Control_001_Acute
0.25
0.15
0.00
0.35
0.05

0.08
0.00
0.04

Control_001_SubAcute
0.15
…
```

For each subject × timepoint:

- One header line: `<Group>_<###>_<Timepoint>`
- Five amplitude values, one per line — these are walking trials 1 through 5
- A blank line
- Three amplitude values — these are standing trials 6 through 8
- A blank line before the next subject's header

Header capitalization is case-sensitive (`Control_001_Acute`, not
`control_001_acute`).

---

## Adding new subjects to the analysis

When you collect data from a new subject, do these three things:

1. Drop the new COP files into the appropriate `Group/Timepoint/` folder
2. Add the new subject's block to the trial-order file
3. Re-run

The pipeline caches results, so already-processed trials are skipped
automatically — re-runs after adding new subjects are fast.

To force a full re-analysis (e.g., after changing the analysis methodology),
uncheck **"Skip already-processed trials"** in the UI, or pass `--no-cache`
on the CLI.

---

## What the pipeline computes

### FRF (frequency response function)

For each trial × stim-frequency × axis (AP and ML):

- **Gain** = |response| / |stimulus| at that frequency
- **Phase** = ∠(response / stimulus) in degrees
- **Coherence** = stim/response coherence (0–1) at that frequency

Two axes are computed for every trial. The "stim-matched" axis is **AP for
standing** (visual scene moves AP) and **ML for walking** (visual scene
moves ML). The other axis is included so you can look at cross-axis effects
too (e.g., AP response during walking).

### Summary metrics

For each trial, on each axis:

- **RMS** of demeaned COP — overall sway amplitude
- **Path length** — total excursion (sum of |Δ|)
- **Mean velocity** — mean of |dx/dt|

These don't depend on the stimulus and are useful sanity checks alongside
the FRF.

---

## Plot styles

Switchable in the UI:

**Bar plots (per-trial)** — one bar per (group × amplitude) combination at
each stim frequency. Good for spotting gross differences and sanity-checking
individual trials.

**Hwang-style line plots (recovery trajectory)** — gain and phase plotted
against timepoint (Acute → SubAcute → Chronic), one line per (group ×
amplitude), error bars = SEM across subjects, one panel per stim frequency.
Reads like figures from Hwang et al. 2014; designed for the recovery story.

Both can be displayed side-by-side ("Both" option).

---

## Stimulus model

The visual scene moves according to:

```
D(t) = A · [1.0·sin(2π·0.16·t) + 0.8·sin(2π·0.21·t)
          + 1.4·sin(2π·0.24·t) + 0.5·sin(2π·0.49·t)]
```

where *A* is the trial scaling factor from the trial-order file:
- standing: *A* ∈ {0, 0.04, 0.08} (AP visual scene motion)
- walking: *A* ∈ {0, 0.05, 0.15, 0.25, 0.35} (ML visual scene motion)

Trials with *A* = 0 are baseline (no stimulus). Gain and phase are
undefined for them, but baseline sway power is reported in the FRF CSV.

---

## CLI usage (for power users / batch processing)

```bash
python scripts/run_pipeline.py \
    --data-dir "/path/to/COM Data" \
    --trial-order "Updated- CAVE Adult Stimulus Factor Trial.txt" \
    --frf-csv frf_results.csv \
    --summary-csv summary_metrics.csv \
    --condition both \
    --plots-dir plots/
```

`python scripts/run_pipeline.py --help` for all options.

---

## Output schema

### `frf_results.csv` — one row per (trial × frequency × axis)

| column | description |
|--------|-------------|
| group | `Control` or `Concussion` |
| subject_id | integer subject ID |
| timepoint | `Acute`, `SubAcute`, or `Chronic` |
| condition | `standing` or `walking` |
| trial_number | filename suffix (1–5 walking, 6–8 standing) |
| amplitude_m | trial scaling factor *A* |
| frequency_hz | one of 0.16, 0.21, 0.24, 0.49 |
| axis | `AP` or `ML` |
| is_stim_matched | True when axis matches stim axis |
| gain | \|FRF\| at this frequency (NaN if baseline) |
| phase_deg | ∠FRF in degrees (NaN if baseline) |
| coherence | 0–1, stim/response coherence |
| response_amplitude_m | raw response amplitude at this freq |
| baseline_only | True if from an *A*=0 trial |

### `summary_metrics.csv` — one row per trial

| column | description |
|--------|-------------|
| group, subject_id, timepoint, condition, trial_number, amplitude_m | trial metadata |
| stim_axis | the axis the stimulus moved in (AP or ML) |
| rms_m_AP, rms_m_ML | RMS of demeaned COP |
| path_length_m_AP, path_length_m_ML | total path length |
| mean_velocity_m_s_AP, mean_velocity_m_s_ML | mean speed |

---

## Methodology notes

- COP_X is ML, COP_Y is AP (force-plate convention used in this study)
- Each trial truncated to exactly 120 s; NaN samples linearly interpolated
- Stimulus reconstructed from the Unity formula at the COP sampling rate
  (1000 Hz), assuming all components phased at 0
- FRF = Y_response(f) / Y_stimulus(f), evaluated at the FFT bin where the
  stimulus magnitude peaks near each target frequency. This handles
  spectral leakage cleanly — the literal frequencies 0.16/0.21/0.24/0.49 Hz
  are not on integer FFT bins of a 120-s window
- Coherence estimated by averaging across 4 sub-segments per trial

---

## Tests

```bash
python tests/test_basic.py
```

Tests verify:

- Stimulus formula matches expected per-component amplitudes
- FRF gives unit gain and zero phase when response = stimulus
- FRF correctly recovers a known time delay as phase lag
- RMS and path length match analytic values for a known sine wave
- Trial-order parser handles the actual file format

---

## Repository layout

```
cave-frf/
├── README.md                  ← this file
├── INSTALL.md                 ← step-by-step install walkthrough w/ troubleshooting
├── CONTRIBUTING.md            ← how to propose changes (for collaborators)
├── CITATION.cff               ← GitHub auto-citation metadata
├── LICENSE                    ← (you add this when creating the repo)
├── .gitignore                 ← blocks subject data files from being committed
├── requirements.txt           ← Python dependencies
├── Updated-_CAVE_Adult_Stimulus_Factor_Trial.txt   ← bundled trial-order
│
├── app.py                     ← Streamlit UI (the main entry point)
├── run.sh                     ← Mac/Linux launcher
├── run.bat                    ← Windows launcher
│
├── cave_frf/                  ← the analysis package
│   ├── __init__.py
│   ├── analysis.py            ← parsing, FRF computation, summary metrics, pipeline
│   └── plots.py               ← all plot functions
│
├── scripts/                   ← maintenance scripts
│   ├── run_pipeline.py        ← command-line interface
│   ├── install_hooks.sh       ← installs the data-protection git hook (Mac/Linux)
│   └── install_hooks.bat      ← same, for Windows
│
├── .githooks/                 ← git hooks (installed by scripts/install_hooks.*)
│   └── pre-commit             ← refuses commits that contain subject data files
│
├── tests/
│   └── test_basic.py          ← 8 smoke tests verifying the analysis math
│
└── build/standalone/          ← experimental PyInstaller bundle (see its own README)
    ├── README.md              ← read this before attempting a standalone build
    ├── cave_frf.spec          ← PyInstaller config
    ├── launcher_main.py       ← entry point for the frozen executable
    └── build.sh               ← convenience wrapper for the build command
```

---

## Authors & contact

**Fernando Vanderlinde dos Santos, PhD** *(maintainer)*
📧 neurokreative@gmail.com
🔗 [ResearchGate profile](https://www.researchgate.net/profile/Fernando-Santos)

**Jaclyn B. Caccese, PhD** — Associate Professor, School of Health and
Rehabilitation Sciences, The Ohio State University; Chronic Brain Injury
Program member. Principal investigator of the CAVE study.
🔗 [ResearchGate profile](https://www.researchgate.net/profile/Jaclyn-Caccese-2)

For questions about the pipeline, methodology, or to report a bug, please
[open an issue](https://github.com/YOUR_USERNAME/cave-frf/issues) on this
repository or email Fernando directly.

---

## Citation

### Citing this software

If you use this pipeline in published work, please cite both the software
and the underlying methodology.

Plain text:

> Vanderlinde dos Santos, F., & Caccese, J. B. (YEAR). *CAVE Sensory
> Reweighting (cave-frf)* (Version X.Y.Z) [Software]. Available from
> https://github.com/YOUR_USERNAME/cave-frf

BibTeX:

```bibtex
@software{vanderlinde_caccese_cavefrf,
  author       = {Vanderlinde dos Santos, Fernando and Caccese, Jaclyn B.},
  title        = {{CAVE Sensory Reweighting (cave-frf)}},
  url          = {https://github.com/YOUR_USERNAME/cave-frf},
  version      = {0.3.0},
  year         = {YEAR}
}
```

### Citing the underlying methodology

> Hwang S, Agada P, Kiemel T, Jeka JJ (2014). Dynamic Reweighting of Three
> Modalities for Sensor Fusion. *PLoS ONE* 9(1): e88132.
> [doi:10.1371/journal.pone.0088132](https://doi.org/10.1371/journal.pone.0088132)

> Vanderlinde dos Santos F (2019). *The Effect of Repetitive Head Impacts in
> Sensory Reweighting and Human Balance.* PhD dissertation, University of
> Delaware. ProQuest 13860200.

A `CITATION.cff` file is included so GitHub renders a "Cite this repository"
button on the repo page.

---

## License

Add your lab's preferred license. **MIT** is recommended for academic
research code so collaborators and other labs can adapt the pipeline freely
while still being required to credit you. To add it: in GitHub, click
**Add file → Create new file**, name it `LICENSE`, and click "Choose a
license template" → MIT.
