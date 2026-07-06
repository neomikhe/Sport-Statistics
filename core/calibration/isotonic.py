"""
Calibracion isotonica multiclase para probabilidades 1X2.

Para cada clase H/D/A, ajusta una IsotonicRegression independiente sobre el
conjunto de validacion. En transform, re-normaliza para que las 3 probabilidades
sumen 1.

La calibracion isotonica es no parametrica y monotona. Corrige sesgos sistematicos
del modelo (ej.: sobrepredecir locales) sin destruir el orden relativo.

Dos clases:
  - IsotonicCalibrator3way   -> ENTRENAMIENTO (necesita sklearn). Se usa en el
    script de calibración, no en la app.
  - IsotonicCalibratorNumpy  -> INFERENCIA (solo numpy, np.interp). Es lo que la
    app carga en la nube: NO requiere sklearn, igual que el modelo Poisson evita
    statsmodels en predicción.
"""
from pathlib import Path

import joblib
import numpy as np

_NOT_FITTED = "Calibrator no ajustado. Llama fit() primero."


class IsotonicCalibrator3way:
    """Calibrador isotonico para clasificacion 3-way (H, D, A). Solo entrenamiento."""

    def __init__(self):
        # sklearn se importa de forma perezosa: así el módulo se puede importar en
        # la nube (para IsotonicCalibratorNumpy) sin tener sklearn instalado.
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
        """Persiste SOLO los puntos de interpolación (numpy). Cargar el artefacto
        para inferir NO requerirá sklearn."""
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
    """Calibrador 3-way de SOLO INFERENCIA con np.interp (sin sklearn).

    np.interp mantiene el valor constante fuera del rango de entrenamiento, lo que
    reproduce IsotonicRegression(out_of_bounds='clip').
    """

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
    """Devuelve un IsotonicCalibratorNumpy, o None si el artefacto no existe o falla."""
    if not Path(path).exists():
        return None
    try:
        return IsotonicCalibratorNumpy.load(path)
    except Exception:
        return None


# ======================================================================
#  Calibrador BINARIO (2-way) para moneyline: NBA, MLB, tenis
# ======================================================================
class BinaryIsotonicCalibrator:
    """Calibra P(local/jugador1 gana). p_away = 1 - p_home (suma 1 garantizada).

    Solo entrenamiento (necesita sklearn, importado de forma perezosa).
    """

    def __init__(self):
        from sklearn.isotonic import IsotonicRegression

        self.reg = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
        self._fitted = False

    def fit(self, p_home, y_home):
        """p_home: prob del modelo (Nx1). y_home: 1 si ganó el local/jugador1, si no 0."""
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
    """Inferencia binaria con np.interp (sin sklearn)."""

    def __init__(self, x, y):
        self._x = np.asarray(x, dtype=float)
        self._y = np.asarray(y, dtype=float)

    @classmethod
    def load(cls, path):
        p = joblib.load(path)
        return cls(p["x"], p["y"])

    def calibrate_home(self, p_home: float) -> float:
        """Devuelve la prob calibrada del local/jugador1 (escalar en [0, 1])."""
        return float(np.interp(float(p_home), self._x, self._y))


def load_binary_calibrator(path):
    """Devuelve un BinaryIsotonicCalibratorNumpy, o None si no existe/falla."""
    if not Path(path).exists():
        return None
    try:
        return BinaryIsotonicCalibratorNumpy.load(path)
    except Exception:
        return None
