"""
Smoke tests for the CAVE FRF pipeline.

Run with:
    python tests/test_basic.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import numpy as np
from cave_frf import (
    build_stimulus, compute_frf, compute_summary_metrics,
    parse_trial_order, lookup_amplitude,
    parse_filename, FILENAME_PATTERN,
    load_cop_file, load_com_file, load_trial_file,
    analyze_trial, TrialEntry,
    STIM_FREQS_HZ, COMPONENT_WEIGHTS, TRIAL_DURATION_S,
    STIM_AXIS_BY_CONDITION,
)


def test_stimulus_zero_amplitude():
    s = build_stimulus(0.0, 1000, 1000)
    assert np.allclose(s, 0)


def test_stimulus_formula_matches():
    fs = 1000
    N = 120 * fs
    A = 0.08
    s = build_stimulus(A, N, fs)
    Y = np.fft.rfft(s)
    for f0, w in zip(STIM_FREQS_HZ, COMPONENT_WEIGHTS):
        center = int(round(f0 * N / fs))
        bin_amp = max(np.abs(Y[center-1:center+2])) * 2 / N
        expected = A * w
        assert 0.85 * expected < bin_amp < 1.05 * expected, \
            f"At {f0} Hz: expected ~{expected}, got {bin_amp}"


def test_frf_identity():
    fs = 1000
    N = 120 * fs
    s = build_stimulus(0.08, N, fs)
    _, gain, phase, coh = compute_frf(s, s, fs, STIM_FREQS_HZ)
    assert np.allclose(gain, 1.0, atol=1e-6)
    assert np.allclose(phase, 0.0, atol=1e-3)
    assert np.allclose(coh, 1.0, atol=1e-6)


def test_frf_scaled_response():
    fs = 1000
    N = 120 * fs
    s = build_stimulus(0.08, N, fs)
    r = 0.5 * s
    _, gain, phase, _ = compute_frf(s, r, fs, STIM_FREQS_HZ)
    assert np.allclose(gain, 0.5, atol=1e-6)
    assert np.allclose(phase, 0.0, atol=1e-3)


def test_frf_phase_shift():
    fs = 1000
    N = 120 * fs
    s = build_stimulus(0.08, N, fs)
    delay_samples = 100  # 100 ms
    r = np.roll(s, delay_samples)
    _, gain, phase_deg, _ = compute_frf(s, r, fs, STIM_FREQS_HZ)
    delay_s = delay_samples / fs
    expected_phase_deg = -360 * np.array(STIM_FREQS_HZ) * delay_s
    def wrap(x): return ((x + 180) % 360) - 180
    diff = wrap(phase_deg - expected_phase_deg)
    assert np.allclose(np.abs(diff), 0, atol=2.0), \
        f"phase off: got {phase_deg}, expected {expected_phase_deg}"


def test_summary_metrics_known_signals():
    """Path length and RMS should match analytic values for a known sine."""
    fs = 1000
    duration = 10
    t = np.arange(0, duration, 1/fs)
    A = 0.05
    f = 1.0
    sig = A * np.sin(2 * np.pi * f * t)

    # Use as cop_y (AP); set cop_x to zero so we know its metrics exactly
    metrics = compute_summary_metrics(np.zeros_like(sig), sig, fs)

    # AP RMS of A*sin should be A/sqrt(2)
    assert abs(metrics['rms_m_AP'] - A / np.sqrt(2)) < 1e-3

    # Total path length of A*sin over duration: 4 * A * f * duration (sum of |Δsin|)
    # because each cycle traces 4*A of arc length
    expected_path = 4 * A * f * duration
    assert abs(metrics['path_length_m_AP'] - expected_path) < 1e-2

    # ML axis was zero
    assert metrics['rms_m_ML'] == 0
    assert metrics['path_length_m_ML'] == 0
    assert metrics['mean_velocity_m_s_ML'] == 0


def test_stim_axis_mapping():
    """Standing → AP, walking → ML."""
    assert STIM_AXIS_BY_CONDITION['standing'] == 'AP'
    assert STIM_AXIS_BY_CONDITION['walking'] == 'ML'


def test_trial_order_parse():
    import tempfile
    text = """CAVE Adult Stimulus Factor Trial Order

Control_001_Acute
0.25
0.15
0.00
0.35
0.05

0.08
0.00
0.04

Concussion_001_Acute
0.15
0.35
0.05
0.25
0.00

0.00
0.08
0.04
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        f.write(text)
        path = f.name
    entries = parse_trial_order(path)
    assert len(entries) == 16

    e = lookup_amplitude(entries, 'Control', 1, 'Acute', 1)
    assert e.amplitude_m == 0.25 and e.condition == 'walking'

    e = lookup_amplitude(entries, 'Control', 1, 'Acute', 6)
    assert e.amplitude_m == 0.08 and e.condition == 'standing'


