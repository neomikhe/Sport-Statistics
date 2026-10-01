import numpy as np

from core.calibration.isotonic import (
    BinaryIsotonicCalibrator,
    BinaryIsotonicCalibratorNumpy,
    IsotonicCalibrator3way,
    IsotonicCalibratorNumpy,
    load_binary_calibrator,
    load_calibrator,
)


def _biased_dataset(n=3000, seed=7):
    rng = np.random.default_rng(seed)
    p_home = rng.uniform(0.2, 0.8, n)
    p_away = (1 - p_home) * 0.55
    p_draw = 1 - p_home - p_away
    probs = np.stack([p_home, p_draw, p_away], axis=1)
    true_home = p_home * 0.75
    u = rng.uniform(0, 1, n)
    outcomes = np.where(u < true_home, "H",
                        np.where(u < true_home + p_draw, "D", "A"))
    return probs, outcomes


def test_numpy_inference_matches_sklearn(tmp_path):
    probs, outcomes = _biased_dataset()
    cal = IsotonicCalibrator3way().fit(probs, outcomes)
    ref = cal.transform(probs)

    path = tmp_path / "cal.joblib"
    cal.save(path)
    npy = IsotonicCalibratorNumpy.load(path)
    got = npy.transform(probs)

    assert np.allclose(ref, got, atol=1e-9)


def test_rows_sum_to_one(tmp_path):
    probs, outcomes = _biased_dataset()
    path = tmp_path / "cal.joblib"
    IsotonicCalibrator3way().fit(probs, outcomes).save(path)
    out = IsotonicCalibratorNumpy.load(path).transform(probs)
    assert np.allclose(out.sum(axis=1), 1.0, atol=1e-9)


def test_calibration_corrects_home_bias(tmp_path):
    probs, outcomes = _biased_dataset()
    path = tmp_path / "cal.joblib"
    IsotonicCalibrator3way().fit(probs, outcomes).save(path)
    out = IsotonicCalibratorNumpy.load(path).transform(probs)
    real_home_rate = float((outcomes == "H").mean())
    assert out[:, 0].mean() < probs[:, 0].mean()
    assert abs(out[:, 0].mean() - real_home_rate) < abs(probs[:, 0].mean() - real_home_rate)


def test_transform_accepts_single_row(tmp_path):
    probs, outcomes = _biased_dataset()
    path = tmp_path / "cal.joblib"
    IsotonicCalibrator3way().fit(probs, outcomes).save(path)
    npy = IsotonicCalibratorNumpy.load(path)
    one = npy.transform([[0.6, 0.25, 0.15]])
    assert one.shape == (1, 3)
    assert abs(one.sum() - 1.0) < 1e-9


def test_load_calibrator_missing_returns_none(tmp_path):
    assert load_calibrator(tmp_path / "no_existe.joblib") is None


def _biased_binary(n=3000, seed=11):
    rng = np.random.default_rng(seed)
    p_home = rng.uniform(0.2, 0.8, n)
    y_home = (rng.uniform(0, 1, n) < p_home * 0.75).astype(float)
    return p_home, y_home


def test_binary_numpy_matches_sklearn(tmp_path):
    p_home, y_home = _biased_binary()
    cal = BinaryIsotonicCalibrator().fit(p_home, y_home)
    ref = cal.transform(p_home)
    path = tmp_path / "bin.joblib"
    cal.save(path)
    npy = BinaryIsotonicCalibratorNumpy.load(path)
    got = np.array([npy.calibrate_home(x) for x in p_home])
    assert np.allclose(ref, got, atol=1e-9)


def test_binary_corrects_home_bias(tmp_path):
    p_home, y_home = _biased_binary()
    path = tmp_path / "bin.joblib"
    BinaryIsotonicCalibrator().fit(p_home, y_home).save(path)
    npy = BinaryIsotonicCalibratorNumpy.load(path)
    cal_mean = np.mean([npy.calibrate_home(x) for x in p_home])
    assert cal_mean < p_home.mean()
    assert abs(cal_mean - y_home.mean()) < abs(p_home.mean() - y_home.mean())


def test_binary_output_in_unit_interval(tmp_path):
    p_home, y_home = _biased_binary()
    path = tmp_path / "bin.joblib"
    BinaryIsotonicCalibrator().fit(p_home, y_home).save(path)
    npy = BinaryIsotonicCalibratorNumpy.load(path)
    for x in (0.0, 0.05, 0.5, 0.95, 1.0):
        v = npy.calibrate_home(x)
        assert 0.0 <= v <= 1.0


def test_load_binary_calibrator_missing_returns_none(tmp_path):
    assert load_binary_calibrator(tmp_path / "no_existe.joblib") is None
