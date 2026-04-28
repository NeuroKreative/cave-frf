"""Plotting routines for CAVE FRF results.

All plots accept a results DataFrame (`frf_df` or `summary_df`) and an
output path, and write a PNG. They are pure functions — no global state.

Plot families:
    Bar plots (per-trial view):
        plot_gain_phase, plot_coherence, plot_nyquist, plot_spectra
    Hwang-style line plots (group/timepoint trajectory view):
        plot_hwang_recovery
    Summary metric plots (sway power):
        plot_summary_metrics
"""
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

from .analysis import (
    STIM_FREQS_HZ, TRIAL_DURATION_S, build_stimulus, load_cop_file,
    parse_trial_order, lookup_amplitude, discover_files,
)

GROUP_COLORS = {'Control': '#2E86AB', 'Concussion': '#E63946'}
TIMEPOINT_ORDER = ['Acute', 'SubAcute', 'Chronic']


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------
def _filter_axis(df, axis):
    """Filter FRF df to a single axis or return as-is."""
    if axis is None or axis == 'both':
        return df
    if axis == 'stim_matched':
        return df[df['is_stim_matched']]
    return df[df['axis'] == axis]


def _sem(x):
    """Standard error of mean. Returns NaN if n < 2."""
    x = np.asarray(x, dtype=float)
    x = x[~np.isnan(x)]
    return np.std(x, ddof=1) / np.sqrt(len(x)) if len(x) >= 2 else np.nan


def _empty_plot(output_path, msg):
    fig, ax = plt.subplots(figsize=(8, 3))
    ax.text(0.5, 0.5, msg, ha='center', va='center',
            transform=ax.transAxes, fontsize=12, color='gray')
    ax.axis('off')
    fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Bar plots — per-trial view
# ---------------------------------------------------------------------------
def plot_gain_phase(df, output_path, axis='stim_matched'):
    """Bar plot: gain (left) and phase (right) at each stim freq, by group/amp."""
    df = _filter_axis(df, axis)
    df = df[~df['baseline_only']]
    if df.empty:
        return _empty_plot(output_path, "no non-baseline trials")

    fig, (ax_g, ax_p) = plt.subplots(1, 2, figsize=(13, 5))
    freqs = sorted(df['frequency_hz'].unique())
    x = np.arange(len(freqs))
    width = 0.18

    combos = []
    for grp in ['Control', 'Concussion']:
        for amp in sorted(df[df['group'] == grp]['amplitude_m'].unique()):
            combos.append((grp, amp))
    if not combos:
        return _empty_plot(output_path, "no data")

    max_amp = max(amp for _, amp in combos) if combos else 1
    for i, (grp, amp) in enumerate(combos):
        sub = df[(df['group'] == grp) & (df['amplitude_m'] == amp)]
        gains = [sub[sub['frequency_hz'] == f]['gain'].mean() for f in freqs]
        phases = [sub[sub['frequency_hz'] == f]['phase_deg'].mean() for f in freqs]
        offset = (i - (len(combos) - 1) / 2) * width
        color = GROUP_COLORS[grp]
        alpha = 0.5 + 0.5 * (amp / max_amp)
        ax_g.bar(x + offset, gains, width, color=color, alpha=alpha,
                 label=f'{grp} amp={amp:.2f}', edgecolor='black', lw=0.5)
        ax_p.bar(x + offset, phases, width, color=color, alpha=alpha,
                 label=f'{grp} amp={amp:.2f}', edgecolor='black', lw=0.5)

    ax_g.set_title('Gain'); ax_g.set_ylabel('|FRF| (response m / stim m)')
    ax_p.set_title('Phase'); ax_p.set_ylabel('Phase (deg)')
    ax_p.set_ylim(-200, 200)
    for ax in (ax_g, ax_p):
        ax.set_xticks(x); ax.set_xticklabels([f'{f:.3f}' for f in freqs])
        ax.set_xlabel('Stimulus frequency (Hz)')
        ax.axhline(0, color='gray', lw=0.5)
        ax.legend(fontsize=8, loc='best'); ax.grid(axis='y', alpha=0.3)

    title_axis = "stim-matched axis" if axis == 'stim_matched' else f"{axis} axis"
    fig.suptitle(f'FRF: gain and phase per trial ({title_axis})', fontsize=11)
    fig.tight_layout()
    fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


