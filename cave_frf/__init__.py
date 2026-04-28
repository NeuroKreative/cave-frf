"""CAVE FRF analysis package."""
from .analysis import (
    STIM_FREQS_HZ, COMPONENT_WEIGHTS, COMPONENT_PHASES, TRIAL_DURATION_S,
    STIM_AXIS_BY_CONDITION,
    TrialEntry,
    parse_trial_order,
    lookup_amplitude,
    load_cop_file,
    load_stimulus_file,
    build_stimulus,
    compute_frf,
    compute_summary_metrics,
    analyze_trial,
    discover_files,
    run_pipeline,
)
from . import plots

__version__ = "0.2.0"
