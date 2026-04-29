"""
CAVE gain/phase analysis pipeline for visual perturbation experiments.

Experimental design:
    - Sum-of-sines visual stimulus
    - 4 frequency components by default, integer cycles per 120-s trial
    - Standing: AP visual perturbation; amplitudes 0.00, 0.04, 0.08
    - Walking:  ML visual perturbation; amplitudes 0.00, 0.05, 0.15, 0.25, 0.35

File formats supported (auto-detected from filename suffix):
    - 'COP' files  (standing): Vicon force-plate export at 1000 Hz.
                                Columns: Sample # | COP_X (ML) | COP_Y (AP).
                                No logged stimulus — reconstructed from amplitude.
    - 'COM' files  (walking):  Vicon motion-capture export at 100 Hz.
                                Columns: Sample # | COMx (ML) | COMy (AP) | COMz |
                                         Visual_Stim | GVS.
                                Visual_Stim (col 5 in 1-indexed/MATLAB convention)
                                is the ground-truth stimulus. GVS is logged but
                                not used by the FRF analysis (visual-only protocol).

Filenames may use spaces or underscores around the dash separator and may
have any suffix after COP/COM (e.g. '_Export'); these are normalized away.

Outputs:
    - FRF (gain, phase, coherence) at each stimulus frequency, per trial
    - Tidy CSV with one row per (subject, timepoint, condition, amplitude, frequency, axis)
"""

from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Experiment configuration
#
# All experiment-specific parameters (stimulus frequencies, weights, phases,
# trial duration, axis-mapping rules) live in a YAML config file under
# configs/. The default config (configs/cave.yaml) describes the CAVE study;
# other labs can copy it and edit the values for their protocol.
#
# The module-level constants STIM_FREQS_HZ, COMPONENT_WEIGHTS, etc. are
# populated from the active config and exposed for backward compatibility
# with code that imports them directly. Use load_config(path) to switch to
# a different study config at runtime.
# -----------------------------------------------------------------------------

DEFAULT_CONFIG_PATH = Path(__file__).resolve().parent.parent / 'configs' / 'cave.yaml'


def load_config(path=None):
    """
    Load an experiment config from a YAML file. If path is None, loads the
    bundled default (configs/cave.yaml).

    Returns a dict with the config contents. Also updates the module-level
    constants so existing code that imports them keeps working.
    """
    import yaml
    cfg_path = Path(path) if path else DEFAULT_CONFIG_PATH
    if not cfg_path.exists():
        raise FileNotFoundError(f"Config file not found: {cfg_path}")
    with open(cfg_path) as f:
        cfg = yaml.safe_load(f)

    # Validate that frequencies / weights / phases all have the same length
    stim = cfg.get('stimulus', {})
    n = len(stim.get('frequencies_hz', []))
    for key in ('weights', 'phases_rad'):
        if len(stim.get(key, [])) != n:
            raise ValueError(
                f"Config error: stimulus.{key} must have the same length as "
                f"stimulus.frequencies_hz (got {len(stim.get(key, []))} vs {n})"
            )
    if n == 0:
        raise ValueError("Config error: stimulus.frequencies_hz cannot be empty")

    # Update module-level constants so existing code keeps working
    global TRIAL_DURATION_S, STIM_FREQS_HZ, COMPONENT_WEIGHTS, COMPONENT_PHASES
    global N_COMPONENTS, STIM_AXIS_BY_CONDITION, _ACTIVE_CONFIG
    TRIAL_DURATION_S       = float(stim['trial_duration_s'])
    STIM_FREQS_HZ          = tuple(stim['frequencies_hz'])
    COMPONENT_WEIGHTS      = tuple(stim['weights'])
    COMPONENT_PHASES       = tuple(stim['phases_rad'])
    N_COMPONENTS           = n
    STIM_AXIS_BY_CONDITION = dict(cfg.get('stim_axis_by_condition', {}))
    _ACTIVE_CONFIG         = cfg
    return cfg


def get_active_config():
    """Return the currently-loaded config dict (read-only — don't mutate)."""
    return _ACTIVE_CONFIG


# Module-level constants populated by load_config(). These are placeholders
# until load_config() runs at module import time below.
TRIAL_DURATION_S       = 120.0
STIM_FREQS_HZ          = ()
COMPONENT_WEIGHTS      = ()
COMPONENT_PHASES       = ()
N_COMPONENTS           = 0
STIM_AXIS_BY_CONDITION = {}
AXIS_TO_COP_COLUMN     = {'AP': 'cop_y', 'ML': 'cop_x'}
_ACTIVE_CONFIG         = None