def test_config_loading():
    """Loading a different config should change the stimulus model."""
    import tempfile, textwrap
    from cave_frf import load_config
    from cave_frf import analysis as A

    # Snapshot original (CAVE) values
    orig_freqs = A.STIM_FREQS_HZ
    orig_n = A.N_COMPONENTS

    # Write a 3-component config to a temp file
    cfg_text = textwrap.dedent("""\
        study_name: "Test 3-component"
        stimulus:
          frequencies_hz: [0.2, 0.3, 0.5]
          weights:        [1.0, 0.5, 0.25]
          phases_rad:     [0.0, 0.0, 0.0]
          trial_duration_s: 60.0
        stim_axis_by_condition:
          quiet_standing: AP
        """)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(cfg_text)
        path = f.name

    load_config(path)
    assert A.N_COMPONENTS == 3
    assert A.STIM_FREQS_HZ == (0.2, 0.3, 0.5)
    assert A.TRIAL_DURATION_S == 60.0
    assert A.STIM_AXIS_BY_CONDITION == {'quiet_standing': 'AP'}

    # Restore CAVE defaults so other tests aren't polluted
    load_config()  # reloads default
    assert A.STIM_FREQS_HZ == orig_freqs
    assert A.N_COMPONENTS == orig_n


def test_config_validation():
    """Mismatched-length lists should raise."""
    import tempfile, textwrap
    from cave_frf import load_config

    cfg_text = textwrap.dedent("""\
        stimulus:
          frequencies_hz: [0.2, 0.3]
          weights:        [1.0]            # wrong length
          phases_rad:     [0.0, 0.0]
          trial_duration_s: 60.0
        """)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(cfg_text)
        path = f.name

    raised = False
    try:
        load_config(path)
    except ValueError:
        raised = True
    assert raised, "load_config should raise ValueError on mismatched lengths"

    load_config()  # restore default


def test_parse_filename_cop_with_spaces():
    """Vicon's actual COP filename: spaces around dash, plain 'COP' suffix."""
    p = parse_filename('CAVE_Concussion_001_Acute_6 - COP.txt')
    assert p is not None
    assert p['group'] == 'Concussion'
    assert p['subject_id'] == 1
    assert p['timepoint'] == 'Acute'
    assert p['trial_number'] == 6
    assert p['file_type'] == 'COP'


def test_parse_filename_com_export():
    """Vicon's actual COM filename: spaces around dash, 'COM_Export' suffix."""
    p = parse_filename('CAVE_Concussion_001_Acute_1 - COM_Export.txt')
    assert p is not None
    assert p['file_type'] == 'COM'
    assert p['trial_number'] == 1


def test_parse_filename_underscore_variant():
    """Older test data sometimes used underscores around the dash."""
    p = parse_filename('CAVE_Control_001_Acute_6_-_COP.txt')
    assert p is not None
    assert p['file_type'] == 'COP'
    p = parse_filename('CAVE_Control_001_Acute_2_-_COM_Export.txt')
    assert p is not None
    assert p['file_type'] == 'COM'


def test_parse_filename_subacute_variants():
    """Both 'SubAcute' and 'Subacute' should parse and normalize."""
    for tp_in in ('SubAcute', 'Subacute'):
        p = parse_filename(f'CAVE_Control_002_{tp_in}_3 - COM_Export.txt')
        assert p is not None
        assert p['timepoint'] == 'SubAcute'


def test_parse_filename_rejects_non_cave():
    assert parse_filename('random_file.txt') is None
    assert parse_filename('CAVE_Control_001_Acute_1 - GVS.txt') is None  # wrong suffix
    assert parse_filename('CAVE_Control_001.txt') is None                 # too short


def _write_synthetic_cop_file(path, fs=1000, duration_s=10):
    """Write a tiny COP-format file for round-trip testing."""
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    cop_x = 0.001 * np.sin(2*np.pi*0.5*t)
    cop_y = 0.002 * np.sin(2*np.pi*0.5*t)
    header = (
        "Caccese - CAVE\t// User ID\n"
        "12-1-2023\t// Evaluation date\n"
        "CAVE_Test_001_Acute_6\t01-01-2024\t12:00:00:000\t// Source file\n"
        f"{float(fs):.3f}\t// Sampling rate\n"
        f"{float(duration_s):.3f}\t// Data capture period\n"
        "\n\n\n"
        "Sample #\tCOP_X\tCOP_Y\t\n"
    )
    with open(path, 'w') as f:
        f.write(header)
        for i in range(n):
            f.write(f"{i}\t{cop_x[i]:.6f}\t{cop_y[i]:.6f}\t\n")


