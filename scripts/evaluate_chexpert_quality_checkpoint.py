"""
Evaluate a saved ConvNeXt-Tiny CheXpert image-quality checkpoint.

This script:
1. Loads a saved checkpoint.
2. Rebuilds the same validation split used during training.
3. Loads local downloaded DICOMs or cached PNGs.
4. Runs inference on the validation set.
5. Prints:
   - label distribution
   - accuracy
   - per-class precision
   - per-class recall
   - per-class F1
   - macro F1
   - confusion matrix
6. Optionally saves validation predictions to CSV.

Use this to compare:
- 4-class image_quality_label model
- binary quality_gate model
- 3-class collapsed quality model
"""

import argparse
import csv
import random
from pathlib import Path

import numpy as np
import pydicom
import torch
import torch.nn as nn
from PIL import Image
from pydicom.pixels import apply_modality_lut
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny


def parse_args():
    parser = argparse.ArgumentParser(
        description="Evaluate a saved CheXpert Plus ConvNeXt quality checkpoint."
    )

    parser.add_argument("--checkpoint-path", type=Path, required=True)
    parser.add_argument("--csv-path", type=Path, default=None)
    parser.add_argument("--local-dicom-root", type=Path, required=True)
    parser.add_argument("--image-cache-dir", type=Path, default=Path("outputs/chexpert_plus/dicom_png_cache"))
    parser.add_argument("--path-column", type=str, default=None)
    parser.add_argument("--label-column", type=str, default=None)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--val-fraction", type=float, default=None)
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--predictions-path", type=Path, default=None)

    return parser.parse_args()


def normalize_index_to_label(index_to_label):
    return {int(key): value for key, value in index_to_label.items()}


def read_csv_rows(csv_path, path_column, label_column, label_to_index):
    rows = []

    with csv_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        for row in reader:
            label = row[label_column].strip().lower()

            if label not in label_to_index:
                raise ValueError(f"Unknown label for this checkpoint: {label}")

            rows.append(row)

    return rows


def stratified_split(rows, label_column, val_fraction, seed):
    rng = random.Random(seed)
    label_to_rows = {}

    for row in rows:
        label = row[label_column].strip().lower()
        label_to_rows.setdefault(label, []).append(row)

    train_rows = []
    val_rows = []

    for _, label_rows in label_to_rows.items():
        rng.shuffle(label_rows)

        val_count = max(1, int(round(len(label_rows) * val_fraction)))

        if len(label_rows) == 1:
            train_rows.extend(label_rows)
            continue

        val_rows.extend(label_rows[:val_count])
        train_rows.extend(label_rows[val_count:])

    rng.shuffle(train_rows)
    rng.shuffle(val_rows)

    return train_rows, val_rows


def clean_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def dicom_to_pil_image(file_obj):
    ds = pydicom.dcmread(file_obj)

    image = ds.pixel_array
    image = apply_modality_lut(image, ds)
    image = image.astype(np.float32)

    if getattr(ds, "PhotometricInterpretation", "") == "MONOCHROME1":
        image = np.max(image) - image

    lower = np.percentile(image, 1)
    upper = np.percentile(image, 99)

    if upper <= lower:
        image = np.zeros(image.shape, dtype=np.float32)
    else:
        image = np.clip((image - lower) / (upper - lower), 0.0, 1.0)

    image = (image * 255.0).astype(np.uint8)

    return Image.fromarray(image).convert("RGB")


def load_image(dicom_path, local_dicom_root, cache_dir):
    dicom_path = clean_dicom_path(dicom_path)

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = dicom_path.replace("/", "__").replace(".dcm", ".png")
    cache_path = cache_dir / cache_name

    if cache_path.exists():
        try:
            with Image.open(cache_path) as cached_image:
                cached_image.load()
                return cached_image.convert("RGB")
        except Exception:
            cache_path.unlink(missing_ok=True)

    local_path = local_dicom_root / dicom_path

    if not local_path.exists():
        raise FileNotFoundError(f"Local DICOM not found: {local_path}")

    with local_path.open("rb") as file_obj:
        image = dicom_to_pil_image(file_obj)

    tmp_cache_path = cache_path.with_suffix(".tmp.png")
    image.save(tmp_cache_path)
    tmp_cache_path.replace(cache_path)

    return image


class CheXpertEvalDataset(Dataset):
    def __init__(
        self,
        rows,
        local_dicom_root,
        image_cache_dir,
        path_column,
        label_column,
        label_to_index,
        transform,
    ):
        self.rows = rows
        self.local_dicom_root = local_dicom_root
        self.image_cache_dir = image_cache_dir
        self.path_column = path_column
        self.label_column = label_column
        self.label_to_index = label_to_index
        self.transform = transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]

        image = load_image(
            dicom_path=row[self.path_column],
            local_dicom_root=self.local_dicom_root,
            cache_dir=self.image_cache_dir,
        )

        label_name = row[self.label_column].strip().lower()
        label_index = self.label_to_index[label_name]

        if self.transform is not None:
            image = self.transform(image)

        return {
            "image": image,
            "label": torch.tensor(label_index, dtype=torch.long),
            "label_name": label_name,
            "dicom_path": clean_dicom_path(row[self.path_column]),
        }


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")

    return torch.device("cpu")


def build_model(num_classes):
    weights = ConvNeXt_Tiny_Weights.IMAGENET1K_V1
    model = convnext_tiny(weights=weights)

    in_features = model.classifier[2].in_features
    model.classifier[2] = nn.Linear(in_features, num_classes)

    return model


def clean_state_dict_keys(state_dict):
    cleaned = {}

    for key, value in state_dict.items():
        if key.startswith("module."):
            key = key.removeprefix("module.")

        cleaned[key] = value

    return cleaned


