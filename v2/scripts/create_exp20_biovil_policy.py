"""Create and verify the frozen policy for the Exp20 BioViL baseline.

The command validates the BioViL checkpoints, source revision, and CheXpert
cohort hashes before creating any output. It refuses to overwrite an existing
experiment directory. No model is loaded and no inference is performed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUTPUT_DIR = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp20_biovil_native_zero_shot_comparison"
)
DEFAULT_CHECKPOINT_DIR = (
    PROJECT_ROOT
    / "external"
    / "biovil"
    / "checkpoints"
    / "BiomedVLP-CXR-BERT-specialized-v1.1"
)
DEFAULT_HIML_ROOT = PROJECT_ROOT / "external" / "biovil" / "hi-ml"
DEFAULT_VALIDATION_MANIFEST = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_manifest.csv"
)
DEFAULT_VALIDATION_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp16_chexpert_competition_val_thresholds"
    / "competition_val_ground_truth.csv"
)
DEFAULT_TEST_MANIFEST = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_view_manifest.csv"
)
DEFAULT_TEST_GROUND_TRUTH = (
    PROJECT_ROOT
    / "v2"
    / "experiments"
    / "exp14_chexpert_competition_auroc"
    / "competition_ground_truth.csv"
)

POLICY_VERSION = "biovil_native_positive_negative_margin_exp20_v1"
EXPECTED_HIML_REVISION = "b67c1d27c6b17d8e8ff01f8c507f3cabdb307388"
EXPECTED_HASHES = {
    "image_checkpoint": (
        "118c4bb1c16d4e69b7c9b7f2ff5b2c0"
        "a79242059acf20bd2ed3068045b8f6b98"
    ),
    "text_checkpoint": (
        "a41d2f4b33e5bdbacabecb8d34c44201"
        "63e2165b9fdc6915014e8263a0d0782b"
    ),
    "validation_manifest": (
        "684f12cc181a6fb987436e0ef01ccc7d"
        "dfd8b86f60669c78e564ff39ebb306be"
    ),
    "validation_ground_truth": (
        "1caf1a4639711f32a1566ab514aed4d7"
        "9f45f6f3477152c19811370586453026"
    ),
    "test_manifest": (
        "fe4084cbb7acb349ffe9aa45f5e56074"
        "0562f76ce6496c3436918fee6444f6aa"
    ),
    "test_ground_truth": (
        "9bab723d2051e2c35b3869e8d659c71"
        "c9c3da78ea21814d3a337120e4150f489"
    ),
}

PROMPTS = {
    "Atelectasis": {
        "positive": "Findings suggesting atelectasis",
        "negative": "No evidence of atelectasis",
    },
    "Cardiomegaly": {
        "positive": "Findings suggesting cardiomegaly",
        "negative": "No evidence of cardiomegaly",
    },
    "Consolidation": {
        "positive": "Findings suggesting consolidation",
        "negative": "No evidence of consolidation",
    },
    "Edema": {
        "positive": "Findings suggesting pulmonary edema",
        "negative": "No evidence of pulmonary edema",
    },
    "Pleural Effusion": {
        "positive": "Findings suggesting pleural effusion",
        "negative": "No evidence of pleural effusion",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate inputs and create the frozen Exp20 BioViL native "
            "zero-shot policy. Existing output is never overwritten."
        )
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--checkpoint-dir", type=Path, default=DEFAULT_CHECKPOINT_DIR
    )
    parser.add_argument("--hi-ml-root", type=Path, default=DEFAULT_HIML_ROOT)
    parser.add_argument(
        "--validation-manifest",
        type=Path,
        default=DEFAULT_VALIDATION_MANIFEST,
    )
    parser.add_argument(
        "--validation-ground-truth",
        type=Path,
        default=DEFAULT_VALIDATION_GROUND_TRUTH,
    )
    parser.add_argument(
        "--test-manifest", type=Path, default=DEFAULT_TEST_MANIFEST
    )
    parser.add_argument(
        "--test-ground-truth", type=Path, default=DEFAULT_TEST_GROUND_TRUTH
    )
    parser.add_argument(
        "--verify-existing",
        action="store_true",
        help="Verify an existing policy and checksum instead of creating it.",
    )
    return parser


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(8 * 1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def resolve_file(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def resolve_directory(path: Path, description: str) -> Path:
    resolved = path.expanduser().resolve()
    if not resolved.is_dir():
        raise FileNotFoundError(f"Missing {description}: {resolved}")
    return resolved


def relative_to_project(path: Path) -> str:
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def verify_hash(path: Path, expected: str, description: str) -> str:
    observed = sha256(path)
    print(description)
    print(f"  File:     {relative_to_project(path)}")
    print(f"  Observed: {observed}")
    print(f"  Expected: {expected}")
    print(f"  Matches:  {observed == expected}")
    if observed != expected:
        raise RuntimeError(
            f"{description} SHA-256 mismatch: expected {expected}, "
            f"observed {observed}"
        )
    return observed


def git_output(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def build_policy(
    *,
    checkpoint_dir: Path,
    hi_ml_root: Path,
    validation_manifest: Path,
    validation_ground_truth: Path,
    test_manifest: Path,
    test_ground_truth: Path,
) -> dict[str, Any]:
    image_checkpoint = resolve_file(
        checkpoint_dir / "biovil_image_resnet50_proj_size_128.pt",
        "BioViL image checkpoint",
    )
    text_checkpoint = resolve_file(
        checkpoint_dir / "pytorch_model.bin", "CXR-BERT checkpoint"
    )
    validation_manifest = resolve_file(
        validation_manifest, "validation manifest"
    )
    validation_ground_truth = resolve_file(
        validation_ground_truth, "validation ground truth"
    )
    test_manifest = resolve_file(test_manifest, "test manifest")
    test_ground_truth = resolve_file(test_ground_truth, "test ground truth")
    hi_ml_root = resolve_directory(hi_ml_root, "Microsoft HI-ML repository")

    print("=== VERIFYING FROZEN INPUTS ===")
    observed_hashes = {
        "image_checkpoint": verify_hash(
            image_checkpoint,
            EXPECTED_HASHES["image_checkpoint"],
            "BioViL image checkpoint",
        ),
        "text_checkpoint": verify_hash(
            text_checkpoint,
            EXPECTED_HASHES["text_checkpoint"],
            "CXR-BERT checkpoint",
        ),
        "validation_manifest": verify_hash(
            validation_manifest,
            EXPECTED_HASHES["validation_manifest"],
            "Validation manifest",
        ),
        "validation_ground_truth": verify_hash(
            validation_ground_truth,
            EXPECTED_HASHES["validation_ground_truth"],
            "Validation ground truth",
        ),
        "test_manifest": verify_hash(
            test_manifest,
            EXPECTED_HASHES["test_manifest"],
            "Test manifest",
        ),
        "test_ground_truth": verify_hash(
            test_ground_truth,
            EXPECTED_HASHES["test_ground_truth"],
            "Test ground truth",
        ),
    }

    revision = git_output(hi_ml_root, "rev-parse", "HEAD")
    status = git_output(hi_ml_root, "status", "--short")
    print("Microsoft HI-ML revision:", revision)
    print("Microsoft HI-ML working tree clean:", not bool(status))
    if revision != EXPECTED_HIML_REVISION:
        raise RuntimeError(
            "Unexpected Microsoft HI-ML revision: "
            f"expected {EXPECTED_HIML_REVISION}, observed {revision}"
        )
    if status:
        raise RuntimeError(
            "Microsoft HI-ML repository has uncommitted changes:\n" + status
        )

    input_paths = {
        "image_checkpoint": relative_to_project(image_checkpoint),
        "text_checkpoint": relative_to_project(text_checkpoint),
        "validation_manifest": relative_to_project(validation_manifest),
        "validation_ground_truth": relative_to_project(
            validation_ground_truth
        ),
        "test_manifest": relative_to_project(test_manifest),
        "test_ground_truth": relative_to_project(test_ground_truth),
    }
    frozen_inputs = {
        key: {"path": input_paths[key], "sha256": observed_hashes[key]}
        for key in input_paths
    }

    return {
        "policy_version": POLICY_VERSION,
        "experiment": {
            "experiment_id": "exp20",
            "name": "biovil_native_zero_shot_comparison",
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "analysis_status": "post_hoc_literature_aligned_baseline",
            "test_results_from_prior_non_native_protocol_seen": True,
            "training_or_finetuning": False,
        },
        "model": {
            "name": "BioViL",
            "image_encoder": "BioViL ResNet-50",
            "text_encoder": "BiomedVLP-CXR-BERT-specialized-v1.1",
            "embedding_dimension": 128,
            "hi_ml_source_revision": revision,
            "weights_frozen": True,
        },
        "labels": list(PROMPTS),
        "prompts": PROMPTS,
        "inference": {
            "image_preprocessing": {
                "implementation": "official BioViL/HI-ML preprocessing",
                "input_channels": 3,
                "final_height": 480,
                "final_width": 480,
            },
            "embedding_normalization": "L2",
            "similarity": "cosine_similarity",
            "positive_similarity": (
                "cosine(image_embedding, positive_text_embedding)"
            ),
            "negative_similarity": (
                "cosine(image_embedding, negative_text_embedding)"
            ),
            "image_raw_score": (
                "positive_similarity - negative_similarity"
            ),
            "softmax_probability_used": False,
            "eligible_views": "frontal_only",
            "study_aggregation": (
                "arithmetic mean of image_raw_score across frontal views"
            ),
            "threshold_images_before_aggregation": False,
        },
        "validation_policy": {
            "selection_split": "competition_validation",
            "expected_studies": 200,
            "expected_frontal_images": 202,
            "normalization": "per-label validation-only z-score",
            "standard_deviation": "population_ddof_0",
            "threshold_selection": (
                "maximum F1 subject to specificity >= 0.60"
            ),
            "minimum_specificity": 0.60,
            "tie_breaker": ["maximum_precision", "higher_threshold"],
        },
        "test_policy": {
            "evaluation_split": "competition_test",
            "expected_studies": 500,
            "expected_frontal_images": 518,
            "normalization_source": "frozen_validation_statistics",
            "threshold_source": "frozen_validation_thresholds",
            "test_time_tuning_allowed": False,
        },
        "metric_policy": {
            "per_label": [
                "auroc",
                "average_precision",
                "precision",
                "recall",
                "f1",
                "specificity",
                "accuracy",
            ],
            "summary": [
                "macro_auroc",
                "macro_average_precision",
                "macro_precision",
                "macro_recall",
                "macro_f1",
                "micro_precision",
                "micro_recall",
                "micro_f1",
            ],
            "unit_of_evaluation": "study",
        },
        "frozen_inputs": frozen_inputs,
    }


def write_policy(output_dir: Path, policy: dict[str, Any]) -> None:
    output_dir = output_dir.expanduser().resolve()
    if output_dir.exists():
        raise FileExistsError(
            f"Refusing to overwrite existing directory: {output_dir}"
        )

    output_dir.mkdir(parents=True, exist_ok=False)
    policy_path = output_dir / "prompt_policy.json"
    checksum_path = output_dir / "prompt_policy.sha256"
    policy_path.write_text(
        json.dumps(policy, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    policy_hash = sha256(policy_path)
    checksum_path.write_text(
        f"{policy_hash}  prompt_policy.json\n", encoding="utf-8"
    )

    print("\n=== EXP20 POLICY CREATED ===")
    print("Directory:", output_dir)
    print("Policy:", policy_path)
    print("Policy SHA-256:", policy_hash)
    print("Checksum file:", checksum_path)
    print("\n=== FROZEN PROMPTS ===")
    for label, prompts in policy["prompts"].items():
        print(label)
        print("  Positive:", prompts["positive"])
        print("  Negative:", prompts["negative"])
    print("\nImage score: positive cosine - negative cosine")
    print("Study aggregation: mean of frontal-image raw scores")
    print("Normalization: validation-only population z-score")
    print("Threshold: maximum F1 with specificity >= 0.60")
    print("Tie-breaker: maximum precision, then higher threshold")
    print("\nSTEP 2 CREATION SUCCEEDED")


def verify_existing_policy(output_dir: Path) -> None:
    output_dir = resolve_directory(output_dir, "Exp20 output directory")
    policy_path = resolve_file(
        output_dir / "prompt_policy.json", "Exp20 prompt policy"
    )
    checksum_path = resolve_file(
        output_dir / "prompt_policy.sha256", "Exp20 checksum file"
    )
    fields = checksum_path.read_text(encoding="utf-8").strip().split()
    if len(fields) != 2 or fields[1] != "prompt_policy.json":
        raise RuntimeError(f"Malformed checksum file: {checksum_path}")
    expected = fields[0]
    observed = sha256(policy_path)
    policy = json.loads(policy_path.read_text(encoding="utf-8"))
    print("Policy:", policy_path)
    print("Observed SHA-256:", observed)
    print("Expected SHA-256:", expected)
    print("Matches:", observed == expected)
    print("Policy version:", policy.get("policy_version"))
    if observed != expected:
        raise RuntimeError("Exp20 prompt-policy checksum mismatch")
    if policy.get("policy_version") != POLICY_VERSION:
        raise RuntimeError(
            f"Unexpected policy version: {policy.get('policy_version')!r}"
        )
    print("STEP 2 VERIFICATION SUCCEEDED")


def main() -> None:
    args = build_parser().parse_args()
    if args.verify_existing:
        verify_existing_policy(args.output_dir)
        return

    checkpoint_dir = resolve_directory(
        args.checkpoint_dir, "BioViL checkpoint directory"
    )
    policy = build_policy(
        checkpoint_dir=checkpoint_dir,
        hi_ml_root=args.hi_ml_root,
        validation_manifest=args.validation_manifest,
        validation_ground_truth=args.validation_ground_truth,
        test_manifest=args.test_manifest,
        test_ground_truth=args.test_ground_truth,
    )
    write_policy(args.output_dir, policy)


if __name__ == "__main__":
    main()
