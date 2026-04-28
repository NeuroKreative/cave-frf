"""
CAVE gain/phase analysis pipeline for visual perturbation experiments.

Experimental design:
    - Sum-of-sines visual stimulus, AP rotation about ankle axis
    - 4 frequency components, integer cycles per 120-s trial
    - Standing: amplitudes 0.00, 0.04, 0.08 (peak AP displacement of summed waveform)
    - Walking:  amplitudes 0.00, 0.05, 0.15, 0.25, 0.35
    - COP recorded at 1000 Hz, COP_Y is AP direction
    - Stimulus and force-plate trigger-aligned at t=0

Outputs:
    - FRF (gain, phase) at each stimulus frequency, per trial
    - Tidy CSV with one row per (subject, timepoint, condition, amplitude, frequency)
"""

from dataclasses import dataclass
from pathlib import Path
import re
import numpy as np
import pandas as pd

# -----------------------------------------------------------------------------
# Stimulus model — confirmed from Unity formula:
#   D(t) = A · [1.0·sin(2π·0.16·t) + 0.8·sin(2π·0.21·t)
#             + 1.4·sin(2π·0.24·t) + 0.5·sin(2π·0.49·t)]
#   where A = trial scaling factor (0.04 / 0.08 standing, 0.05/.../0.35 walking)
# -----------------------------------------------------------------------------
TRIAL_DURATION_S = 120.0
STIM_FREQS_HZ      = (0.16, 0.21, 0.24, 0.49)
COMPONENT_WEIGHTS  = (1.0,  0.8,  1.4,  0.5)
COMPONENT_PHASES   = (0.0,  0.0,  0.0,  0.0)   # zero per Unity formula
N_COMPONENTS = len(STIM_FREQS_HZ)

# Stimulus axis per condition. Standing: visual scene moves AP
# (anterior-posterior). Walking: visual scene moves ML (mediolateral).
# COP_X is recorded as ML, COP_Y as AP.
STIM_AXIS_BY_CONDITION = {
    'standing': 'AP',
    'walking':  'ML',
}
AXIS_TO_COP_COLUMN = {'AP': 'cop_y', 'ML': 'cop_x'}