# Load the default (CAVE) config at import time. Callers can switch configs
# by calling load_config(path) explicitly.
load_config()


# -----------------------------------------------------------------------------
# Filename parsing
#
# CAVE files come in two flavors: COP (standing, force-plate) and COM (walking,
# motion-capture). Vicon exports them with a space-and-dash separator and an
# optional '_Export' suffix:
#     CAVE_Control_001_Acute_6 - COP.txt
#     CAVE_Concussion_004_Chronic_2 - COM_Export.txt
# Older test data sometimes had underscores around the dash. Both are accepted.
# -----------------------------------------------------------------------------
FILENAME_PATTERN = re.compile(
    r'CAVE_(Control|Concussion)_(\d+)_(Acute|SubAcute|Subacute|Chronic)_(\d+)'
    r'[\s_]+-[\s_]+(COP|COM)[^.]*\.txt$',
    re.IGNORECASE
)


def parse_filename(name):
    """
    Parse a CAVE filename into its components.

    Accepts both Vicon's native format (spaces around the dash, optional
    '_Export' suffix) and the underscore-separated variant used in some
    older test data. The text after 'COP' or 'COM' is ignored.

    Returns a dict with keys: group, subject_id, timepoint, trial_number,
    file_type ('COP' or 'COM'). Returns None if the filename doesn't match.
    """
    m = FILENAME_PATTERN.match(name)
    if not m:
        return None
    group, subj, tp, trial, ftype = m.groups()
    tp = 'SubAcute' if tp.lower() == 'subacute' else tp
    return {
        'group':        group,
        'subject_id':   int(subj),
        'timepoint':    tp,
        'trial_number': int(trial),
        'file_type':    ftype.upper(),
    }


def _trim_or_pad(arr, n_target):
    """Trim or zero-pad a 1-D array to exactly n_target samples."""
    arr = np.asarray(arr, dtype=float)
    if len(arr) > n_target:
        return arr[:n_target]
    if len(arr) < n_target:
        return np.concatenate([arr, np.zeros(n_target - len(arr))])
    return arr


def _interpolate_nans(arr):
    """In-place linear interpolation over NaNs in a 1-D float array."""
    nans = np.isnan(arr)
    if nans.any():
        idx = np.arange(len(arr))
        arr[nans] = np.interp(idx[nans], idx[~nans], arr[~nans])
    return arr


def build_stimulus(trial_amplitude_m, n_samples, fs):
    """
    Reconstruct the stimulus time-series from the active configuration.

    Returns
    -------
    stim : ndarray of shape (n_samples,), in meters of visual-scene displacement
    """
    if trial_amplitude_m == 0:
        return np.zeros(n_samples)
    t = np.arange(n_samples) / fs
    stim = np.zeros(n_samples)
    for f, w, ph in zip(STIM_FREQS_HZ, COMPONENT_WEIGHTS, COMPONENT_PHASES):
        stim += trial_amplitude_m * w * np.sin(2 * np.pi * f * t + ph)
    return stim


def load_stimulus_file(path, fs_expected=1000.0):
    """
    Optional: load the per-trial Visual_Stim time-series from a logged txt file
    (when available). This is the ground-truth stimulus and should be preferred
    over `build_stimulus` reconstruction.

    The function looks for a column named 'Visual_Stim' (case-insensitive) in
    a text file with a tab- or whitespace-delimited header.
    """
    import io
    path = Path(path)
    text = path.read_text()
    # Find header line containing 'visual_stim'
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        if 'visual_stim' in ln.lower():
            header = ln.split()
            data_start = i + 1
            break
    else:
        raise ValueError(f"No 'Visual_Stim' column found in {path.name}")
    col_idx = next(j for j, h in enumerate(header) if h.lower() == 'visual_stim')
    data_text = '\n'.join(lines[data_start:])
    arr = np.loadtxt(io.StringIO(data_text))
    return arr[:, col_idx]


# -----------------------------------------------------------------------------
# Trial-order parsing
# -----------------------------------------------------------------------------
@dataclass
class TrialEntry:
    group: str           # 'Control' or 'Concussion'
    subject_id: int      # 1, 2, 3, ...
    timepoint: str       # 'Acute', 'SubAcute', 'Chronic'
    condition: str       # 'walking' or 'standing'
    trial_number: int    # filename suffix (1..5 walking, 6..8 standing)
    amplitude_m: float   # 0.00, 0.04, 0.08, ... (peak AP displacement)