def compute_metrics(targets, predictions, index_to_label):
    num_classes = len(index_to_label)
    matrix = np.zeros((num_classes, num_classes), dtype=int)

    for target, prediction in zip(targets, predictions):
        matrix[target, prediction] += 1

    accuracy = sum(int(t == p) for t, p in zip(targets, predictions)) / max(len(targets), 1)

    per_class = []
    f1_scores = []

    for class_index in range(num_classes):
        tp = matrix[class_index, class_index]
        fp = matrix[:, class_index].sum() - tp
        fn = matrix[class_index, :].sum() - tp
        support = matrix[class_index, :].sum()

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)

        if precision + recall == 0:
            f1 = 0.0
        else:
            f1 = 2 * precision * recall / (precision + recall)

        f1_scores.append(f1)

        per_class.append(
            {
                "label": index_to_label[class_index],
                "support": int(support),
                "precision": precision,
                "recall": recall,
                "f1": f1,
            }
        )

    return {
        "accuracy": accuracy,
        "macro_f1": sum(f1_scores) / max(len(f1_scores), 1),
        "per_class": per_class,
        "confusion_matrix": matrix,
    }


def main():
    args = parse_args()

    checkpoint = torch.load(args.checkpoint_path, map_location="cpu")
    checkpoint_args = checkpoint.get("args", {})

    csv_path = args.csv_path or Path(checkpoint_args["csv_path"])
    path_column = args.path_column or checkpoint_args.get("path_column", "dicom_path")
    label_column = args.label_column or checkpoint_args.get("label_column", "image_quality_label")
    val_fraction = args.val_fraction or float(checkpoint_args.get("val_fraction", 0.2))
    seed = args.seed if args.seed is not None else int(checkpoint_args.get("seed", 42))

    label_to_index = checkpoint["label_to_index"]
    index_to_label = normalize_index_to_label(checkpoint["index_to_label"])
    num_classes = len(index_to_label)

    rows = read_csv_rows(
        csv_path=csv_path,
        path_column=path_column,
        label_column=label_column,
        label_to_index=label_to_index,
    )

    _, val_rows = stratified_split(
        rows=rows,
        label_column=label_column,
        val_fraction=val_fraction,
        seed=seed,
    )

    print("Checkpoint:", args.checkpoint_path)
    print("CSV:", csv_path)
    print("Label column:", label_column)
    print("Path column:", path_column)
    print("Validation rows:", len(val_rows))
    print("Labels:", [index_to_label[i] for i in range(num_classes)])

    label_counts = {}

    for row in val_rows:
        label = row[label_column].strip().lower()
        class_index = label_to_index[label]
        label_name = index_to_label[class_index]
        label_counts[label_name] = label_counts.get(label_name, 0) + 1

    print("Validation label distribution:", label_counts)

    transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    dataset = CheXpertEvalDataset(
        rows=val_rows,
        local_dicom_root=args.local_dicom_root,
        image_cache_dir=args.image_cache_dir,
        path_column=path_column,
        label_column=label_column,
        label_to_index=label_to_index,
        transform=transform,
    )

    loader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    device = get_device()
    model = build_model(num_classes=num_classes)
    model.load_state_dict(clean_state_dict_keys(checkpoint["model_state_dict"]))
    model = model.to(device)
    model.eval()

    targets = []
    predictions = []
    prediction_rows = []

    with torch.no_grad():
        for batch_index, batch in enumerate(loader, start=1):
            images = batch["image"].to(device)
            labels = batch["label"].to(device)

            logits = model(images)
            probabilities = torch.softmax(logits, dim=1)
            predicted = logits.argmax(dim=1)

            targets.extend(labels.cpu().tolist())
            predictions.extend(predicted.cpu().tolist())

            for i in range(images.size(0)):
                true_index = int(labels[i].cpu().item())
                pred_index = int(predicted[i].cpu().item())

                row = {
                    "dicom_path": batch["dicom_path"][i],
                    "true_label": index_to_label[true_index],
                    "predicted_label": index_to_label[pred_index],
                    "correct": true_index == pred_index,
                }

                for class_index in range(num_classes):
                    row[f"prob_{index_to_label[class_index]}"] = float(
                        probabilities[i, class_index].cpu().item()
                    )

                prediction_rows.append(row)

            if batch_index == 1 or batch_index % 10 == 0 or batch_index == len(loader):
                print(f"Evaluated batch {batch_index}/{len(loader)}", flush=True)

    metrics = compute_metrics(targets, predictions, index_to_label)

    print()
    print(f"Accuracy: {metrics['accuracy']:.4f}")
    print(f"Macro F1: {metrics['macro_f1']:.4f}")
    print()

    print("Per-class metrics:")
    for item in metrics["per_class"]:
        print(
            f"{item['label']:20s} "
            f"support={item['support']:4d} "
            f"precision={item['precision']:.4f} "
            f"recall={item['recall']:.4f} "
            f"f1={item['f1']:.4f}"
        )

    print()
    print("Confusion matrix rows=true, cols=predicted")
    print("labels:", [index_to_label[i] for i in range(num_classes)])
    print(metrics["confusion_matrix"])

    if args.predictions_path is not None:
        args.predictions_path.parent.mkdir(parents=True, exist_ok=True)

        with args.predictions_path.open("w", newline="") as file:
            writer = csv.DictWriter(file, fieldnames=list(prediction_rows[0].keys()))
            writer.writeheader()
            writer.writerows(prediction_rows)

        print()
        print("Saved predictions:", args.predictions_path)


if __name__ == "__main__":
    main()