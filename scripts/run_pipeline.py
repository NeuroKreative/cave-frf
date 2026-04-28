"""
CLI runner for CAVE FRF analysis. Use this for batch processing or cron jobs
when you don't need the UI.

Examples
--------
    # Standing only
    python scripts/run_pipeline.py \\
        --data-dir "/path/to/COM Data" \\
        --trial-order "Updated- CAVE Adult Stimulus Factor Trial.txt" \\
        --frf-csv frf_results.csv \\
        --summary-csv summary_metrics.csv \\
        --condition standing

    # Walking only, also generate all plots
    python scripts/run_pipeline.py \\
        --data-dir "/path/to/COM Data" \\
        --trial-order trial_order.txt \\
        --frf-csv walking_frf.csv \\
        --summary-csv walking_summary.csv \\
        --condition walking \\
        --plots-dir plots/

    # Force full re-run (no cache)
    python scripts/run_pipeline.py \\
        --data-dir "/path/to/COM Data" \\
        --trial-order trial_order.txt \\
        --frf-csv frf.csv --summary-csv sum.csv \\
        --no-cache
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from cave_frf import run_pipeline, discover_files
from cave_frf.plots import (
    plot_gain_phase, plot_coherence, plot_nyquist, plot_spectra,
    plot_hwang_recovery, plot_summary_metrics,
)


def main():
    p = argparse.ArgumentParser(
        description="Run CAVE gain/phase analysis on a folder of COP files."
    )
    p.add_argument('--data-dir', required=True,
                   help="Top-level data folder (e.g. 'COM Data')")
    p.add_argument('--trial-order', required=True,
                   help="Path to the trial-order text file")
    p.add_argument('--frf-csv', required=True,
                   help="Output CSV for FRF results (one row per trial × freq × axis)")
    p.add_argument('--summary-csv', required=True,
                   help="Output CSV for per-trial summary metrics")
    p.add_argument('--condition', choices=['standing', 'walking', 'both'],
                   default='both',
                   help="Which condition(s) to analyze (default: both)")
    p.add_argument('--no-baseline', action='store_true',
                   help="Skip amp=0 trials")
    p.add_argument('--no-cache', action='store_true',
                   help="Don't reuse cached results — re-process every file")
    p.add_argument('--plots-dir',
                   help="If set, also generate plots here")
    p.add_argument('--axis', default='stim_matched',
                   choices=['stim_matched', 'AP', 'ML'],
                   help="Axis for FRF plots (default: stim_matched)")
    args = p.parse_args()

    cache = None if args.no_cache else args.frf_csv

    frf_df, summary_df = run_pipeline(
        cop_dir=args.data_dir,
        trial_order_path=args.trial_order,
        output_csv=args.frf_csv,
        summary_csv=args.summary_csv,
        condition_filter=args.condition,
        include_baseline=not args.no_baseline,
        cache_path=cache,
    )

    if args.plots_dir:
        plots_dir = Path(args.plots_dir)
        plots_dir.mkdir(exist_ok=True, parents=True)

        plot_gain_phase(frf_df, plots_dir / 'gain_phase_bars.png', axis=args.axis)
        plot_coherence(frf_df, plots_dir / 'coherence.png', axis=args.axis)
        plot_nyquist(frf_df, plots_dir / 'nyquist.png', axis=args.axis)
        plot_hwang_recovery(frf_df, plots_dir / 'hwang_recovery.png', axis=args.axis)

        # Summary metrics — one plot per condition present in data
        for cond in summary_df['condition'].unique():
            plot_summary_metrics(summary_df,
                                  plots_dir / f'summary_{cond}.png',
                                  condition=cond)

        # Spectra (first 8 trials)
        files = discover_files(args.data_dir, recursive=True)
        if files:
            spectra_axis = 'AP' if args.axis in ('stim_matched', 'AP') else 'ML'
            plot_spectra(files[:8], args.trial_order,
                         plots_dir / 'spectra.png', axis=spectra_axis)

        print(f"Plots written to {plots_dir}/")

    print(f"Done. {len(frf_df)} FRF rows, {len(summary_df)} summary rows.")


if __name__ == '__main__':
    main()
