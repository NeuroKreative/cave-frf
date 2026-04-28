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