def parse_trial_order(path):
    """
    Parse the CAVE trial-order text file.

    File format: blocks separated by blank lines. Each subject_timepoint block
    has a header line (e.g., 'Control_001_Acute') followed by 5 walking values,
    a blank line, then 3 standing values.

    Returns: list[TrialEntry]
    """
    text = Path(path).read_text()
    entries = []
    # Split on blank lines, but headers are recognized by the underscore pattern
    header_re = re.compile(r'^(Control|Concussion)_(\d+)_(Acute|SubAcute|Subacute|Chronic)_?$')
    lines = [ln.strip() for ln in text.splitlines()]

    i = 0
    while i < len(lines):
        m = header_re.match(lines[i])
        if not m:
            i += 1
            continue
        group, subj_str, timepoint = m.groups()
        subject_id = int(subj_str)
        timepoint = 'SubAcute' if timepoint.lower() == 'subacute' else timepoint
        i += 1

        # Collect numeric values in order until we have 5 walking + 3 standing
        # Tolerate blank lines between blocks
        values = []
        while i < len(lines) and len(values) < 8:
            ln = lines[i]
            i += 1
            if not ln:
                continue
            if header_re.match(ln):
                i -= 1  # back up; next iteration will re-read header
                break
            try:
                values.append(float(ln))
            except ValueError:
                continue

        if len(values) >= 5:
            for trial_num, amp in enumerate(values[:5], start=1):
                entries.append(TrialEntry(group, subject_id, timepoint,
                                          'walking', trial_num, amp))
        if len(values) >= 8:
            for trial_num, amp in enumerate(values[5:8], start=6):
                entries.append(TrialEntry(group, subject_id, timepoint,
                                          'standing', trial_num, amp))
    return entries


def lookup_amplitude(entries, group, subject_id, timepoint, trial_number):
    for e in entries:
        if (e.group == group and e.subject_id == subject_id
                and e.timepoint == timepoint and e.trial_number == trial_number):
            return e
    return None


# -----------------------------------------------------------------------------
# Data file loading — COP (standing) and COM (walking)
# -----------------------------------------------------------------------------
def _read_header_and_fs(path, n_header=9):
    """Read the header lines and parse the sampling rate from line 4."""
    path = Path(path)
    with open(path) as f:
        header = [next(f) for _ in range(n_header)]
    fs_match = re.search(r'([\d.]+)', header[3])
    fs = float(fs_match.group(1)) if fs_match else None
    return header, fs


def load_cop_file(path):
    """
    Load a CAVE COP file (standing trials, force-plate data at 1000 Hz).

    Expected columns: Sample # | COP_X (ML) | COP_Y (AP).
    The standing protocol does not log the stimulus signal — it must be
    reconstructed from the trial amplitude using build_stimulus().

    Returns
    -------
    fs : float, sampling rate in Hz (parsed from header line 4)
    cop_x : ndarray, ML response
    cop_y : ndarray, AP response
    """
    _, fs = _read_header_and_fs(path)
    if fs is None:
        fs = 1000.0
    data = np.loadtxt(path, skiprows=9)
    cop_x = _interpolate_nans(data[:, 1].astype(float))
    cop_y = _interpolate_nans(data[:, 2].astype(float))
    return fs, cop_x, cop_y


def load_com_file(path):
    """
    Load a CAVE COM file (walking trials, motion-capture at 100 Hz).

    Expected columns: Sample # | COMx (ML) | COMy (AP) | COMz |
                      Visual_Stim | GVS.
    The Visual_Stim column is the ground-truth stimulus logged by Unity at
    each capture frame; FRF analysis uses it directly rather than
    reconstructing. The GVS column is loaded but not used by the current
    visual-only protocol.

    Returns
    -------
    fs : float, sampling rate in Hz (parsed from header line 4)
    com_x : ndarray, ML response (matches MATLAB SigOUT convention, col 2)
    com_y : ndarray, AP response (cross-axis)
    visual_stim : ndarray, logged visual-scene displacement (MATLAB SigIN, col 5)
    """
    _, fs = _read_header_and_fs(path)
    if fs is None:
        fs = 100.0
    data = np.loadtxt(path, skiprows=9)
    if data.shape[1] < 5:
        raise ValueError(
            f"COM file {Path(path).name} has only {data.shape[1]} columns; "
            f"expected at least 5 (Sample, COMx, COMy, COMz, Visual_Stim)."
        )
    com_x       = _interpolate_nans(data[:, 1].astype(float))  # ML
    com_y       = _interpolate_nans(data[:, 2].astype(float))  # AP
    visual_stim = _interpolate_nans(data[:, 4].astype(float))
    return fs, com_x, com_y, visual_stim


