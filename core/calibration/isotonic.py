from pathlib import Path

import joblib
import numpy as np

_NOT_FITTED = "Calibrator no ajustado. Llama fit() primero."


class IsotonicCalibrator3way:
    def __init__(self):
        from sklearn.isotonic import IsotonicRegression

        self.reg_h = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.reg_d = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self.reg_a = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._fitted = False

    def fit(self, probs, outcomes):
        probs = np.asarray(probs, dtype=float)
        outcomes = np.asarray(outcomes)
        self.reg_h.fit(probs[:, 0], (outcomes == "H").astype(float))
        self.reg_d.fit(probs[:, 1], (outcomes == "D").astype(float))
        self.reg_a.fit(probs[:, 2], (outcomes == "A").astype(float))
        self._fitted = True
        return self

    def transform(self, probs):
        if not self._fitted:
            raise RuntimeError(_NOT_FITTED)
        probs = np.asarray(probs, dtype=float)
        ch = self.reg_h.transform(probs[:, 0])
        cd = self.reg_d.transform(probs[:, 1])
        ca = self.reg_a.transform(probs[:, 2])
        calibrated = np.stack([ch, cd, ca], axis=1)
        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums < 1e-9, 1e-9, row_sums)
        return calibrated / row_sums

    def fit_transform(self, probs, outcomes):
        return self.fit(probs, outcomes).transform(probs)

    def save(self, path) -> None:
        if not self._fitted:
            raise RuntimeError(_NOT_FITTED)
        payload = {
            "version": "iso3way_v1",
            "h": (np.asarray(self.reg_h.X_thresholds_), np.asarray(self.reg_h.y_thresholds_)),
            "d": (np.asarray(self.reg_d.X_thresholds_), np.asarray(self.reg_d.y_thresholds_)),
            "a": (np.asarray(self.reg_a.X_thresholds_), np.asarray(self.reg_a.y_thresholds_)),
        }
        joblib.dump(payload, path)


class IsotonicCalibratorNumpy:
    def __init__(self, h, d, a):
        self._h = (np.asarray(h[0], dtype=float), np.asarray(h[1], dtype=float))
        self._d = (np.asarray(d[0], dtype=float), np.asarray(d[1], dtype=float))
        self._a = (np.asarray(a[0], dtype=float), np.asarray(a[1], dtype=float))

    @classmethod
    def load(cls, path):
        p = joblib.load(path)
        return cls(p["h"], p["d"], p["a"])

    def transform(self, probs):
        probs = np.asarray(probs, dtype=float)
        if probs.ndim == 1:
            probs = probs[None, :]
        ch = np.interp(probs[:, 0], self._h[0], self._h[1])
        cd = np.interp(probs[:, 1], self._d[0], self._d[1])
        ca = np.interp(probs[:, 2], self._a[0], self._a[1])
        calibrated = np.stack([ch, cd, ca], axis=1)
        row_sums = calibrated.sum(axis=1, keepdims=True)
        row_sums = np.where(row_sums < 1e-9, 1e-9, row_sums)
        return calibrated / row_sums


def load_calibrator(path):
    if not Path(path).exists():
        return None
    try:
        return IsotonicCalibratorNumpy.load(path)
    except Exception:
        return None


class BinaryIsotonicCalibrator:
    def __init__(self):
        from sklearn.isotonic import IsotonicRegression

        self.reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._fitted = False

    def fit(self, p_home, y_home):
        self.reg.fit(np.asarray(p_home, dtype=float), np.asarray(y_home, dtype=float))
        self._fitted = True
        return self

    def transform(self, p_home):
        if not self._fitted:
            raise RuntimeError(_NOT_FITTED)
        return self.reg.transform(np.asarray(p_home, dtype=float))

    def save(self, path) -> None:
        if not self._fitted:
            raise RuntimeError(_NOT_FITTED)
        payload = {
            "version": "iso2way_v1",
            "x": np.asarray(self.reg.X_thresholds_),
            "y": np.asarray(self.reg.y_thresholds_),
        }
        joblib.dump(payload, path)


class BinaryIsotonicCalibratorNumpy:
    def __init__(self, x, y):
        self._x = np.asarray(x, dtype=float)
        self._y = np.asarray(y, dtype=float)

    @classmethod
    def load(cls, path):
        p = joblib.load(path)
        return cls(p["x"], p["y"])

    def calibrate_home(self, p_home: float) -> float:
        return float(np.interp(float(p_home), self._x, self._y))


def load_binary_calibrator(path):
    if not Path(path).exists():
        return None
    try:
        return BinaryIsotonicCalibratorNumpy.load(path)
    except Exception:
        return None
