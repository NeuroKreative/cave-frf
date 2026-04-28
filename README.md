# CAVE Sensory Reweighting

> Analysis pipeline for the CAVE study — frequency response function (gain,
> phase, coherence) plus per-trial summary metrics (RMS, path length, mean
> velocity) for postural sway in response to a sum-of-sines visual
> perturbation.

Built for the CAVE Adult Stimulus Factor study: Control vs. Concussion, across
Acute / SubAcute / Chronic timepoints, in Standing and Walking conditions.

This pipeline continues the line of sensory-reweighting research developed by
the Jeka lab (Hwang et al. 2014) and extended in
[Vanderlinde dos Santos (2019)](#citation) and Dr. Jaclyn Caccese on repetitive head impacts and
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

Each data file must be named according to one of two patterns, matching
the standing or walking export format from Vicon:

```
CAVE_<Group>_<###>_<Timepoint>_<TrialNumber> - COP.txt          ← standing
CAVE_<Group>_<###>_<Timepoint>_<TrialNumber> - COM_Export.txt   ← walking
```

The filename has **five underscore-separated fields**, then a space-dash-space
separator, then either `COP` (standing, force-plate) or `COM` (walking,
motion-capture) followed by an optional suffix. The pipeline accepts both
spaces and underscores around the dash, and ignores whatever appears after
`COP` / `COM` (so `- COP.txt`, `- COP_Export.txt`, and `_-_COP.txt` all work).

Worked example: `CAVE_Concussion_023_SubAcute_4 - COM_Export.txt` parses as

| position | piece | meaning | allowed values |
|---|---|---|---|
| 1 | `CAVE_` | fixed prefix | exactly this |
| 2 | `Concussion` | **Group** | `Control` or `Concussion` (case-sensitive) |
| 3 | `023` | **Subject ID** | three digits, zero-padded (`001`, `015`, `103` …) |
| 4 | `SubAcute` | **Timepoint** | `Acute`, `SubAcute`, or `Chronic` (also accepts `Subacute`) |
| 5 | `4` | **Trial number** | `1`–`5` for walking trials, `6`–`8` for standing trials |
| 6 | ` - ` | separator | space-dash-space (or `_-_`) |
| 7 | `COM_Export` | **File type** | `COP*` (standing) or `COM*` (walking); suffix ignored |
| 8 | `.txt` | extension | required |

A few correctly-named examples:

```
CAVE_Control_001_Acute_3 - COM_Export.txt    ← Control 1, Acute, walking trial 3
CAVE_Concussion_017_Chronic_7 - COP.txt      ← Concussion 17, Chronic, standing trial 7
CAVE_Control_042_SubAcute_5 - COM_Export.txt ← Control 42, SubAcute, walking trial 5
```

The pipeline cross-checks the file type against the trial number and warns
if there's a mismatch (e.g. a COP file at trial position 3, which should
have been a walking trial).

### Common naming mistakes that cause silent skips

