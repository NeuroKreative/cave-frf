"""
CAVE FRF Analysis — Streamlit UI

For students/lab members. Run with:
    streamlit run app.py

Then your browser opens at http://localhost:8501. Point at a folder of
COP files, click Run, see plots, download CSVs. All processing is local.
"""
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd
import streamlit as st
import matplotlib
matplotlib.use('Agg')

from cave_frf import (
    parse_trial_order, lookup_amplitude, run_pipeline, discover_files,
    STIM_FREQS_HZ, COMPONENT_WEIGHTS, TRIAL_DURATION_S,
    STIM_AXIS_BY_CONDITION,
    load_config, get_active_config, DEFAULT_CONFIG_PATH,
)
from cave_frf.plots import (
    plot_gain_phase, plot_coherence, plot_nyquist, plot_spectra,
    plot_hwang_recovery, plot_summary_metrics,
    GROUP_COLORS,
)


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="CAVE FRF Analysis",
    page_icon="🧠",
    layout="wide",
)

# Persistent state
for key, default in [('frf_df', None), ('summary_df', None),
                      ('last_cop_dir', ""), ('last_run_files', [])]:
    if key not in st.session_state:
        st.session_state[key] = default


# ---------------------------------------------------------------------------
# Sidebar — methodology reference
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("# 🧠 CAVE FRF")
    st.markdown(
        "Frequency response analysis of postural sway to a sum-of-sines "
        "visual perturbation."
    )

    st.markdown("---")

    # =========================================================
    # Stimulus configuration panel — collapsible
    # =========================================================
    with st.expander("⚙️ Stimulus configuration", expanded=False):
        active_cfg = get_active_config()
        study_name = active_cfg.get('study_name', 'unnamed') if active_cfg else 'unnamed'
        st.caption(f"**Active config:** {study_name}")

        st.latex(r"D(t) = A \cdot \sum_{i=1}^{N} w_i \, \sin(2\pi f_i t + \varphi_i)")

        freqs_str = ", ".join(f"{f}" for f in STIM_FREQS_HZ)
        weights_str = ", ".join(f"{w}" for w in COMPONENT_WEIGHTS)
        axis_str = ", ".join(f"{c}→{a}" for c, a in STIM_AXIS_BY_CONDITION.items())
        st.markdown(
            f"- N components: **{len(STIM_FREQS_HZ)}**\n"
            f"- frequencies (Hz): **{freqs_str}**\n"
            f"- weights: **{weights_str}**\n"
            f"- duration: **{TRIAL_DURATION_S:.0f} s**\n"
            f"- axis mapping: **{axis_str}**"
        )

        st.markdown("**Load a different config file:**")
        st.caption(
            "To run on data from a different protocol, point at a YAML config "
            "matching that study. See `configs/example_other_lab.yaml` for a "
            "template."
        )
        custom_cfg_path = st.text_input(
            "Path to YAML config",
            value="",
            placeholder=str(DEFAULT_CONFIG_PATH),
            key='custom_cfg_path',
        )
        if st.button("Load config", use_container_width=True, key='load_cfg_btn'):
            try:
                if custom_cfg_path.strip():
                    load_config(custom_cfg_path.strip())
                    st.success(f"Loaded: {custom_cfg_path}")
                else:
                    load_config()  # reload default
                    st.success(f"Reloaded default ({DEFAULT_CONFIG_PATH.name})")
                st.rerun()
            except Exception as e:
                st.error(f"Could not load config: {e}")

    st.markdown("---")
    st.markdown("### Folder layout")
    st.code(
        "COM_Data/\n"
        "  Standing/\n"
        "    Control/\n"
        "      Acute/\n"
        "        CAVE_Control_001_Acute_6_-_COP.txt\n"
        "      SubAcute/\n"
        "      Chronic/\n"
        "    Concussion/\n"
        "  Walking/\n"
        "    ...",
        language="text",
    )
    st.caption("Point at the top-level folder; subdirectories walked automatically.")

    st.markdown("---")
    st.caption("CAVE FRF · v0.4 · local-only, no data leaves this machine")


# ---------------------------------------------------------------------------
# Main header
# ---------------------------------------------------------------------------
st.title("CAVE Gain / Phase Analysis")
st.caption(
    "Drop in a folder of COP files, get gain, phase, coherence, and summary "
    "sway metrics per trial. All processing happens on this computer — "
    "nothing is uploaded anywhere."
)


# ---------------------------------------------------------------------------
# Step 1 — Trial-order
# ---------------------------------------------------------------------------
st.markdown("### 1 — Trial-order file")
trial_col1, trial_col2 = st.columns([3, 2])
with trial_col1:
    trial_upload = st.file_uploader(
        "Trial-order text file",
        type=['txt'],
        help="The file mapping each (subject, timepoint, trial) to its amplitude.",
    )