def load_trial_file(path):
    """
    Auto-detect file type from the filename and dispatch to the right loader.

    Returns
    -------
    dict with keys:
        file_type   : 'COP' or 'COM'
        fs          : sampling rate in Hz
        signal_ml   : ML response axis
        signal_ap   : AP response axis
        stim        : ndarray or None — logged Visual_Stim (COM only).
                       For COP files this is None; the caller must reconstruct
                       the stimulus from build_stimulus(amplitude, ...).
    """
    parsed = parse_filename(Path(path).name)
    if parsed is None:
        raise ValueError(f"Could not parse CAVE filename: {path}")
    if parsed['file_type'] == 'COP':
        fs, ml, ap = load_cop_file(path)
        return {'file_type': 'COP', 'fs': fs,
                'signal_ml': ml, 'signal_ap': ap, 'stim': None}
    else:  # COM
        fs, ml, ap, stim = load_com_file(path)
        return {'file_type': 'COM', 'fs': fs,
                'signal_ml': ml, 'signal_ap': ap, 'stim': stim}


# -----------------------------------------------------------------------------
# Frequency response function (FRF) at exact stimulus bins
# -----------------------------------------------------------------------------
def compute_frf(stim, response, fs, stim_freqs_hz):
    """
    Compute FRF at each stimulus frequency.

    Because the literal stim frequencies (0.16, 0.21, 0.24, 0.49 Hz) do not
    fall on integer FFT bins of a 120-s trial, energy leaks into 1-2 adjacent
    bins. We handle this by evaluating FRF = Y_resp(f) / Y_stim(f) at the bin
    nearest each stim freq — leakage cancels in the ratio for a linear system.
    Coherence is estimated by sub-segmenting the trial.

    Returns
    -------
    frf : complex ndarray, FRF at each stim freq
    gain : ndarray, |FRF|
    phase_deg : ndarray, angle(FRF) in degrees, wrapped to [-180, 180]
    coherence : ndarray
    """
    N = len(stim)
    Y_resp = np.fft.rfft(response)
    Y_stim = np.fft.rfft(stim)
    f = np.fft.rfftfreq(N, 1 / fs)

    # For each stim freq, evaluate at the bin where the stimulus FFT has
    # peak magnitude in a small window around f0 (handles leakage robustly)
    bins = []
    for f0 in stim_freqs_hz:
        center = int(round(f0 * N / fs))
        window = slice(max(0, center - 1), min(len(Y_stim), center + 2))
        rel_peak = np.argmax(np.abs(Y_stim[window]))
        bins.append(window.start + rel_peak)
    bins = np.array(bins)

    # FRF at peak-stim bins
    frf = Y_resp[bins] / Y_stim[bins]
    gain = np.abs(frf)
    phase_deg = np.angle(frf, deg=True)

    # Coherence — average across K trial sub-segments
    K = 4
    seg_N = N // K
    Pxy = np.zeros(len(stim_freqs_hz), dtype=complex)
    Pxx = np.zeros(len(stim_freqs_hz))
    Pyy = np.zeros(len(stim_freqs_hz))
    for k in range(K):
        s = stim[k*seg_N : (k+1)*seg_N]
        r = response[k*seg_N : (k+1)*seg_N]
        w = np.hanning(seg_N)
        s_w = (s - s.mean()) * w
        r_w = (r - r.mean()) * w
        S = np.fft.rfft(s_w)
        R = np.fft.rfft(r_w)
        f_seg = np.fft.rfftfreq(seg_N, 1/fs)
        # Find peak bin per stim freq within this segment
        seg_bins = []
        for f0 in stim_freqs_hz:
            center = int(round(f0 * seg_N / fs))
            window = slice(max(0, center - 1), min(len(S), center + 2))
            rel = np.argmax(np.abs(S[window]))
            seg_bins.append(window.start + rel)
        seg_bins = np.array(seg_bins)
        Pxy += np.conj(S[seg_bins]) * R[seg_bins]
        Pxx += np.abs(S[seg_bins])**2
        Pyy += np.abs(R[seg_bins])**2
    Pxy /= K; Pxx /= K; Pyy /= K
    coh = np.abs(Pxy)**2 / (Pxx * Pyy + 1e-20)

    return frf, gain, phase_deg, coh