- Using a hyphen `-` instead of an underscore `_` between the *first five* fields
- Subject ID with fewer than three digits (`CAVE_Control_1_…` won't match — needs `001`)
- Lowercased group (`control` instead of `Control`)
- Stray characters in the filename
- A trial number outside 1–8

If files are present in the folder but the UI says it found 0 files, it's
almost always one of the above. Rename the files and re-run.

### File contents

The pipeline understands both Vicon Nexus export formats. Both share a
9-line header structure (user ID, date, source filename, **sampling rate
on line 4**, capture period, blank lines, column header) and tab-separated
data starting at line 10.

**COP files** (standing, 1000 Hz):

| col | name | meaning |
|---|---|---|
| 1 | `Sample #` | sample index |
| 2 | `COP_X` | center of pressure, mediolateral (ML) — meters |
| 3 | `COP_Y` | center of pressure, anteroposterior (AP) — meters |

The standing protocol does **not** log the visual stimulus; the pipeline
reconstructs it from the trial amplitude (looked up in the trial-order
file) and the sum-of-sines parameters in the active config.

**COM files** (walking, 100 Hz):

| col | name | meaning |
|---|---|---|
| 1 | `Sample #` | sample index |
| 2 | `COMx` | center of mass, mediolateral (ML response) — meters |
| 3 | `COMy` | center of mass, anteroposterior (AP) — meters |
| 4 | `COMz` | center of mass, vertical — meters (not used) |
| 5 | `Visual_Stim` | logged visual-scene displacement — meters |
| 6 | `GVS` | logged GVS channel — **loaded but not used** in current visual-only protocol |

Walking trials use the logged `Visual_Stim` column directly as the FRF
input — no reconstruction needed. The matched stimulus axis is ML for
walking (the visual scene translates laterally, driving lateral COM sway).

The pipeline expects 120 seconds of data per trial regardless of file
type. Shorter files are zero-padded; longer ones are truncated. The
sampling rate is parsed from the header on every load, so trials with
non-standard rates work as long as the header reports it correctly.

> **Note on the GVS channel:** in the current adult visual-only protocol,
> the logged GVS column is a scaled copy of `Visual_Stim` (no actual
> galvanic stimulation is being delivered). The pipeline ignores it. If
> a future protocol uses real GVS, the column will already be loadable
> and only the analysis dispatch will need to be extended.

> **Note on standing-trial phase alignment:** because COP files don't log
> the stimulus, the standing reconstruction assumes the data starts at
> *t* = 0 with the visual stimulus also at zero phase. Gain and coherence
> are robust to small offsets; absolute phase is not. If your protocol
> introduces a pre-trial period before stimulus onset, that needs to be
> trimmed before running the pipeline (or the reconstruction generalized).

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

The visual scene moves as a sum of sinusoids:

$$
D(t) = A \cdot \sum_{i=1}^{N} w_i \, \sin(2\pi f_i t + \varphi_i)
$$

where *A* is a per-trial scaling factor from the trial-order file, and the
frequencies *fᵢ*, weights *wᵢ*, and phases *φᵢ* are read from a YAML
config file in `configs/`.

The default config (`configs/cave.yaml`, used by the CAVE study) specifies:

- **N = 4** components
- **frequencies:** 0.16, 0.21, 0.24, 0.49 Hz
- **weights:** 1.0, 0.8, 1.4, 0.5
- **phases:** 0, 0, 0, 0
- **trial duration:** 120 s
- **standing trials:** stim moves AP, pipeline analyzes COP_Y
- **walking trials:** stim moves ML, pipeline analyzes COP_X
- **trial scaling factors:** A ∈ {0, 0.04, 0.08} standing; {0, 0.05, 0.15, 0.25, 0.35} walking

Trials with *A* = 0 are baseline (no stimulus). Gain and phase are undefined
for them, but baseline sway power is reported in the FRF CSV.

---

## Adapting this pipeline for a different study

The pipeline supports any sum-of-sines stimulus design. To run it on data
from a different protocol — different number of components, different
frequencies, different axis-mapping — copy `configs/cave.yaml` to a new
file, edit the values, and load it via the UI sidebar (**⚙️ Stimulus
configuration → Load config**) or the `--config` flag on the CLI.

A worked template is provided in `configs/example_other_lab.yaml` showing
a 3-component stimulus with different axis names. The pipeline will:

- Use any number of components (the math handles arbitrary N)
- Accept any axis-mapping rules (e.g., `eyes_closed_standing → AP`,
  `treadmill_walk → ML`, etc. — the mapping just needs to use `AP` or `ML`
  on the right-hand side because COP files have only those two axes)
- Validate per-trial amplitudes against an allowed-list (optional)
- Read `trial_duration_s` from the config rather than hard-coding 120 s

> **Filename and folder format limitation (v0.4):** the current filename
> parser is hard-coded to the CAVE study's convention. Specifically, every
> COP filename must look like:
>
> ```
> CAVE_<Group>_<###>_<Timepoint>_<TrialNumber>_-_COP.txt
> ```
>
> with `Group ∈ {Control, Concussion}` and `Timepoint ∈ {Acute, SubAcute, Chronic}`.
> See the **Data naming and folder layout** section above for the complete
> filename specification with examples.
>
> If your study uses different group names (e.g., `Athletes` vs. `NonAthletes`)
> or different timepoints (e.g., `Pre`, `Post`, `Followup`), you have two
> options:
>
> 1. **Rename your files to fit the CAVE pattern.** Map your groups to
>    `Control`/`Concussion` and your timepoints to `Acute`/`SubAcute`/`Chronic`
>    (the names are just labels in the output CSVs — relabel after analysis if
>    you want).
> 2. **Wait for v0.5**, which will introduce a configurable filename pattern.
>    [Open an issue](https://github.com/YOUR_USERNAME/cave-frf/issues) if your
>    use case would benefit so we can prioritize it.

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

To run with a non-default config (e.g., for another lab's study):

```bash
python scripts/run_pipeline.py \
    --config configs/my_lab.yaml \
    --data-dir "/path/to/data" \
    --trial-order trial_order.txt \
    --frf-csv frf_results.csv \
    --summary-csv summary_metrics.csv
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
├── LICENSE                    ← MIT
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

This project is licensed under the MIT License — see the `LICENSE` file for
details. You're free to use, adapt, and redistribute the code for academic
or commercial purposes as long as you preserve the copyright notice and
credit the original work (see [Citation](#citation) above).