with trial_col2:
    bundled = Path(__file__).parent / 'Updated-_CAVE_Adult_Stimulus_Factor_Trial.txt'
    use_bundled = st.checkbox(
        "Use bundled file",
        value=bundled.exists() and trial_upload is None,
        disabled=not bundled.exists(),
    )

trial_order_path = None
if use_bundled and bundled.exists():
    trial_order_path = bundled
    st.success(f"Using bundled: `{bundled.name}`")
elif trial_upload is not None:
    text = trial_upload.getvalue().decode('utf-8', errors='replace')
    tmp = Path(tempfile.gettempdir()) / 'cave_trial_order.txt'
    tmp.write_text(text)
    trial_order_path = tmp
    st.success(f"Loaded: `{trial_upload.name}`")


# ---------------------------------------------------------------------------
# Step 2 — Folder
# ---------------------------------------------------------------------------
st.markdown("### 2 — Data folder")
cop_dir = st.text_input(
    "Path to top-level COM Data folder on your machine",
    value=st.session_state.last_cop_dir,
    placeholder="/Users/yourname/CAVE/COM Data",
    help="The folder that contains Standing/ and Walking/ subdirectories.",
)

files_found = []
if cop_dir and Path(cop_dir).exists():
    st.session_state.last_cop_dir = cop_dir
    try:
        files_found = discover_files(cop_dir, recursive=True)
    except Exception as e:
        st.error(f"Error walking folder: {e}")

    if files_found:
        df_files = pd.DataFrame(files_found)
        df_files['condition'] = df_files['condition_from_path'].fillna('?')
        breakdown = (
            df_files
            .groupby(['condition', 'group', 'timepoint'])
            .size()
            .reset_index(name='n_files')
        )
        st.success(f"Found **{len(files_found)}** COP files")
        with st.expander("Breakdown by condition / group / timepoint"):
            st.dataframe(breakdown, hide_index=True, use_container_width=True)
    else:
        st.warning("No CAVE COP files found in that folder.")
elif cop_dir:
    st.error(f"Folder does not exist: {cop_dir}")


# ---------------------------------------------------------------------------
# Step 3 — Filters
# ---------------------------------------------------------------------------
st.markdown("### 3 — Analyze")
fc1, fc2, fc3 = st.columns(3)
with fc1:
    condition_filter = st.radio(
        "Condition",
        ['standing', 'walking', 'both'],
        index=0,
        help="Standing analyzes COP_Y (AP); walking analyzes COP_X (ML).",
    )
with fc2:
    include_baseline = st.checkbox(
        "Include amp=0 baseline trials",
        value=True,
    )
with fc3:
    use_cache = st.checkbox(
        "Skip already-processed trials",
        value=True,
        help="Reuses results from the previous run for trials that haven't changed. "
             "Speeds up re-runs as new subjects are added.",
    )

cache_dir = Path(tempfile.gettempdir()) / 'cave_frf_cache'
cache_dir.mkdir(exist_ok=True)
frf_cache = cache_dir / 'frf_results.csv'
summary_cache = cache_dir / 'summary_metrics.csv'


# ---------------------------------------------------------------------------
# Run button
# ---------------------------------------------------------------------------
ready = trial_order_path is not None and bool(files_found)
run_clicked = st.button(
    "▶ Run analysis",
    type='primary',
    disabled=not ready,
    use_container_width=True,
)
if not ready:
    if trial_order_path is None:
        st.info("⬆ Upload or select a trial-order file")
    elif not files_found:
        st.info("⬆ Point at a data folder containing COP files")

if run_clicked:
    progress_bar = st.progress(0.0, text="Starting...")

    def cb(i, n, name):
        progress_bar.progress(i / n if n else 1.0,
                              text=f"Processing {name} ({i}/{n})")

    frf_df, summary_df = run_pipeline(
        cop_dir=cop_dir,
        trial_order_path=trial_order_path,
        output_csv=str(frf_cache),
        summary_csv=str(summary_cache),
        condition_filter=condition_filter,
        include_baseline=include_baseline,
        progress_callback=cb,
        cache_path=str(frf_cache) if use_cache else None,
    )
    progress_bar.empty()
    st.session_state.frf_df = frf_df
    st.session_state.summary_df = summary_df
    st.session_state.last_run_files = files_found


# ---------------------------------------------------------------------------
# Results
# ---------------------------------------------------------------------------
frf_df = st.session_state.frf_df
summary_df = st.session_state.summary_df

