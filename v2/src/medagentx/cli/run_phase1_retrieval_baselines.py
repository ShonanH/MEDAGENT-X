"""Run controlled non-LLM retrieval baselines on frozen vision outputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import time
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from medagentx.cli.evaluate_matched_positive_threshold import (
    build_matched_positive_predictions,
)
from medagentx.evaluation.fusion_eval import (
    filter_gray_zone_ground_truth,
    named_judge_summary_payload,
    per_label_metrics_frame,
    run_named_judge_result,
    status_confusion_by_label_frame,
    study_labels_to_ground_truth_strata,
    study_outputs_by_key,
    uncertain_status_metrics_frame,
    vision_status_map,
)
from medagentx.labels.constants import DISEASE_LABELS
from medagentx.labels.schema import snake_label
from medagentx.labels.statuses import LabelStatus
from medagentx.reasoning.baselines import (
    StructuredVoteStudyResult,
    structured_vote_status_map,
    structured_vote_study,
)
from medagentx.reasoning.constants import (
    FUSION_RETRIEVAL_TOP_K,
    GRAY_ZONE_MARGIN,
)
from medagentx.reasoning.fuse import (
    FusionStudyResult,
    fuse_study_labels,
)
from medagentx.reasoning.retrieve import (
    open_retrieval_collection,
    retrieve_similar_reports,
)
from medagentx.reasoning.vision_adapter import fusion_vision_inputs
from medagentx.retrieval.constants import DEFAULT_COLLECTION_NAME
from medagentx.retrieval.index import RetrievedStudy
from medagentx.vision.inference_output import (
    VisionStudyOutput,
    load_vision_study_outputs,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compare frozen vision, matched thresholds, deterministic keyword "
            "fusion, structured kNN voting, and random retrieval controls."
        )
    )
    parser.add_argument("--vision-outputs-cache", type=Path, required=True)
    parser.add_argument("--reference-fusion-csv", type=Path, required=True)
    parser.add_argument("--study-labels-csv", type=Path, required=True)
    parser.add_argument("--vector-db-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--collection-name", default=DEFAULT_COLLECTION_NAME)
    parser.add_argument(
        "--retrieval-top-k",
        type=int,
        default=FUSION_RETRIEVAL_TOP_K,
    )
    parser.add_argument(
        "--gray-zone-margin",
        type=float,
        default=GRAY_ZONE_MARGIN,
    )
    parser.add_argument(
        "--random-seeds",
        default="42,123,456",
        help="Comma-separated deterministic random-retrieval seeds.",
    )
    parser.add_argument("--progress-every", type=int, default=100)
    parser.add_argument(
        "--max-studies",
        type=int,
        default=None,
        help="Optional development-only smoke-test limit.",
    )
    return parser


def _parse_seeds(value: str) -> tuple[int, ...]:
    seeds = tuple(int(item.strip()) for item in value.split(",") if item.strip())
    if not seeds or len(set(seeds)) != len(seeds):
        raise ValueError("random-seeds must contain unique integer seeds")
    return seeds


def _parse_fusion_predictions(
    frame: pd.DataFrame,
) -> dict[tuple[str, str], LabelStatus]:
    required = {"study_key", "label", "fused_status"}
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Reference fusion CSV is missing columns: {missing}")
    if frame.duplicated(["study_key", "label"]).any():
        raise ValueError("Reference fusion CSV contains duplicate cells")
    return {
        (str(row.study_key), str(row.label)): LabelStatus(
            str(row.fused_status).strip().lower()
        )
        for row in frame.itertuples(index=False)
    }


def _structured_label_lookups(
    frame: pd.DataFrame,
) -> dict[str, dict[str, dict[str, LabelStatus]]]:
    required = {"study_key"} | {
        f"status_{snake_label(label)}" for label in DISEASE_LABELS
    } | {
        f"training_mask_{snake_label(label)}" for label in DISEASE_LABELS
    } | {
        f"training_target_{snake_label(label)}" for label in DISEASE_LABELS
    }
    missing = sorted(required - set(frame.columns))
    if missing:
        raise ValueError(f"Study labels are missing columns: {missing}")
    if frame["study_key"].astype(str).duplicated().any():
        raise ValueError("Study labels contain duplicate study keys")
    explicit_lookup: dict[str, dict[str, LabelStatus]] = {}
    training_lookup: dict[str, dict[str, LabelStatus]] = {}
    for _, row in frame.iterrows():
        key = str(row["study_key"]).strip()
        explicit_statuses: dict[str, LabelStatus] = {}
        training_statuses: dict[str, LabelStatus] = {}
        for label in DISEASE_LABELS:
            slug = snake_label(label)
            explicit = LabelStatus(str(row[f"status_{slug}"]).strip().lower())
            mask = pd.to_numeric(
                pd.Series([row[f"training_mask_{slug}"]]), errors="coerce"
            ).iloc[0]
            target = pd.to_numeric(
                pd.Series([row[f"training_target_{slug}"]]), errors="coerce"
            ).iloc[0]
            is_derived_negative = (
                explicit is LabelStatus.UNMENTIONED
                and not pd.isna(mask)
                and int(mask) == 1
                and not pd.isna(target)
                and float(target) == 0.0
            )
            explicit_statuses[label] = explicit
            training_statuses[label] = (
                LabelStatus.ABSENT if is_derived_negative else explicit
            )
        explicit_lookup[key] = explicit_statuses
        training_lookup[key] = training_statuses
    return {
        "explicit_votes": explicit_lookup,
        "training_policy_votes": training_lookup,
    }


def _collection_pool(collection: Any) -> list[RetrievedStudy]:
    payload = collection.get(include=["documents", "metadatas"])
    documents = payload.get("documents") or []
    metadatas = payload.get("metadatas") or []
    if len(documents) != len(metadatas):
        raise ValueError("Chroma random pool documents/metadata length mismatch")
    pool = []
    for document, metadata in zip(documents, metadatas):
        metadata = metadata or {}
        pool.append(
            RetrievedStudy(
                study_key=str(metadata.get("study_key", "")).strip(),
                deid_patient_id=str(
                    metadata.get("deid_patient_id", "")
                ).strip(),
                document=str(document or ""),
                distance=1.0,
                similarity=0.0,
            )
        )
    if not pool or any(not item.study_key or not item.document for item in pool):
        raise ValueError("Chroma random pool contains empty study keys or documents")
    return sorted(pool, key=lambda item: item.study_key)


def _random_neighbors(
    pool: Sequence[RetrievedStudy],
    output: VisionStudyOutput,
    *,
    top_k: int,
    seed: int,
) -> list[RetrievedStudy]:
    eligible = [
        item
        for item in pool
        if item.study_key != output.study_key
        and item.deid_patient_id != output.deid_patient_id
    ]
    if len(eligible) < top_k:
        raise ValueError("Random retrieval pool is smaller than top_k")
    digest = hashlib.sha256(
        f"phase1-random-v1:{seed}:{output.study_key}".encode("utf-8")
    ).digest()
    query_seed = int.from_bytes(digest[:8], "big", signed=False)
    rng = random.Random(query_seed)
    return rng.sample(eligible, top_k)


def _fusion_status_map(
    results: Sequence[FusionStudyResult],
) -> dict[tuple[str, str], LabelStatus]:
    return {
        (result.study_key, item.label): item.fused_status
        for result in results
        for item in result.labels
    }


def _vote_rows(
    method: str,
    results: Sequence[StructuredVoteStudyResult],
) -> list[dict[str, Any]]:
    return [
        {
            "method": method,
            "study_key": result.study_key,
            "label": item.label,
            "vision_status": item.vision_status.value,
            "final_status": item.final_status.value,
            "in_gray_zone": item.in_gray_zone,
            "positive_votes": item.positive_votes,
            "negative_votes": item.negative_votes,
            "uncertain_votes": item.uncertain_votes,
            "unmentioned_votes": item.unmentioned_votes,
            "positive_weight": item.positive_weight,
            "negative_weight": item.negative_weight,
            "changed": item.changed,
            "reason": item.reason,
        }
        for result in results
        for item in result.labels
    ]


def _prediction_rows(
    methods: Mapping[str, Mapping[tuple[str, str], LabelStatus]],
) -> list[dict[str, str]]:
    return [
        {
            "method": method,
            "study_key": study_key,
            "label": label,
            "status": status.value,
        }
        for method, predictions in methods.items()
        for (study_key, label), status in predictions.items()
    ]


def _trace_rows(
    *,
    query: VisionStudyOutput,
    neighbors: Sequence[RetrievedStudy],
    retrieval_method: str,
    neighbor_status_lookups: Mapping[
        str, Mapping[str, Mapping[str, LabelStatus]]
    ],
    seed: int | None,
) -> list[dict[str, Any]]:
    rows = []
    for rank, neighbor in enumerate(neighbors, start=1):
        row: dict[str, Any] = {
            "query_study_key": query.study_key,
            "query_patient_id": query.deid_patient_id,
            "retrieval_method": retrieval_method,
            "random_seed": seed,
            "rank": rank,
            "neighbor_study_key": neighbor.study_key,
            "neighbor_patient_id": neighbor.deid_patient_id,
            "distance": neighbor.distance,
            "similarity": neighbor.similarity,
        }
        for evidence_policy, lookup in neighbor_status_lookups.items():
            statuses = lookup[neighbor.study_key]
            for label in DISEASE_LABELS:
                row[
                    f"{evidence_policy}_{snake_label(label)}"
                ] = statuses[label].value
        rows.append(row)
    return rows


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    seeds = _parse_seeds(args.random_seeds)
    if args.retrieval_top_k <= 0:
        raise ValueError("retrieval-top-k must be > 0")
    if args.gray_zone_margin < 0:
        raise ValueError("gray-zone-margin must be >= 0")
    if args.progress_every <= 0:
        raise ValueError("progress-every must be > 0")
    if args.max_studies is not None and args.max_studies <= 0:
        raise ValueError("max-studies must be > 0")
    for path in (
        args.vision_outputs_cache,
        args.reference_fusion_csv,
        args.study_labels_csv,
        args.vector_db_dir,
    ):
        if not path.exists():
            raise FileNotFoundError(f"Required Phase 1 input is missing: {path}")

    outputs, vision_metadata = load_vision_study_outputs(
        args.vision_outputs_cache
    )
    if args.max_studies is not None:
        outputs = outputs[: args.max_studies]
    study_keys = [output.study_key for output in outputs]
    key_set = set(study_keys)

    labels_frame = pd.read_csv(args.study_labels_csv, dtype=str)
    label_lookups = _structured_label_lookups(labels_frame)
    reference_frame = pd.read_csv(args.reference_fusion_csv, dtype=str)
    reference_frame = reference_frame[
        reference_frame["study_key"].astype(str).isin(key_set)
    ].copy()
    reference_fusion = _parse_fusion_predictions(reference_frame)
    expected_cells = len(outputs) * len(DISEASE_LABELS)
    if len(reference_fusion) != expected_cells:
        raise ValueError(
            "Reference fusion cells do not match selected vision studies: "
            f"expected={expected_cells} actual={len(reference_fusion)}"
        )

    vision_predictions = vision_status_map(outputs)
    matched_predictions, matched_thresholds, _ = (
        build_matched_positive_predictions(
            outputs,
            reference_fusion,
            gray_zone_margin=args.gray_zone_margin,
        )
    )
    prediction_methods: dict[
        str, Mapping[tuple[str, str], LabelStatus]
    ] = {
        "vision": vision_predictions,
        "keyword_fusion_similar": reference_fusion,
        "matched_threshold": matched_predictions,
    }

    print(f"[Phase1] opening retrieval collection at {args.vector_db_dir}")
    collection = open_retrieval_collection(
        args.vector_db_dir,
        collection_name=args.collection_name,
    )
    random_pool = _collection_pool(collection)
    missing_pool_labels = [
        item.study_key
        for item in random_pool
        if any(
            item.study_key not in lookup for lookup in label_lookups.values()
        )
    ]
    if missing_pool_labels:
        raise ValueError(
            "Indexed studies are missing structured labels: "
            f"{missing_pool_labels[:10]}"
        )
    print(
        f"[Phase1] studies={len(outputs)} index_pool={len(random_pool)} "
        f"top_k={args.retrieval_top_k} seeds={seeds}"
    )

    similar_neighbors: dict[str, list[RetrievedStudy]] = {}
    random_neighbors: dict[tuple[int, str], list[RetrievedStudy]] = {}
    retrieval_trace_rows: list[dict[str, Any]] = []
    start = time.perf_counter()
    for index, output in enumerate(outputs, start=1):
        neighbors = retrieve_similar_reports(
            collection,
            output,
            top_k=args.retrieval_top_k,
        )
        if len(neighbors) != args.retrieval_top_k:
            raise ValueError(
                f"Similar retrieval returned {len(neighbors)} rows for "
                f"{output.study_key!r}"
            )
        similar_neighbors[output.study_key] = neighbors
        retrieval_trace_rows.extend(
            _trace_rows(
                query=output,
                neighbors=neighbors,
                retrieval_method="similar",
                neighbor_status_lookups=label_lookups,
                seed=None,
            )
        )
        for seed in seeds:
            selected = _random_neighbors(
                random_pool,
                output,
                top_k=args.retrieval_top_k,
                seed=seed,
            )
            random_neighbors[(seed, output.study_key)] = selected
            retrieval_trace_rows.extend(
                _trace_rows(
                    query=output,
                    neighbors=selected,
                    retrieval_method="random",
                    neighbor_status_lookups=label_lookups,
                    seed=seed,
                )
            )
        if index == 1 or index % args.progress_every == 0 or index == len(outputs):
            print(
                f"[Phase1] retrieved {index}/{len(outputs)} studies "
                f"elapsed={time.perf_counter() - start:.1f}s",
                flush=True,
            )

    keyword_similar_results = [
        fuse_study_labels(
            fusion_vision_inputs(output),
            similar_neighbors[output.study_key],
            study_key=output.study_key,
            margin=args.gray_zone_margin,
        )
        for output in outputs
    ]
    recomputed_keyword_fusion = _fusion_status_map(keyword_similar_results)
    mismatches = [
        key
        for key, status in reference_fusion.items()
        if recomputed_keyword_fusion.get(key) is not status
    ]
    if mismatches:
        raise ValueError(
            "Recomputed similar keyword fusion differs from frozen reference: "
            f"{mismatches[:10]}"
        )

    vote_evidence_rows: list[dict[str, Any]] = []
    for evidence_policy, label_lookup in label_lookups.items():
        for gray_only in (True, False):
            for weighted in (False, True):
                results = [
                    structured_vote_study(
                        output,
                        similar_neighbors[output.study_key],
                        label_lookup,
                        margin=args.gray_zone_margin,
                        gray_zone_only=gray_only,
                        similarity_weighted=weighted,
                    )
                    for output in outputs
                ]
                method = f"{results[0].method}_{evidence_policy}"
                prediction_methods[method] = structured_vote_status_map(results)
                vote_evidence_rows.extend(_vote_rows(method, results))

    for seed in seeds:
        for evidence_policy, label_lookup in label_lookups.items():
            random_vote_results = [
                structured_vote_study(
                    output,
                    random_neighbors[(seed, output.study_key)],
                    label_lookup,
                    margin=args.gray_zone_margin,
                    gray_zone_only=True,
                    similarity_weighted=False,
                )
                for output in outputs
            ]
            random_vote_method = (
                f"random_knn_majority_gray_{evidence_policy}_seed{seed}"
            )
            prediction_methods[random_vote_method] = structured_vote_status_map(
                random_vote_results
            )
            vote_evidence_rows.extend(
                _vote_rows(random_vote_method, random_vote_results)
            )

        random_keyword_results = [
            fuse_study_labels(
                fusion_vision_inputs(output),
                random_neighbors[(seed, output.study_key)],
                study_key=output.study_key,
                margin=args.gray_zone_margin,
            )
            for output in outputs
        ]
        prediction_methods[f"random_keyword_fusion_seed{seed}"] = (
            _fusion_status_map(random_keyword_results)
        )

    selected_labels = labels_frame[
        labels_frame["study_key"].astype(str).isin(key_set)
    ].copy()
    ground_truth = study_labels_to_ground_truth_strata(
        selected_labels,
        study_keys=study_keys,
    )
    policy_records = {
        "explicit": ground_truth.explicit,
        "no_finding_derived": ground_truth.no_finding_derived,
        "combined_training_policy": ground_truth.combined,
    }
    outputs_by_key = study_outputs_by_key(outputs)
    judge_runs = []
    for policy_name, full_records in policy_records.items():
        gray_records = filter_gray_zone_ground_truth(
            full_records,
            outputs_by_key,
            margin=args.gray_zone_margin,
        )
        for scope, records in (("full", full_records), ("gray_zone", gray_records)):
            for method, predictions in prediction_methods.items():
                judge_runs.append(
                    run_named_judge_result(
                        name=f"{method}_{policy_name}_{scope}",
                        eval_scope=scope,
                        ground_truth_records=records,
                        predicted_statuses=predictions,
                        ground_truth_policy=policy_name,
                    )
                )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(retrieval_trace_rows).to_csv(
        args.output_dir / "retrieval_trace.csv", index=False
    )
    pd.DataFrame(vote_evidence_rows).to_csv(
        args.output_dir / "structured_vote_evidence.csv", index=False
    )
    pd.DataFrame(_prediction_rows(prediction_methods)).to_csv(
        args.output_dir / "method_predictions.csv", index=False
    )
    matched_thresholds.to_csv(
        args.output_dir / "matched_thresholds_by_label.csv", index=False
    )
    per_label_metrics_frame(judge_runs).to_csv(
        args.output_dir / "per_label_metrics.csv", index=False
    )
    uncertain_status_metrics_frame(judge_runs).to_csv(
        args.output_dir / "uncertain_status_metrics.csv", index=False
    )
    status_confusion_by_label_frame(judge_runs).to_csv(
        args.output_dir / "status_confusion_by_label.csv", index=False
    )
    summary = {
        "experiment": "phase1_non_llm_retrieval_baselines_v1",
        "vision_outputs_cache": str(args.vision_outputs_cache),
        "vision_cache_metadata": vision_metadata,
        "reference_fusion_csv": str(args.reference_fusion_csv),
        "study_labels_csv": str(args.study_labels_csv),
        "vector_db_dir": str(args.vector_db_dir),
        "collection_name": args.collection_name,
        "index_count": len(random_pool),
        "study_count": len(outputs),
        "retrieval_top_k": args.retrieval_top_k,
        "gray_zone_margin": args.gray_zone_margin,
        "random_seeds": list(seeds),
        "methods": list(prediction_methods),
        "ground_truth_scoreable_cells": {
            "explicit": int(ground_truth.provenance["explicit_scoreable"].sum()),
            "no_finding_derived": int(
                ground_truth.provenance["no_finding_derived_scoreable"].sum()
            ),
            "combined_training_policy": int(
                ground_truth.provenance["combined_scoreable"].sum()
            ),
        },
        "runs": [named_judge_summary_payload(run) for run in judge_runs],
    }
    (args.output_dir / "judge_summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    print(f"[Phase1] wrote outputs -> {args.output_dir}")
    for run in summary["runs"]:
        if run.get("skipped") or run["eval_scope"] != "full":
            continue
        if run["ground_truth_policy"] not in (
            "explicit",
            "combined_training_policy",
        ):
            continue
        macro_f1 = run.get("macro_f1")
        macro_text = "n/a" if macro_f1 is None else f"{macro_f1:.4f}"
        print(
            f"[Phase1] {run['name']}: macro_f1={macro_text} "
            f"coverage={run['coverage']:.4f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