def plot_coherence(df, output_path, axis='stim_matched'):
    df = _filter_axis(df, axis)
    df = df[~df['baseline_only']]
    if df.empty:
        return _empty_plot(output_path, "no non-baseline trials")

    fig, ax = plt.subplots(figsize=(11, 4.5))
    freqs = sorted(df['frequency_hz'].unique())
    x = np.arange(len(freqs))
    width = 0.18
    combos = []
    for grp in ['Control', 'Concussion']:
        for amp in sorted(df[df['group'] == grp]['amplitude_m'].unique()):
            combos.append((grp, amp))
    max_amp = max(amp for _, amp in combos) if combos else 1
    for i, (grp, amp) in enumerate(combos):
        sub = df[(df['group'] == grp) & (df['amplitude_m'] == amp)]
        cohs = [sub[sub['frequency_hz'] == f]['coherence'].mean() for f in freqs]
        offset = (i - (len(combos) - 1) / 2) * width
        ax.bar(x + offset, cohs, width, color=GROUP_COLORS[grp],
               alpha=0.5 + 0.5 * (amp / max_amp),
               label=f'{grp} amp={amp:.2f}', edgecolor='black', lw=0.5)
    ax.set_xticks(x); ax.set_xticklabels([f'{f:.3f}' for f in freqs])
    ax.set_xlabel('Stimulus frequency (Hz)')
    ax.set_ylabel('Coherence (0-1)')
    title_axis = "stim-matched axis" if axis == 'stim_matched' else f"{axis} axis"
    ax.set_title(f'Stimulus / response coherence ({title_axis})')
    ax.set_ylim(0, 1); ax.legend(fontsize=8); ax.grid(axis='y', alpha=0.3)
    fig.tight_layout(); fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


def plot_nyquist(df, output_path, axis='stim_matched'):
    df = _filter_axis(df, axis)
    df = df[~df['baseline_only']]
    if df.empty:
        return _empty_plot(output_path, "no non-baseline trials")

    freqs = sorted(df['frequency_hz'].unique())
    fig, axes = plt.subplots(1, len(freqs), figsize=(4*len(freqs), 4),
                              subplot_kw=dict(projection='polar'))
    if len(freqs) == 1:
        axes = [axes]
    max_amp_map = {grp: (df[df['group']==grp]['amplitude_m'].max() or 1)
                   for grp in df['group'].unique()}
    for ax, freq in zip(axes, freqs):
        sub = df[df['frequency_hz'] == freq]
        for _, row in sub.iterrows():
            color = GROUP_COLORS[row['group']]
            alpha = 0.4 + 0.6 * (row['amplitude_m'] / max_amp_map.get(row['group'], 1))
            theta = np.deg2rad(row['phase_deg'])
            r = row['gain']
            ax.plot(theta, r, 'o', color=color, alpha=alpha, markersize=10,
                    markeredgecolor='black', markeredgewidth=0.7)
        ax.set_title(f'{freq:.3f} Hz', fontsize=10, pad=12)
        ax.set_ylim(0, max(0.6, sub['gain'].max() * 1.15) if not sub.empty else 1)
    handles = [plt.Line2D([0],[0], marker='o', color='w', markerfacecolor=c,
                          markersize=10, label=g, markeredgecolor='black')
               for g, c in GROUP_COLORS.items()]
    fig.legend(handles=handles, loc='lower center', ncol=2, bbox_to_anchor=(0.5, -0.02))
    title_axis = "stim-matched axis" if axis == 'stim_matched' else f"{axis} axis"
    fig.suptitle(f'FRF in complex plane ({title_axis})', fontsize=11)
    fig.tight_layout(); fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