# -----------------------------------------------------------------------------
# Per-trial summary metrics (path length, RMS, mean velocity)
# -----------------------------------------------------------------------------
def compute_summary_metrics(cop_x, cop_y, fs):
    """
    Compute time-domain sway metrics for both AP and ML axes.

    These are standard postural-control metrics intended to complement the
    frequency-domain FRF analysis. They don't depend on the stimulus.

    Returns
    -------
    dict with keys:
        path_length_m_AP, path_length_m_ML  — sum of |Δ| over the trial
        rms_m_AP, rms_m_ML                  — sqrt(mean((x - mean)**2))
        mean_velocity_m_s_AP, mean_velocity_m_s_ML — mean of |dx/dt|
    """
    out = {}
    for label, sig in (('AP', cop_y), ('ML', cop_x)):
        sig = np.asarray(sig, dtype=float)
        sig_dem = sig - np.mean(sig)
        diff = np.diff(sig)
        out[f'path_length_m_{label}']     = float(np.sum(np.abs(diff)))
        out[f'rms_m_{label}']              = float(np.sqrt(np.mean(sig_dem**2)))
        out[f'mean_velocity_m_s_{label}']  = float(np.mean(np.abs(diff)) * fs)
    return out


# -----------------------------------------------------------------------------
# Pipeline driver
# -----------------------------------------------------------------------------
def analyze_trial(file_path, entry):
    """
    Run full analysis on a single CAVE trial. The file type is auto-detected
    from the filename:

      - COP files (standing): force-plate, 1000 Hz, stimulus reconstructed
                              from the trial amplitude (no logged column).
      - COM files (walking):  motion-capture, 100 Hz, stimulus taken from the
                              logged Visual_Stim column.

    FRF is computed on BOTH axes (AP and ML). The `stim_axis` field flags
    which axis the visual stimulus was applied along — that's the matched
    axis. The cross-axis FRF is included for diagnostic value.

    Returns
    -------
    dict with keys:
        frf_per_axis : dict[axis, dict] with 'gain', 'phase_deg',
                       'coherence', 'response_amplitude_m', 'baseline_only',
                       'frequencies_hz'
        summary      : dict from compute_summary_metrics
        stim_axis    : 'AP' (standing) or 'ML' (walking) — matched axis
        file_type    : 'COP' or 'COM' (auto-detected)
        fs_hz        : sampling rate from the file header
    """
    loaded = load_trial_file(file_path)
    file_type = loaded['file_type']
    fs        = loaded['fs']
    signal_ml = loaded['signal_ml']
    signal_ap = loaded['signal_ap']

    # Trim or pad to exactly TRIAL_DURATION_S worth of samples at this fs
    n_target = int(TRIAL_DURATION_S * fs)
    signal_ml = _trim_or_pad(signal_ml, n_target)
    signal_ap = _trim_or_pad(signal_ap, n_target)

    # Stimulus comes from the file (COM/walking) or is reconstructed (COP/standing)
    if file_type == 'COM':
        stim = _trim_or_pad(loaded['stim'], n_target)
    else:  # COP — reconstruct from configured sum-of-sines and trial amplitude
        stim = build_stimulus(entry.amplitude_m, n_target, fs)

    summary = compute_summary_metrics(signal_ml, signal_ap, fs)
    stim_axis = STIM_AXIS_BY_CONDITION.get(entry.condition, 'AP')

    frf_per_axis = {}
    for axis_label, sig in (('AP', signal_ap), ('ML', signal_ml)):
        sig_dem = sig - np.mean(sig)

        if entry.amplitude_m == 0:
            # No stimulus: gain/phase undefined. Report baseline sway power.
            N = len(sig_dem)
            Y = np.fft.rfft(sig_dem)
            bins = [int(round(f0 * N / fs)) for f0 in STIM_FREQS_HZ]
            baseline_amp = np.abs(Y[bins]) * 2 / N
            frf_per_axis[axis_label] = {
                'frequencies_hz':       list(STIM_FREQS_HZ),
                'gain':                 [np.nan]*N_COMPONENTS,
                'phase_deg':            [np.nan]*N_COMPONENTS,
                'coherence':            [np.nan]*N_COMPONENTS,
                'response_amplitude_m': baseline_amp.tolist(),
                'baseline_only':        True,
            }
            continue

        frf, gain, phase, coh = compute_frf(stim, sig_dem, fs, STIM_FREQS_HZ)
        N = len(sig_dem)
        Y_resp = np.fft.rfft(sig_dem)
        bins = [int(round(f0 * N / fs)) for f0 in STIM_FREQS_HZ]
        resp_amp = np.abs(Y_resp[bins]) * 2 / N

        frf_per_axis[axis_label] = {
            'frequencies_hz':       list(STIM_FREQS_HZ),
            'gain':                 gain.tolist(),
            'phase_deg':            phase.tolist(),
            'coherence':            coh.tolist(),
            'response_amplitude_m': resp_amp.tolist(),
            'baseline_only':        False,
        }

    return {
        'frf_per_axis': frf_per_axis,
        'summary':      summary,
        'stim_axis':    stim_axis,
        'file_type':    file_type,
        'fs_hz':        fs,
    }


