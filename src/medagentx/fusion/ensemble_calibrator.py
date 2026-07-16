from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

from src.medagentx.fusion.calibration import agreement_field, default_densenet_thresholds
from src.medagentx.fusion.constants import DISEASE_LABELS, snake_label


class PerLabelEnsembleCalibrator:
    def __init__(self):
        self.models: dict[str, Any] = {}
        self.method: dict[str, str] = {}

    def fit(
        self,
        label: str,
        y_true: np.ndarray,
        densenet_prob: np.ndarray,
        fusion_prob: np.ndarray,
        ensemble_prob: np.ndarray,
        mask: np.ndarray,
    ) -> None:
        valid = mask.astype(bool) & np.isfinite(y_true) & np.isfinite(ensemble_prob)
        if valid.sum() < 8:
            self.models[label] = None
            self.method[label] = "passthrough"
            return

        yt = y_true[valid].astype(np.float32)
        d = densenet_prob[valid].astype(np.float32)
        f = fusion_prob[valid].astype(np.float32)
        e = ensemble_prob[valid].astype(np.float32)
        X = np.column_stack([d, f, e, d * f, np.abs(d - f), np.maximum(d, f)])

        if len(np.unique(yt)) < 2:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(e, yt)
            self.models[label] = iso
            self.method[label] = "isotonic_ensemble"
            return

        try:
            logistic = LogisticRegression(max_iter=2000, class_weight="balanced")
            logistic.fit(X, yt.astype(int))
            self.models[label] = logistic
            self.method[label] = "logistic_stack"
        except ValueError:
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(e, yt)
            self.models[label] = iso
            self.method[label] = "isotonic_ensemble"

    def predict(
        self,
        label: str,
        densenet_prob: float | None,
        fusion_prob: float | None,
        ensemble_prob: float | None,
    ) -> float | None:
        if ensemble_prob is None:
            return None

        model = self.models.get(label)
        if model is None:
            return float(ensemble_prob)

        method = self.method.get(label, "passthrough")
        d = 0.0 if densenet_prob is None else float(densenet_prob)
        f = 0.0 if fusion_prob is None else float(fusion_prob)
        e = float(ensemble_prob)

        if method == "logistic_stack":
            X = np.asarray([[d, f, e, d * f, abs(d - f), max(d, f)]], dtype=np.float32)
            return float(model.predict_proba(X)[0, 1])

        if method.startswith("isotonic"):
            return float(model.predict(np.asarray([e], dtype=np.float32))[0])

        return e

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"labels": {}, "model_version": "ensemble_calibrator_v1"}
        for label in DISEASE_LABELS:
            model = self.models.get(label)
            method = self.method.get(label, "passthrough")
            entry: dict[str, Any] = {"method": method}
            if model is None:
                entry["fitted"] = False
            elif method == "logistic_stack":
                entry["fitted"] = True
                entry["coef"] = model.coef_.astype(float).tolist()
                entry["intercept"] = model.intercept_.astype(float).tolist()
            elif method.startswith("isotonic"):
                entry["fitted"] = True
                entry["x_thresholds"] = model.X_thresholds_.astype(float).tolist()
                entry["y_thresholds"] = model.y_thresholds_.astype(float).tolist()
            payload["labels"][label] = entry
        return payload

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "PerLabelEnsembleCalibrator":
        calibrator = cls()
        labels_payload = payload.get("labels", {})
        for label in DISEASE_LABELS:
            entry = labels_payload.get(label, {})
            method = entry.get("method", "passthrough")
            calibrator.method[label] = method
            if not entry.get("fitted", False):
                calibrator.models[label] = None
                continue
            if method == "logistic_stack":
                model = LogisticRegression(max_iter=2000)
                model.classes_ = np.asarray([0, 1], dtype=int)
                model.coef_ = np.asarray(entry["coef"], dtype=np.float64)
                model.intercept_ = np.asarray(entry["intercept"], dtype=np.float64)
                calibrator.models[label] = model
            elif method.startswith("isotonic"):
                x = np.asarray(entry["x_thresholds"], dtype=np.float64)
                y = np.asarray(entry["y_thresholds"], dtype=np.float64)

                class _IsotonicProxy:
                    def predict(self, values):
                        arr = np.asarray(values, dtype=np.float64)
                        return np.clip(np.interp(arr, x, y), 0.0, 1.0)

                calibrator.models[label] = _IsotonicProxy()
            else:
                calibrator.models[label] = None
        return calibrator


def save_ensemble_calibrator(calibrator: PerLabelEnsembleCalibrator, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(calibrator.to_payload(), indent=2), encoding="utf-8")


def load_ensemble_calibrator(path: str | Path) -> PerLabelEnsembleCalibrator:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return PerLabelEnsembleCalibrator.from_payload(payload)


def build_calibration_arrays(
    label_df: pd.DataFrame,
    ensemble_df: pd.DataFrame,
    label_mode: str = "judge",
) -> tuple[dict[str, np.ndarray], pd.DataFrame]:
    from src.medagentx.fusion.labels import training_value_from_row

    merged = label_df.merge(ensemble_df, on=["study_key", "dicom_path"], how="inner", suffixes=("_label", "_ens"))

    y = {label: [] for label in DISEASE_LABELS}
    d = {label: [] for label in DISEASE_LABELS}
    f = {label: [] for label in DISEASE_LABELS}
    e = {label: [] for label in DISEASE_LABELS}
    mask = {label: [] for label in DISEASE_LABELS}

    for _, row in merged.iterrows():
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            value = training_value_from_row(row, label, label_mode)
            if value is None:
                mask[label].append(0.0)
                y[label].append(0.0)
            else:
                mask[label].append(1.0)
                y[label].append(float(value))

            d[label].append(_safe_prob(row.get(f"densenet_prob_{slug}")))
            f[label].append(_safe_prob(row.get(f"fusion_prob_{slug}")))
            e[label].append(_safe_prob(row.get(f"ensemble_prob_{slug}")))

    arrays = {
        "y": {label: np.asarray(y[label], dtype=np.float32) for label in DISEASE_LABELS},
        "densenet": {label: np.asarray(d[label], dtype=np.float32) for label in DISEASE_LABELS},
        "fusion": {label: np.asarray(f[label], dtype=np.float32) for label in DISEASE_LABELS},
        "ensemble": {label: np.asarray(e[label], dtype=np.float32) for label in DISEASE_LABELS},
        "mask": {label: np.asarray(mask[label], dtype=np.float32) for label in DISEASE_LABELS},
    }
    return arrays, merged


def fit_ensemble_calibrator_from_tables(
    label_df: pd.DataFrame,
    ensemble_df: pd.DataFrame,
    label_mode: str = "judge",
) -> PerLabelEnsembleCalibrator:
    arrays, _ = build_calibration_arrays(label_df, ensemble_df, label_mode=label_mode)
    calibrator = PerLabelEnsembleCalibrator()
    for label in DISEASE_LABELS:
        calibrator.fit(
            label=label,
            y_true=arrays["y"][label],
            densenet_prob=arrays["densenet"][label],
            fusion_prob=arrays["fusion"][label],
            ensemble_prob=arrays["ensemble"][label],
            mask=arrays["mask"][label],
        )
    return calibrator


def _safe_prob(value) -> float:
    if value is None or value == "":
        return 0.0
    try:
        out = float(value)
    except (TypeError, ValueError):
        return 0.0
    if np.isnan(out):
        return 0.0
    return out