def plot_spectra(cop_files_with_meta, trial_order_path, output_path,
                  max_files=8, axis='AP'):
    entries = parse_trial_order(trial_order_path)
    files = [f for f in cop_files_with_meta if lookup_amplitude(
                entries, f['group'], f['subject_id'], f['timepoint'], f['trial_number'])]
    files = files[:max_files]
    if not files:
        return _empty_plot(output_path, "no files")

    n = len(files)
    fig, axes = plt.subplots(n, 1, figsize=(11, 1.7 * n), sharex=True)
    if n == 1:
        axes = [axes]
    for ax, f in zip(axes, files):
        e = lookup_amplitude(entries, f['group'], f['subject_id'],
                              f['timepoint'], f['trial_number'])
        fs, cop_x, cop_y = load_cop_file(f['path'])
        sig = cop_y if axis == 'AP' else cop_x
        sig = sig - sig.mean()
        N = len(sig)
        Y = np.abs(np.fft.rfft(sig)) * 2 / N
        freq = np.fft.rfftfreq(N, 1/fs)
        ax.semilogy(freq, Y * 1000, color=GROUP_COLORS[e.group], lw=0.7)
        for f0 in STIM_FREQS_HZ:
            ax.axvline(f0, color='gray', ls=':', lw=0.8, alpha=0.6)
        ax.set_xlim(0, 1.0); ax.set_ylim(1e-3, 100)
        label = (f"{e.group} #{e.subject_id} {e.timepoint} {e.condition} "
                 f"trial {e.trial_number} amp={e.amplitude_m:.2f}")
        ax.set_ylabel(f'|COP_{axis}| (mm)', fontsize=9)
        ax.text(0.99, 0.92, label, transform=ax.transAxes, ha='right', va='top',
                fontsize=9, bbox=dict(facecolor='white', edgecolor='none', alpha=0.85))
        ax.tick_params(labelsize=8)
    axes[-1].set_xlabel('Frequency (Hz)')
    ax2 = axes[0].twiny(); ax2.set_xlim(axes[0].get_xlim())
    ax2.set_xticks(STIM_FREQS_HZ)
    ax2.set_xticklabels([f'{f:.3f}' for f in STIM_FREQS_HZ], fontsize=8)
    ax2.tick_params(axis='x', colors='gray')
    fig.suptitle(f'COP_{axis} response spectra — stim freqs marked at top',
                 y=0.995, fontsize=11)
    fig.tight_layout(); fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Hwang-style: recovery trajectory across timepoints
# ---------------------------------------------------------------------------
def plot_hwang_recovery(df, output_path, axis='stim_matched'):
    """
    Hwang-style line plot: gain and phase vs timepoint.

    Layout: 4 rows (one per stim frequency) × 2 cols (gain, phase).
    Each panel: x = timepoint (Acute / SubAcute / Chronic), one line per
    (group × amplitude), error bars = SEM across subjects.
    """
    df = _filter_axis(df, axis)
    df = df[~df['baseline_only']]
    if df.empty:
        return _empty_plot(output_path, "no non-baseline trials")

    freqs = sorted(df['frequency_hz'].unique())
    timepoints = [tp for tp in TIMEPOINT_ORDER if tp in df['timepoint'].unique()]
    if not timepoints:
        return _empty_plot(output_path, "no timepoints in data")

    fig, axes = plt.subplots(len(freqs), 2, figsize=(11, 2.6 * len(freqs)),
                              sharex=True)
    if len(freqs) == 1:
        axes = axes[np.newaxis, :]

    amplitudes = sorted([a for a in df['amplitude_m'].unique() if a > 0])
    if not amplitudes:
        return _empty_plot(output_path, "no non-zero amplitudes")

    for row_idx, freq in enumerate(freqs):
        ax_g = axes[row_idx, 0]
        ax_p = axes[row_idx, 1]
        sub_freq = df[df['frequency_hz'] == freq]

        for grp in ['Control', 'Concussion']:
            color = GROUP_COLORS[grp]
            for amp in amplitudes:
                ls = '-' if amp == max(amplitudes) else '--'
                marker = 'o' if amp == max(amplitudes) else 's'
                gains_mean = []; gains_sem = []
                phases_mean = []; phases_sem = []
                for tp in timepoints:
                    cell = sub_freq[(sub_freq['group'] == grp) &
                                     (sub_freq['amplitude_m'] == amp) &
                                     (sub_freq['timepoint'] == tp)]
                    gains_mean.append(cell['gain'].mean() if not cell.empty else np.nan)
                    gains_sem.append(_sem(cell['gain'].values))
                    phases_mean.append(cell['phase_deg'].mean() if not cell.empty else np.nan)
                    phases_sem.append(_sem(cell['phase_deg'].values))
                label = f'{grp} A={amp:.2f}'
                ax_g.errorbar(range(len(timepoints)), gains_mean, yerr=gains_sem,
                              color=color, ls=ls, marker=marker, markersize=7,
                              capsize=3, label=label, lw=1.5,
                              markeredgecolor='black', markeredgewidth=0.5)
                ax_p.errorbar(range(len(timepoints)), phases_mean, yerr=phases_sem,
                              color=color, ls=ls, marker=marker, markersize=7,
                              capsize=3, label=label, lw=1.5,
                              markeredgecolor='black', markeredgewidth=0.5)

        ax_g.set_ylabel(f'{freq:.3f} Hz\nGain', fontsize=10)
        ax_p.set_ylabel('Phase (deg)', fontsize=10)
        ax_p.set_ylim(-200, 200); ax_p.axhline(0, color='gray', lw=0.5)
        ax_g.grid(alpha=0.3); ax_p.grid(alpha=0.3)
        if row_idx == 0:
            ax_g.set_title('Gain', fontsize=11)
            ax_p.set_title('Phase', fontsize=11)
            ax_g.legend(fontsize=7, loc='best', ncol=2)

    for ax in axes[-1]:
        ax.set_xticks(range(len(timepoints)))
        ax.set_xticklabels(timepoints)
        ax.set_xlabel('Timepoint')

    title_axis = 'stim-matched axis' if axis == 'stim_matched' else f'{axis} axis'
    fig.suptitle(f'FRF recovery trajectory ({title_axis}) — error bars = SEM',
                 fontsize=12, y=0.998)
    fig.tight_layout(); fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)