def discover_files(root_dir, recursive=True):
    """
    Find all CAVE COP and COM files under root_dir.

    Walks the standard nested layout, e.g.:
        root_dir/Standing/Control/Acute/CAVE_Control_001_Acute_6 - COP.txt
        root_dir/Walking/Concussion/Chronic/CAVE_Concussion_004_Chronic_2 - COM_Export.txt

    Filenames may use either spaces or underscores around the dash, and the
    text after COP/COM (e.g. '_Export') is ignored. The condition
    (Standing/Walking) is inferred from the path; group, subject, timepoint,
    trial number, and file type from the filename.

    Parameters
    ----------
    root_dir : str or Path
        Top-level directory to walk.
    recursive : bool
        If True (default), walk subdirectories. If False, only check root_dir.

    Returns
    -------
    list of dicts with keys: path, group, subject_id, timepoint, trial_number,
    file_type ('COP' or 'COM'), condition_from_path (or None).
    """
    root = Path(root_dir)
    paths = root.rglob('CAVE_*.txt') if recursive else root.glob('CAVE_*.txt')

    out = []
    for p in sorted(paths):
        parsed = parse_filename(p.name)
        if parsed is None:
            continue

        # Infer condition from the path (folder name 'Standing' or 'Walking')
        path_parts_lower = [pp.lower() for pp in p.parts]
        condition_from_path = None
        if 'standing' in path_parts_lower:
            condition_from_path = 'standing'
        elif 'walking' in path_parts_lower:
            condition_from_path = 'walking'

        out.append({
            'path':                p,
            'group':               parsed['group'],
            'subject_id':          parsed['subject_id'],
            'timepoint':           parsed['timepoint'],
            'trial_number':        parsed['trial_number'],
            'file_type':           parsed['file_type'],
            'condition_from_path': condition_from_path,
        })
    return out