def build_stimulus(trial_amplitude_m, n_samples, fs):
    """
    Reconstruct the AP visual-scene stimulus from the Unity formula.

    Returns
    -------
    stim : ndarray of shape (n_samples,), AP displacement in meters
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
# COP file loading
# -----------------------------------------------------------------------------
def load_cop_file(path):
    """
    Load a CAVE COP_Export text file.

    Returns
    -------
    fs : float, sampling rate in Hz (parsed from header line 4)
    cop_x, cop_y : ndarrays. NaNs are linearly interpolated.
    """
    path = Path(path)
    with open(path) as f:
        header = [next(f) for _ in range(9)]
    # Sampling rate is line 4 of header
    fs_match = re.search(r'([\d.]+)', header[3])
    fs = float(fs_match.group(1)) if fs_match else 1000.0

    data = np.loadtxt(path, skiprows=9)
    cop_x = data[:, 1].astype(float)
    cop_y = data[:, 2].astype(float)

    for arr in (cop_x, cop_y):
        nans = np.isnan(arr)
        if nans.any():
            idx = np.arange(len(arr))
            arr[nans] = np.interp(idx[nans], idx[~nans], arr[~nans])
    return fs, cop_x, cop_y


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
def analyze_trial(file_path, entry, fs_expected=1000.0):
    """
    Run full analysis on a single COP trial.

    Computes FRF on BOTH axes (AP=COP_Y, ML=COP_X) and per-trial summary
    metrics. The stimulus-axis-matched FRF (AP for standing, ML for walking)
    is the primary measure; the cross-axis FRF is included for exploring
    cross-axis effects.

    Returns
    -------
    dict with keys:
        frf_per_axis : dict[axis, dict] with 'gain', 'phase_deg', 'coherence',
                        'response_amplitude_m', 'baseline_only', 'frequencies_hz'
        summary       : dict from compute_summary_metrics
        stim_axis     : 'AP' or 'ML' (the axis the stimulus moved in)
    """
    fs, cop_x, cop_y = load_cop_file(file_path)
    if abs(fs - fs_expected) > 1:
        print(f"  WARN: fs={fs} Hz, expected {fs_expected}")

    # Truncate to exactly 120 s
    n_target = int(TRIAL_DURATION_S * fs)
    if len(cop_y) > n_target:
        cop_x = cop_x[:n_target]
        cop_y = cop_y[:n_target]
    elif len(cop_y) < n_target:
        pad = n_target - len(cop_y)
        cop_x = np.concatenate([cop_x, np.zeros(pad)])
        cop_y = np.concatenate([cop_y, np.zeros(pad)])

    summary = compute_summary_metrics(cop_x, cop_y, fs)
    stim_axis = STIM_AXIS_BY_CONDITION.get(entry.condition, 'AP')
    stim = build_stimulus(entry.amplitude_m, n_target, fs)

    frf_per_axis = {}
    for axis_label, sig in (('AP', cop_y), ('ML', cop_x)):
        sig_dem = sig - np.mean(sig)

        if entry.amplitude_m == 0:
            # No stimulus: gain/phase undefined. Report baseline sway power.
            N = len(sig_dem)
            Y = np.fft.rfft(sig_dem)
            f_arr = np.fft.rfftfreq(N, 1/fs)
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
    }


def discover_files(root_dir, recursive=True):
    """
    Find all CAVE COP files under root_dir.

    Walks the standard nested layout:
        root_dir/Standing/Control/Acute/CAVE_Control_001_Acute_6_-_COP.txt
        root_dir/Standing/Control/SubAcute/...
        root_dir/Walking/Concussion/Chronic/...

    The condition (Standing/Walking) is inferred from the path; group, subject,
    timepoint, and trial number from the filename. Validates that path-implied
    condition agrees with the one looked up from the trial-order file.

    Parameters
    ----------
    root_dir : str or Path
        Top-level directory to walk (e.g. the COM Data folder).
    recursive : bool
        If True (default), walk subdirectories. If False, only check root_dir.

    Returns
    -------
    list of dicts with keys: path, group, subject_id, timepoint, trial_number,
    condition_from_path
    """
    pat = re.compile(
        r'CAVE_(Control|Concussion)_(\d+)_(Acute|SubAcute|Subacute|Chronic)_(\d+)_-_COP\.txt',
        re.IGNORECASE
    )
    root = Path(root_dir)
    paths = root.rglob('CAVE_*_-_COP.txt') if recursive else root.glob('CAVE_*_-_COP.txt')

    out = []
    for p in sorted(paths):
        m = pat.match(p.name)
        if not m:
            continue
        group, subj, tp, trial = m.groups()
        tp = 'SubAcute' if tp.lower() == 'subacute' else tp

        # Infer condition from the path (folder name 'Standing' or 'Walking')
        path_parts_lower = [pp.lower() for pp in p.parts]
        condition_from_path = None
        if 'standing' in path_parts_lower:
            condition_from_path = 'standing'
        elif 'walking' in path_parts_lower:
            condition_from_path = 'walking'

        out.append({
            'path': p,
            'group': group,
            'subject_id': int(subj),
            'timepoint': tp,
            'trial_number': int(trial),
            'condition_from_path': condition_from_path,
        })
    return out


def run_pipeline(cop_dir, trial_order_path,
                 output_csv=None, summary_csv=None,
                 condition_filter='both', include_baseline=True,
                 progress_callback=None, cache_path=None):
    """
    Discover all COP files under cop_dir, look up each in the trial-order
    file, run analysis (both-axis FRF + summary metrics), and return two
    DataFrames.

    Parameters
    ----------
    cop_dir : str or Path
        Top-level directory containing COP files (walked recursively).
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
        files not already in it. Set to None to force full re-run.

    Returns
    -------
    (frf_df, summary_df) : tuple of DataFrames
    """
    entries = parse_trial_order(trial_order_path)
    files = discover_files(cop_dir, recursive=True)

    cached_frf_rows = []
    cached_keys = set()
    if cache_path is not None and Path(cache_path).exists():
        cached_df = pd.read_csv(cache_path)
        cached_frf_rows = cached_df.to_dict('records')
        cached_keys = {(r['group'], r['subject_id'], r['timepoint'],
                         r['condition'], r['trial_number'])
                        for r in cached_frf_rows}

    cached_summary_rows = []
    if summary_csv is not None and Path(summary_csv).exists():
        cached_summary_rows = pd.read_csv(summary_csv).to_dict('records')

    frf_rows = list(cached_frf_rows)
    summary_rows = list(cached_summary_rows)
    n_processed = 0
    n_skipped = 0
    n_total = len(files)

    for i, f in enumerate(files):
        if progress_callback is not None:
            progress_callback(i, n_total, f['path'].name)

        entry = lookup_amplitude(entries, f['group'], f['subject_id'],
                                  f['timepoint'], f['trial_number'])
        if entry is None:
            n_skipped += 1
            continue

        if (f['condition_from_path'] is not None
                and entry.condition != f['condition_from_path']):
            print(f"  WARN: path says {f['condition_from_path']} but "
                  f"trial-order says {entry.condition} for {f['path'].name}")

        if condition_filter != 'both' and entry.condition != condition_filter:
            continue
        if not include_baseline and entry.amplitude_m == 0:
            continue

        key = (entry.group, entry.subject_id, entry.timepoint,
                entry.condition, entry.trial_number)
        if key in cached_keys:
            continue

        try:
            result = analyze_trial(f['path'], entry)
        except Exception as e:
            print(f"  ERROR analyzing {f['path'].name}: {e}")
            continue
        n_processed += 1

        # FRF rows: one per (frequency, axis)
        meta = {
            'group':        entry.group,
            'subject_id':   entry.subject_id,
            'timepoint':    entry.timepoint,
            'condition':    entry.condition,
            'trial_number': entry.trial_number,
            'amplitude_m':  entry.amplitude_m,
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

    print(f"Discovered {n_total} files; processed {n_processed} new, "
          f"reused {len(cached_frf_rows)//8 if cached_frf_rows else 0} cached, "
          f"skipped {n_skipped}.")
    return frf_df, summary_df