# ---------------------------------------------------------------------------
# Summary metrics — group comparison
# ---------------------------------------------------------------------------
SUMMARY_METRICS = [
    ('rms_m',                   'RMS (m)'),
    ('path_length_m',           'Path length (m)'),
    ('mean_velocity_m_s',       'Mean velocity (m/s)'),
]


def plot_summary_metrics(summary_df, output_path,
                          condition='walking', axes=('AP', 'ML')):
    """
    Group comparison of per-trial summary metrics.

    Layout: rows = metrics (RMS / path length / velocity),
            cols = axes (AP, ML).
    Each panel: x = timepoint, bars colored by group, error bars = SEM
    across subjects. Aggregates across all amplitudes within each
    (group, timepoint) cell.
    """
    df = summary_df[summary_df['condition'] == condition].copy()
    if df.empty:
        return _empty_plot(output_path, f"no {condition} trials in summary")

    timepoints = [tp for tp in TIMEPOINT_ORDER if tp in df['timepoint'].unique()]
    if not timepoints:
        return _empty_plot(output_path, "no timepoints")

    n_metrics = len(SUMMARY_METRICS)
    n_axes = len(axes)
    fig, panels = plt.subplots(n_metrics, n_axes, figsize=(4.5*n_axes, 3*n_metrics),
                                squeeze=False)

    width = 0.36
    x = np.arange(len(timepoints))

    for r, (metric_key, metric_label) in enumerate(SUMMARY_METRICS):
        for c, ax_label in enumerate(axes):
            panel = panels[r, c]
            col = f'{metric_key}_{ax_label}'
            for i, grp in enumerate(['Control', 'Concussion']):
                means = []; sems = []
                for tp in timepoints:
                    cell = df[(df['group'] == grp) & (df['timepoint'] == tp)][col]
                    means.append(cell.mean() if not cell.empty else np.nan)
                    sems.append(_sem(cell.values))
                offset = (i - 0.5) * width
                panel.bar(x + offset, means, width, yerr=sems,
                          color=GROUP_COLORS[grp], alpha=0.85,
                          label=grp, edgecolor='black', lw=0.5,
                          capsize=4, error_kw=dict(lw=1))
            panel.set_xticks(x); panel.set_xticklabels(timepoints)
            panel.set_ylabel(metric_label if c == 0 else '')
            if r == 0:
                panel.set_title(f'{ax_label} axis')
            if r == n_metrics - 1:
                panel.set_xlabel('Timepoint')
            if r == 0 and c == n_axes - 1:
                panel.legend(fontsize=9, loc='best')
            panel.grid(axis='y', alpha=0.3)

    fig.suptitle(f'Per-trial summary metrics — {condition} trials, '
                  f'group × timepoint comparison (error bars = SEM)',
                  fontsize=11, y=0.995)
    fig.tight_layout(); fig.savefig(output_path, dpi=130, bbox_inches='tight')
    plt.close(fig)