def run_pipeline(data_dir, trial_order_path,
                 output_csv=None, summary_csv=None,
                 condition_filter='both', include_baseline=True,
                 progress_callback=None, cache_path=None,
                 cop_dir=None,
                 diagnostics_callback=None):
    """
    Discover all CAVE data files (COP and COM) under data_dir, look up each
    in the trial-order file, run analysis (both-axis FRF + summary metrics),
    and return two DataFrames.

    Parameters
    ----------
    data_dir : str or Path
        Top-level directory containing CAVE data files (walked recursively).
        Walks both Standing/ (COP files) and Walking/ (COM files) subtrees.
    trial_order_path : str or Path
        Path to the trial-order text file.
    output_csv : str or Path or None
        If provided, write FRF results CSV here. One row per
        (trial × frequency × axis).
    summary_csv : str or Path or None
        If provided, write per-trial summary metrics CSV here. One row
        per trial.
    condition_filter : 'standing' | 'walking' | 'both'
    include_baseline : bool
    progress_callback : callable(i, n, name) or None
    cache_path : str or Path or None
        If provided, load existing FRF results from this CSV and only re-process
        files not already in it. Set to None to force full re-run. The cache
        is filtered by `condition_filter` on load — cached rows from a
        different condition than the one being requested are ignored, so
        a stale walking cache can never leak into a standing output.
    cop_dir : deprecated alias for data_dir (kept for backward compatibility).
    diagnostics_callback : callable(diagnostics_dict) or None
        If provided, called once at the end with a dict containing
        per-file outcome counts and a list of skipped files. The same
        information is also printed to stdout. Lets the Streamlit UI
        display a structured "what happened" panel after each run.

    Returns
    -------
    (frf_df, summary_df) : tuple of DataFrames
    """
    # Back-compat: callers from before the COP/COM split passed cop_dir
    if cop_dir is not None and data_dir is None:
        data_dir = cop_dir

    entries = parse_trial_order(trial_order_path)
    files = discover_files(data_dir, recursive=True)

    # ------------------------------------------------------------------
    # Cache load — FILTERED by condition_filter
    #
    # Previously: all cached rows were loaded into the output unconditionally.
    # That meant a "standing" run after a "walking" run would re-emit the
    # walking rows from the cache, even when zero standing files actually
    # got processed. The output looked like a successful walking run because
    # it WAS the walking run, just relabeled "standing" by user intent.
    # The filter below makes the cache respect condition_filter so only
    # rows matching the requested condition survive.
    # ------------------------------------------------------------------
    cached_frf_rows = []
    cached_keys = set()
    n_cache_loaded = 0
    n_cache_dropped_wrong_condition = 0
    if cache_path is not None and Path(cache_path).exists():
        cached_df = pd.read_csv(cache_path)
        n_cache_loaded = len(cached_df)
        if condition_filter != 'both':
            mask = cached_df['condition'] == condition_filter
            n_cache_dropped_wrong_condition = int((~mask).sum())
            cached_df = cached_df[mask]
        cached_frf_rows = cached_df.to_dict('records')
        cached_keys = {(r['group'], r['subject_id'], r['timepoint'],
                         r['condition'], r['trial_number'])
                        for r in cached_frf_rows}

    cached_summary_rows = []
    if summary_csv is not None and Path(summary_csv).exists():
        cached_summary_df = pd.read_csv(summary_csv)
        if condition_filter != 'both':
            cached_summary_df = cached_summary_df[
                cached_summary_df['condition'] == condition_filter
            ]
        cached_summary_rows = cached_summary_df.to_dict('records')

    frf_rows = list(cached_frf_rows)
    summary_rows = list(cached_summary_rows)
    n_total = len(files)

    # ------------------------------------------------------------------
    # Per-file outcome tracking
    #
    # Every discovered file falls into exactly one of these buckets. The
    # buckets become a structured diagnostic at the end of the run, so
    # silent failures (the original symptom that produced misleading
    # standing output) are no longer possible.
    # ------------------------------------------------------------------
    outcomes = {
        'processed':                  0,  # ran analyze_trial, added to output
        'cache_hit':                  0,  # already in cache, skipped re-analysis
        'skipped_no_trial_order':     0,  # filename parsed but no trial-order match
        'skipped_wrong_condition':    0,  # entry.condition != condition_filter
        'skipped_baseline':           0,  # amp=0 and include_baseline=False
        'errored':                    0,  # analyze_trial raised
    }
    # Detailed list of every file that didn't make it through to processed/cache_hit.
    # Each entry is (path_name, reason, detail).
    skipped_files = []

    # Discovery breakdown (independent of run outcome — what did discover_files see?)
    discovery_breakdown = {}  # {(condition_from_path, file_type): count}
    for f in files:
        key = (f['condition_from_path'] or '(no Standing/Walking folder)',
                f['file_type'])
        discovery_breakdown[key] = discovery_breakdown.get(key, 0) + 1

    for i, f in enumerate(files):
        if progress_callback is not None:
            progress_callback(i, n_total, f['path'].name)

        entry = lookup_amplitude(entries, f['group'], f['subject_id'],
                                  f['timepoint'], f['trial_number'])
        if entry is None:
            outcomes['skipped_no_trial_order'] += 1
            skipped_files.append((
                f['path'].name,
                'no_trial_order_match',
                f"no entry for {f['group']}/{f['subject_id']}/{f['timepoint']}/trial {f['trial_number']}",
            ))
            continue

        if (f['condition_from_path'] is not None
                and entry.condition != f['condition_from_path']):
            print(f"  WARN: path says {f['condition_from_path']} but "
                  f"trial-order says {entry.condition} for {f['path'].name}")

        # Cross-check: COP→standing, COM→walking
        expected_ftype = 'COP' if entry.condition == 'standing' else 'COM'
        if f['file_type'] != expected_ftype:
            print(f"  WARN: {f['path'].name} is a {f['file_type']} file but "
                  f"trial-order says {entry.condition} (expected {expected_ftype})")

        if condition_filter != 'both' and entry.condition != condition_filter:
            outcomes['skipped_wrong_condition'] += 1
            skipped_files.append((
                f['path'].name,
                'wrong_condition',
                f"trial-order says condition='{entry.condition}', "
                f"filter='{condition_filter}'",
            ))
            continue
        if not include_baseline and entry.amplitude_m == 0:
            outcomes['skipped_baseline'] += 1
            skipped_files.append((
                f['path'].name,
                'baseline_excluded',
                'amplitude=0 and include_baseline=False',
            ))
            continue

        key = (entry.group, entry.subject_id, entry.timepoint,
                entry.condition, entry.trial_number)
        if key in cached_keys:
            outcomes['cache_hit'] += 1
            continue

        try:
            result = analyze_trial(f['path'], entry)
        except Exception as e:
            outcomes['errored'] += 1
            skipped_files.append((f['path'].name, 'analyze_trial_error', str(e)))
            print(f"  ERROR analyzing {f['path'].name}: {e}")
            continue
        outcomes['processed'] += 1

        # FRF rows: one per (frequency, axis)
        meta = {
            'group':        entry.group,
            'subject_id':   entry.subject_id,
            'timepoint':    entry.timepoint,
            'condition':    entry.condition,
            'trial_number': entry.trial_number,
            'amplitude_m':  entry.amplitude_m,
            'file_type':    result['file_type'],
            'fs_hz':        result['fs_hz'],
        }
        stim_axis = result['stim_axis']
        for axis_label, axis_result in result['frf_per_axis'].items():
            for j, freq in enumerate(axis_result['frequencies_hz']):
                frf_rows.append({
                    **meta,
                    'frequency_hz':         round(freq, 4),
                    'axis':                 axis_label,
                    'is_stim_matched':      (axis_label == stim_axis),
                    'gain':                 axis_result['gain'][j],
                    'phase_deg':            axis_result['phase_deg'][j],
                    'coherence':            axis_result['coherence'][j],
                    'response_amplitude_m': axis_result['response_amplitude_m'][j],
                    'baseline_only':        axis_result['baseline_only'],
                })

        # Summary metrics row: one per trial
        summary_rows.append({**meta, 'stim_axis': stim_axis, **result['summary']})

    if progress_callback is not None:
        progress_callback(n_total, n_total, 'done')

    frf_df = pd.DataFrame(frf_rows)
    summary_df = pd.DataFrame(summary_rows)

    if output_csv is not None and not frf_df.empty:
        frf_df.to_csv(output_csv, index=False)
    if summary_csv is not None and not summary_df.empty:
        summary_df.to_csv(summary_csv, index=False)

    # ------------------------------------------------------------------
    # End-of-run diagnostics
    #
    # Always printed, also passed to diagnostics_callback if provided.
    # When zero standing files survive a "standing" run, this is what
    # tells you immediately why — instead of having to guess from a CSV
    # that looks suspiciously like a previous walking output.
    # ------------------------------------------------------------------
    diagnostics = {
        'n_discovered':                  n_total,
        'discovery_breakdown':           discovery_breakdown,
        'condition_filter':              condition_filter,
        'include_baseline':              include_baseline,
        'cache_path':                    str(cache_path) if cache_path else None,
        'n_cache_loaded':                n_cache_loaded,
        'n_cache_dropped_wrong_condition': n_cache_dropped_wrong_condition,
        'outcomes':                      outcomes,
        'skipped_files':                 skipped_files,
        'n_frf_rows_out':                len(frf_rows),
        'n_summary_rows_out':            len(summary_rows),
    }

    print("─" * 70)
    print(f"CAVE pipeline run summary  (condition_filter={condition_filter})")
    print("─" * 70)
    print(f"Discovered {n_total} files. Discovery breakdown:")
    for (cond, ftype), n in sorted(discovery_breakdown.items()):
        print(f"    {cond:>40s}  {ftype:>3s}  ×  {n}")
    if cache_path is not None:
        print(f"Cache: loaded {n_cache_loaded} rows from {cache_path}; "
              f"dropped {n_cache_dropped_wrong_condition} not matching "
              f"condition_filter='{condition_filter}'.")
    print("Per-file outcomes:")
    for name, n in outcomes.items():
        print(f"    {name:>30s}  {n}")
    if skipped_files:
        print(f"Skipped files (showing up to 10 of {len(skipped_files)}):")
        for name, reason, detail in skipped_files[:10]:
            print(f"    [{reason}]  {name}  —  {detail}")
        if len(skipped_files) > 10:
            print(f"    ... and {len(skipped_files) - 10} more")
    print(f"Output: {len(frf_rows)} FRF rows, {len(summary_rows)} summary rows.")
    print("─" * 70)

    if diagnostics_callback is not None:
        try:
            diagnostics_callback(diagnostics)
        except Exception as e:
            print(f"  WARN: diagnostics_callback raised: {e}")

    return frf_df, summary_df