if frf_df is not None and len(frf_df) > 0:
    st.markdown("---")

    n_trials = frf_df[['group', 'subject_id', 'timepoint', 'condition', 'trial_number']].drop_duplicates().shape[0]
    n_subjects = frf_df[['group', 'subject_id']].drop_duplicates().shape[0]
    st.success(
        f"✅ **{n_trials}** trials from **{n_subjects}** subjects analyzed"
    )

    # Downloads
    dl_c1, dl_c2, dl_c3 = st.columns([1, 1, 3])
    with dl_c1:
        st.download_button(
            "📥 FRF results",
            data=frf_df.to_csv(index=False).encode('utf-8'),
            file_name='frf_results.csv',
            mime='text/csv',
            use_container_width=True,
        )
    with dl_c2:
        if summary_df is not None and len(summary_df):
            st.download_button(
                "📥 Summary metrics",
                data=summary_df.to_csv(index=False).encode('utf-8'),
                file_name='summary_metrics.csv',
                mime='text/csv',
                use_container_width=True,
            )
    with dl_c3:
        st.caption(f"FRF: {len(frf_df)} rows (trial × frequency × axis). "
                    f"Summary: {len(summary_df) if summary_df is not None else 0} rows (one per trial).")

    # =========================================================
    # Plot controls
    # =========================================================
    st.markdown("### Plot options")
    pc1, pc2, pc3 = st.columns(3)
    with pc1:
        plot_axis = st.radio(
            "Analysis axis",
            ['stim_matched', 'AP', 'ML'],
            index=0,
            help="`stim_matched` = AP for standing, ML for walking (default). "
                 "AP/ML force a single axis regardless of condition.",
            horizontal=True,
        )
    with pc2:
        plot_style = st.radio(
            "Plot style",
            ['Bar (per-trial)', 'Hwang-style (recovery)', 'Both'],
            index=0,
            help="Bar plots show per-trial values. Hwang-style line plots show "
                 "group means across timepoints — useful for the recovery story.",
            horizontal=True,
        )
    with pc3:
        summary_condition = st.radio(
            "Summary metrics — which condition?",
            ['walking', 'standing'],
            index=0 if 'walking' in (summary_df['condition'].unique() if summary_df is not None else []) else 1,
            horizontal=True,
        )

    # =========================================================
    # Plot tabs
    # =========================================================
    show_bar = plot_style in ('Bar (per-trial)', 'Both')
    show_hwang = plot_style in ('Hwang-style (recovery)', 'Both')

    tabs = st.tabs([
        "📊 Gain & Phase",
        "📊 Coherence",
        "🎯 Nyquist",
        "📈 Spectra",
        "📋 Summary metrics",
        "📑 Group means table",
    ])

    # --- Gain & Phase ---
    with tabs[0]:
        if show_bar:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
                plot_gain_phase(frf_df, tf.name, axis=plot_axis)
                st.image(tf.name)
        if show_hwang:
            st.markdown("**Recovery trajectory**")
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
                plot_hwang_recovery(frf_df, tf.name, axis=plot_axis)
                st.image(tf.name)

    # --- Coherence ---
    with tabs[1]:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
            plot_coherence(frf_df, tf.name, axis=plot_axis)
            st.image(tf.name)

    # --- Nyquist ---
    with tabs[2]:
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
            plot_nyquist(frf_df, tf.name, axis=plot_axis)
            st.image(tf.name)

    # --- Spectra ---
    with tabs[3]:
        files = st.session_state.last_run_files
        if files and trial_order_path is not None:
            spectra_axis = 'AP' if plot_axis in ('stim_matched', 'AP') else 'ML'
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
                plot_spectra(files, trial_order_path, tf.name,
                             max_files=8, axis=spectra_axis)
                st.image(tf.name)
            st.caption(f"Showing first 8 trials, COP_{spectra_axis}.")
        else:
            st.info("Re-run with the data folder set to see spectra.")

    # --- Summary metrics ---
    with tabs[4]:
        if summary_df is not None and len(summary_df) > 0:
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tf:
                plot_summary_metrics(summary_df, tf.name,
                                      condition=summary_condition)
                st.image(tf.name)
            st.caption(
                f"Per-trial summary metrics for **{summary_condition}** trials. "
                "Aggregated across amplitudes within each (group × timepoint) "
                "cell. Error bars are SEM across subjects."
            )
        else:
            st.info("No summary data — re-run pipeline to populate.")

    # --- Group means table ---
    with tabs[5]:
        if not frf_df[~frf_df.baseline_only].empty:
            cols_to_show = ['group', 'condition', 'timepoint',
                             'amplitude_m', 'frequency_hz', 'axis']
            grp = frf_df[~frf_df.baseline_only].groupby(cols_to_show)
            summary = grp.agg(
                n_trials=('gain', 'count'),
                gain=('gain', 'mean'),
                phase_deg=('phase_deg', 'mean'),
                coherence=('coherence', 'mean'),
            ).round(4).reset_index()
            st.dataframe(summary, hide_index=True, use_container_width=True)
        else:
            st.info("No non-baseline FRF data.")

elif frf_df is not None:
    st.warning("No trials matched the filter. Adjust filters and re-run.")