def _write_synthetic_com_file(path, fs=100, duration_s=10):
    """Write a tiny COM-format file (6 cols incl. Visual_Stim and GVS)."""
    n = int(fs * duration_s)
    t = np.arange(n) / fs
    comx = 0.05 * np.sin(2*np.pi*0.5*t)
    comy = 0.7 + 0.001 * t                        # slow drift
    comz = 0.9 * np.ones(n)
    visual_stim = 0.10 * np.sin(2*np.pi*0.5*t)    # the input signal
    gvs = 0.5 * visual_stim                        # what Vicon actually logs
    header = (
        "Caccese - CAVE\t// User ID\n"
        "12-1-2023\t// Evaluation date\n"
        "CAVE_Test_001_Acute_1\t01-01-2024\t12:00:00:000\t// Source file\n"
        f"{float(fs):.3f}\t// Sampling rate\n"
        f"{float(duration_s):.3f}\t// Data capture period\n"
        "\n\n\n"
        "Sample #\tCOMx\tCOMy\tCOMz\tVisual_Stim\tGVS\t\n"
    )
    with open(path, 'w') as f:
        f.write(header)
        for i in range(n):
            f.write(f"{i}\t{comx[i]:.6f}\t{comy[i]:.6f}\t{comz[i]:.6f}\t"
                    f"{visual_stim[i]:.6f}\t{gvs[i]:.6f}\t\n")


def test_load_cop_file_round_trip():
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        path = f.name
    try:
        _write_synthetic_cop_file(path, fs=1000, duration_s=2)
        fs, cop_x, cop_y = load_cop_file(path)
        assert fs == 1000.0
        assert len(cop_x) == 2000
        assert len(cop_y) == 2000
        # Amplitudes should match what we wrote (within fp precision)
        assert 0.0009 < cop_x.max() < 0.0011
        assert 0.0019 < cop_y.max() < 0.0021
    finally:
        os.unlink(path)


def test_load_com_file_extracts_stim():
    import tempfile, os
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        path = f.name
    try:
        _write_synthetic_com_file(path, fs=100, duration_s=2)
        fs, com_x, com_y, stim = load_com_file(path)
        assert fs == 100.0
        assert len(com_x) == len(com_y) == len(stim) == 200
        # Visual_Stim should be the 0.10-amplitude sine we wrote
        assert 0.099 < stim.max() < 0.101
        # COMx (response) should be the 0.05-amplitude sine
        assert 0.049 < com_x.max() < 0.051
        # COMy starts ~0.7 (drift baseline), not zero
        assert 0.69 < com_y[0] < 0.71
    finally:
        os.unlink(path)


def test_load_trial_file_dispatches():
    """load_trial_file should route to COP or COM loader based on filename."""
    import tempfile, os
    with tempfile.TemporaryDirectory() as d:
        cop_path = os.path.join(d, 'CAVE_Control_001_Acute_6 - COP.txt')
        com_path = os.path.join(d, 'CAVE_Control_001_Acute_1 - COM_Export.txt')
        _write_synthetic_cop_file(cop_path, fs=1000, duration_s=2)
        _write_synthetic_com_file(com_path, fs=100, duration_s=2)

        cop_result = load_trial_file(cop_path)
        com_result = load_trial_file(com_path)

    assert cop_result['file_type'] == 'COP'
    assert cop_result['fs'] == 1000.0
    assert cop_result['stim'] is None  # COP files don't log stimulus

    assert com_result['file_type'] == 'COM'
    assert com_result['fs'] == 100.0
    assert com_result['stim'] is not None
    assert len(com_result['stim']) == len(com_result['signal_ml'])


def test_analyze_trial_routes_by_filetype():
    """analyze_trial should produce results from both COP and COM files."""
    import tempfile, os
    from cave_frf import analysis as A

    # Build a 120-s trial so the FRF pipeline has its full window
    with tempfile.TemporaryDirectory() as d:
        cop_path = os.path.join(d, 'CAVE_Control_001_Acute_6 - COP.txt')
        com_path = os.path.join(d, 'CAVE_Control_001_Acute_1 - COM_Export.txt')
        _write_synthetic_cop_file(cop_path, fs=1000,
                                   duration_s=int(A.TRIAL_DURATION_S))
        _write_synthetic_com_file(com_path, fs=100,
                                   duration_s=int(A.TRIAL_DURATION_S))

        # Standing trial — COP
        e_stand = TrialEntry('Control', 1, 'Acute', 'standing', 6, 0.08)
        r_stand = analyze_trial(cop_path, e_stand)
        assert r_stand['file_type'] == 'COP'
        assert r_stand['fs_hz'] == 1000.0
        assert r_stand['stim_axis'] == 'AP'
        assert set(r_stand['frf_per_axis'].keys()) == {'AP', 'ML'}

        # Walking trial — COM
        e_walk = TrialEntry('Control', 1, 'Acute', 'walking', 1, 0.25)
        r_walk = analyze_trial(com_path, e_walk)
        assert r_walk['file_type'] == 'COM'
        assert r_walk['fs_hz'] == 100.0
        assert r_walk['stim_axis'] == 'ML'
        assert set(r_walk['frf_per_axis'].keys()) == {'AP', 'ML'}


if __name__ == '__main__':
    tests = [v for k, v in globals().items() if k.startswith('test_')]
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    if failed:
        print(f"\n{failed} tests failed")
        sys.exit(1)
    print(f"\nAll {len(tests)} tests passed")
