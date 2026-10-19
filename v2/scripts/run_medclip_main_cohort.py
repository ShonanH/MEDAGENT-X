"""Run a frozen zero-shot MedCLIP baseline on the 12-label main cohort.

This is deliberately separate from the five-condition CheXpert competition
runner.  It scores quality-passed DICOM views from the balanced cohort,
averages logits per study, converts the mean logits with a sigmoid, and emits
the same wide vision-prediction contract used by the main MEDAGENT-X Judge.

Run this once for ``--split val`` with the initial 0.5 thresholds, tune those
scores with ``medagentx.cli.tune_vision_thresholds``, then run it for
``--split test`` with the frozen policy.  The test branch writes and hashes
the predictions before it opens the study-label table for Judge evaluation.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import random
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import torch

PROJECT_ROOT = Path(__file__).resolve().parents[2]
V2_SRC = PROJECT_ROOT / "v2" / "src"
if str(V2_SRC) not in sys.path:
    sys.path.insert(0, str(V2_SRC))

import run_medclip_validation_inference as base
from medagentx.data.dicoms import local_dicom_path
from medagentx.evaluation.fusion_eval import (
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    study_labels_to_ground_truth,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label


DEFAULT_COHORT_ROOT = PROJECT_ROOT / "v2" / "artifacts" / "cohort_balanced_v1"
DEFAULT_OUTPUT_ROOT = PROJECT_ROOT / "v2" / "experiments" / "medclip_main_cohort"
MODEL_NAME = "medclip_vit_zero_shot_main_cohort"

# MedCLIP supplies official report-derived prompt sets for only the five
# competition labels.  These fixed positive finding prompts extend the
# zero-shot baseline to the remaining labels in the main cohort.  They are
# intentionally declared in source and recorded in run_config.json before
# test inference, rather than constructed from any validation/test labels.
PROMPTS: dict[str, tuple[str, ...]] = {
    "Atelectasis": (
        "subsegmental atelectasis",
        "linear atelectasis at the lung bases",
        "bibasilar atelectasis",
    ),
    "Cardiomegaly": (
        "cardiomegaly",
        "mildly enlarged cardiac silhouette",
        "enlarged heart size",
    ),
    "Consolidation": (
        "airspace consolidation",
        "patchy pulmonary consolidation",
        "bilateral consolidation",
    ),
    "Edema": (
        "pulmonary edema",
        "interstitial pulmonary edema",
        "vascular congestion and edema",
    ),
    "Pleural Effusion": (
        "pleural effusion",
        "small bilateral pleural effusions",
        "right pleural effusion",
    ),
    "Pneumonia": (
        "pneumonia",
        "focal airspace pneumonia",
        "multifocal pneumonia",
    ),
    "Pneumothorax": (
        "pneumothorax",
        "small apical pneumothorax",
        "right-sided pneumothorax",
    ),
    "Fracture": (
        "acute rib fracture",
        "fracture of the clavicle",
        "osseous fracture in the chest",
    ),
    "Lung Lesion": (
        "pulmonary nodule",
        "lung mass",
        "focal lung lesion",
    ),
    "Lung Opacity": (
        "pulmonary opacity",
        "bilateral lung opacities",
        "focal airspace opacity",
    ),
    "Enlarged Cardiomediastinum": (
        "enlarged cardiomediastinal silhouette",
        "widened mediastinum",
        "cardiomediastinal enlargement",
    ),
    "Pleural Other": (
        "pleural thickening",
        "pleural plaque",
        "pleural abnormality",
    ),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score the 12-label MEDAGENT-X cohort with zero-shot MedCLIP."
    )
    parser.add_argument("--cohort-root", type=Path, default=DEFAULT_COHORT_ROOT)
    parser.add_argument("--views-csv", type=Path, default=None)
    parser.add_argument("--dicom-root", type=Path, default=None)
    parser.add_argument("--study-labels-csv", type=Path, default=None)
    parser.add_argument("--split", choices=("val", "test"), required=True)
    parser.add_argument("--output-dir", type=Path, default=None)
    parser.add_argument(
        "--threshold-policy",
        type=Path,
        default=None,
        help="Required for test; a policy created only from the MedCLIP val run.",
    )
    parser.add_argument("--expected-studies", type=int, required=True)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--seed", type=int, default=20261019)
    parser.add_argument("--device", default="cuda:0")
    return parser


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _load_thresholds(path: Path) -> dict[str, float]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    thresholds = payload.get("selected_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("Threshold policy lacks selected_thresholds")
    missing = sorted(set(DISEASE_LABELS) - set(thresholds))
    if missing:
        raise ValueError(f"Threshold policy is missing labels: {missing}")
    return {label: float(thresholds[label]) for label in DISEASE_LABELS}


def _prepare_views(path: Path, split: str, dicom_root: Path) -> pd.DataFrame:
    views = pd.read_csv(path, dtype=str)
    required = {"study_key", "deid_patient_id", "dicom_path", "split"}
    missing = sorted(required - set(views.columns))
    if missing:
        raise ValueError(f"views CSV is missing columns: {missing}")
    views = views.loc[views["split"].eq(split)].copy()
    if views.empty:
        raise ValueError(f"No views found for split={split!r}")
    views["study_key"] = views["study_key"].str.strip()
    views["deid_patient_id"] = views["deid_patient_id"].str.strip()
    views["dicom_path"] = views["dicom_path"].str.strip()
    if (views["study_key"] == "").any() or (views["dicom_path"] == "").any():
        raise ValueError("views CSV contains empty study_key or dicom_path")
    if views.duplicated(["study_key", "dicom_path"]).any():
        raise ValueError("views CSV contains duplicate study_key/dicom_path pairs")
    views["local_path"] = views["dicom_path"].map(
        lambda item: str(local_dicom_path(dicom_root, item))
    )
    missing_paths = [item for item in views["local_path"] if not Path(item).is_file()]
    if missing_paths:
        raise FileNotFoundError(
            f"Missing {len(missing_paths)} DICOM files; first: {missing_paths[0]}"
        )
    return views.sort_values(["study_key", "dicom_path"], kind="stable").reset_index(drop=True)


def _score_views(
    *,
    views: pd.DataFrame,
    classifier: Any,
    preprocessing: dict[str, float],
    prompt_inputs: Any,
    device: torch.device,
    batch_size: int,
) -> pd.DataFrame:
    from medagentx.vision.data import dicom_to_pil_rgb

    batches: list[pd.DataFrame] = []
    for start in range(0, len(views), batch_size):
        batch = views.iloc[start : start + batch_size].reset_index(drop=True)
        images: list[Any] = []
        try:
            for local_path in batch["local_path"]:
                images.append(dicom_to_pil_rgb(local_path))
            inputs = {
                "pixel_values": base.prepare_medclip_pixels(images, preprocessing).to(device),
                "prompt_inputs": base._move_to_device(prompt_inputs, device),
            }
            with torch.inference_mode():
                output = classifier(**inputs)
        finally:
            for image in images:
                image.close()

        class_names = list(output.get("class_names", [])) if isinstance(output, dict) else []
        if class_names != list(DISEASE_LABELS):
            raise RuntimeError(
                f"Unexpected MedCLIP prompt class order: {class_names}"
            )
        logits = output.get("logits") if isinstance(output, dict) else None
        if not isinstance(logits, torch.Tensor) or tuple(logits.shape) != (
            len(batch), len(DISEASE_LABELS)
        ):
            raise RuntimeError(f"Unexpected MedCLIP logits shape: {getattr(logits, 'shape', None)}")
        values = logits.detach().float().cpu().numpy()
        if not np.isfinite(values).all():
            raise RuntimeError("MedCLIP produced non-finite logits")
        frame = batch[["study_key", "deid_patient_id", "split", "dicom_path"]].copy()
        frame.insert(0, "model_name", MODEL_NAME)
        for index, label in enumerate(DISEASE_LABELS):
            frame[f"raw_{snake_label(label)}"] = values[:, index]
        batches.append(frame)
        print(f"Processed {min(start + batch_size, len(views))}/{len(views)} DICOM views", flush=True)
        del inputs, output
        gc.collect()
        torch.cuda.empty_cache()
    return pd.concat(batches, ignore_index=True)


def _study_predictions(
    image_scores: pd.DataFrame, thresholds: dict[str, float]
) -> pd.DataFrame:
    raw_columns = [f"raw_{snake_label(label)}" for label in DISEASE_LABELS]
    grouped = image_scores.groupby("study_key", sort=True, as_index=False)
    scores = grouped[raw_columns].mean()
    metadata = grouped.agg(
        deid_patient_id=("deid_patient_id", "first"),
        split=("split", "first"),
        view_count=("dicom_path", "size"),
        dicom_paths=("dicom_path", lambda values: json.dumps(list(values))),
    ).reset_index()
    predictions = metadata.merge(scores, on="study_key", validate="one_to_one")
    predictions.insert(0, "model_name", MODEL_NAME)
    for label in DISEASE_LABELS:
        slug = snake_label(label)
        # A monotonic transformation of the ensembled logits lets the existing
        # validation-only threshold tuner operate on its documented [0, 1] grid.
        predictions[f"probability_{slug}"] = 1.0 / (1.0 + np.exp(-predictions[f"raw_{slug}"]))
        predictions[f"threshold_{slug}"] = float(thresholds[label])
        predictions[f"status_{slug}"] = np.where(
            predictions[f"probability_{slug}"] >= float(thresholds[label]),
            "present",
            "absent",
        )
    return predictions


def _evaluate_test(predictions: pd.DataFrame, study_labels_path: Path, output_dir: Path) -> None:
    study_labels = pd.read_csv(study_labels_path, dtype=str)
    study_keys = predictions["study_key"].astype(str).tolist()
    ground_truth = study_labels_to_ground_truth(study_labels, study_keys=study_keys)
    statuses = {
        (str(row.study_key), label): getattr(row, f"status_{snake_label(label)}")
        for row in predictions.itertuples(index=False)
        for label in DISEASE_LABELS
    }
    from medagentx.labels.statuses import LabelStatus

    status_map = {(key, label): LabelStatus(value) for (key, label), value in statuses.items()}
    judge_run = run_named_judge_result(
        name="medclip_zero_shot_full", eval_scope="full", ground_truth_records=ground_truth,
        predicted_statuses=status_map,
    )
    summary = {
        "model_name": MODEL_NAME,
        "evaluation_split": "test",
        "study_count": int(predictions["study_key"].nunique()),
        "runs": [named_judge_summary_payload(judge_run)],
    }
    evaluation_dir = output_dir / "judge_evaluation"
    evaluation_dir.mkdir(parents=True, exist_ok=False)
    _write_json(evaluation_dir / "judge_summary.json", summary)
    per_label_metrics_frame([judge_run]).to_csv(
        evaluation_dir / "per_label_metrics.csv", index=False
    )


def main() -> None:
    args = build_parser().parse_args()
    if args.batch_size <= 0 or args.expected_studies <= 0:
        raise ValueError("--batch-size and --expected-studies must be positive")
    if args.device != "cuda:0" and not str(args.device).startswith("cuda:"):
        raise ValueError("MedCLIP's official PromptClassifier requires a CUDA device")
    if not torch.cuda.is_available():
        raise RuntimeError("CUDA is required by MedCLIP's official PromptClassifier")
    if args.split == "test" and args.threshold_policy is None:
        raise ValueError("--threshold-policy is required for test inference")
    if args.split == "val" and args.threshold_policy is not None:
        raise ValueError("Validation must use the fixed initial 0.5 thresholds, not a policy")

    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.cuda.manual_seed_all(args.seed)
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True

    cohort_root = args.cohort_root.expanduser().resolve()
    views_path = (args.views_csv or cohort_root / "splits" / "view_splits.csv").expanduser().resolve()
    dicom_root = (args.dicom_root or cohort_root / "dicom_train").expanduser().resolve()
    labels_path = (args.study_labels_csv or cohort_root / "study_label_table.csv").expanduser().resolve()
    output_dir = (args.output_dir or DEFAULT_OUTPUT_ROOT / args.split).expanduser().resolve()
    for path, description in ((views_path, "views CSV"), (dicom_root, "DICOM root")):
        if not path.exists():
            raise FileNotFoundError(f"Missing {description}: {path}")
    if output_dir.exists():
        raise FileExistsError(f"Refusing to overwrite existing output directory: {output_dir}")

    thresholds = {label: 0.5 for label in DISEASE_LABELS}
    policy_path: Path | None = None
    if args.threshold_policy is not None:
        policy_path = args.threshold_policy.expanduser().resolve()
        if not policy_path.is_file():
            raise FileNotFoundError(f"Missing threshold policy: {policy_path}")
        thresholds = _load_thresholds(policy_path)

    views = _prepare_views(views_path, args.split, dicom_root)
    if views["study_key"].nunique() != args.expected_studies:
        raise RuntimeError(
            f"Expected {args.expected_studies} studies, found {views['study_key'].nunique()}"
        )
    output_dir.mkdir(parents=True)
    device = torch.device(args.device)
    classifier, preprocessing, _unused_inputs, _unused_prompts = base.load_medclip(device, 1)
    from medclip.prompts import process_class_prompts

    prompt_inputs = process_class_prompts(PROMPTS)
    image_scores = _score_views(
        views=views, classifier=classifier, preprocessing=preprocessing,
        prompt_inputs=prompt_inputs, device=device, batch_size=args.batch_size,
    )
    predictions = _study_predictions(image_scores, thresholds)
    if len(predictions) != args.expected_studies:
        raise RuntimeError("Unexpected number of study-level predictions")
    image_scores_path = output_dir / "image_scores.csv"
    predictions_path = output_dir / "vision_study_predictions.csv"
    image_scores.to_csv(image_scores_path, index=False)
    predictions.to_csv(predictions_path, index=False)

    config: dict[str, Any] = {
        "model_name": MODEL_NAME,
        "model_variant": "MedCLIP ViT official pretrained checkpoint",
        "split": args.split,
        "cohort_root": str(cohort_root),
        "views_csv": str(views_path),
        "dicom_root": str(dicom_root),
        "labels": list(DISEASE_LABELS),
        "prompts": {label: list(PROMPTS[label]) for label in DISEASE_LABELS},
        "score_definition": "mean_view_logit_then_sigmoid",
        "threshold_source": "fixed_0.5" if policy_path is None else str(policy_path),
        "study_count": len(predictions),
        "view_count": len(image_scores),
        "execution": {"device": str(device), "batch_size": args.batch_size, "seed": args.seed},
    }
    if args.split == "test":
        lock = {
            "model_name": MODEL_NAME,
            "test_ground_truth_opened_before_prediction_lock": False,
            "views_csv_sha256": _sha256(views_path),
            "threshold_policy_sha256": _sha256(policy_path),
            "artifact_sha256": {
                image_scores_path.name: _sha256(image_scores_path),
                predictions_path.name: _sha256(predictions_path),
            },
        }
        _write_json(output_dir / "test_prediction_lock.json", lock)
        config["predictions_locked_before_ground_truth"] = True
        if not labels_path.is_file():
            raise FileNotFoundError(f"Missing study label table: {labels_path}")
        _evaluate_test(predictions, labels_path, output_dir)
    _write_json(output_dir / "run_config.json", config)
    print(f"Saved image scores: {image_scores_path}")
    print(f"Saved study predictions: {predictions_path}")
    print(f"Saved run config: {output_dir / 'run_config.json'}")
    if args.split == "test":
        print(f"Saved Judge metrics: {output_dir / 'judge_evaluation' / 'judge_summary.json'}")


if __name__ == "__main__":
    main()
