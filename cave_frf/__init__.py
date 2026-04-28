"""CAVE FRF analysis package."""
from .analysis import (
    STIM_FREQS_HZ, COMPONENT_WEIGHTS, COMPONENT_PHASES, TRIAL_DURATION_S,
    STIM_AXIS_BY_CONDITION,
    TrialEntry,
    parse_trial_order,
    lookup_amplitude,
    parse_filename,
    FILENAME_PATTERN,
    load_cop_file,
    load_com_file,
    load_trial_file,
    load_stimulus_file,
    build_stimulus,
    compute_frf,
    compute_summary_metrics,
    analyze_trial,
    discover_files,
    run_pipeline,
    load_config,
    get_active_config,
    DEFAULT_CONFIG_PATH,
)
from . import plots

__version__ = "0.5.0"
