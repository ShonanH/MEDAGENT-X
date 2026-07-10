"""
Train ConvNeXt-Tiny to predict CheXpert Plus image-quality labels.

What this script does:
1. Reads a CSV file that already contains image-quality labels.
   Expected label column:
       image_quality_label

   Expected image path column:
       dicom_path

2. Converts each quality label into a class index:
       review    -> 0
       uncertain -> 1
       usable    -> 2
       good      -> 3

3. Loads each medical image from disk.
   - If the file is a DICOM image, it uses pydicom.
   - If the file is PNG/JPG/TIF, it uses PIL.
   - The image is normalized and converted to 3-channel RGB because ConvNeXt expects RGB input.

4. Splits the CSV rows into training and validation sets.
   The split is stratified, meaning it tries to preserve the label distribution.

5. Loads pretrained ConvNeXt-Tiny.
   The original ImageNet classifier is replaced with a 4-class classifier for:
       review, uncertain, usable, good

6. Trains the model using cross-entropy classification loss.
   Class weights are used because the 50-image dataset may have imbalanced labels.

7. Prints training and validation metrics after every epoch:
       train loss
       train accuracy
       validation loss
       validation accuracy
       validation macro F1

8. Saves the best checkpoint based on validation loss.

Important:
This is a pipeline training script for CheXpert Plus image-quality labels.
For small samples, treat the result as a sanity check. For larger samples,
use local downloaded DICOMs plus the PNG cache so training does not repeatedly
stream files from Redivis.
"""

import argparse
import csv
import random
from pathlib import Path
import redivis
import pydicom
from pydicom.pixels import apply_modality_lut

import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torch.utils.data import DataLoader, Dataset
from torchvision import transforms
from torchvision.models import ConvNeXt_Tiny_Weights, convnext_tiny

LABEL_TO_INDEX = {
    "review": 0,
    "uncertain": 0,
    "usable": 1,
    "good": 2,
}

INDEX_TO_LABEL = {
    0: "review_or_uncertain",
    1: "usable",
    2: "good",
}

DICOM_TRAIN_TABLE = "aimi.chexpert_plus:5yyj:v1_0.dicom_train:1934"

def parse_args():
    parser = argparse.ArgumentParser(
        description="Train ConvNeXt-Tiny on CheXpert Plus image-quality labels."
    )

    parser.add_argument("--csv-path", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/chexpert_plus/convnext_quality_label"))
    parser.add_argument("--path-column", type=str, default="dicom_path")
    parser.add_argument("--label-column", type=str, default="image_quality_label")
    parser.add_argument("--epochs", type=int, default=20)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--learning-rate", type=float, default=1e-4)
    parser.add_argument("--val-fraction", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--dicom-table-ref",
        type=str,
        default=DICOM_TRAIN_TABLE,
        help="Redivis file index table for CheXpert Plus DICOM files.",
    )

    parser.add_argument(
        "--local-dicom-root",
        type=Path,
        default=None,
        help="Local folder that contains downloaded CheXpert Plus DICOMs.",
    )
    
    parser.add_argument(
        "--image-cache-dir",
        type=Path,
        default=Path("outputs/chexpert_plus/dicom_png_cache"),
        help="Local PNG cache to avoid decoding the same DICOM every epoch.",
    )

    return parser.parse_args()


def seed_everything(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


def get_device():
    if torch.cuda.is_available():
        return torch.device("cuda")

    if torch.backends.mps.is_available():
        return torch.device("mps")

    return torch.device("cpu")


def read_csv_rows(csv_path, path_column, label_column):
    rows = []

    with csv_path.open("r", newline="") as file:
        reader = csv.DictReader(file)

        if path_column not in reader.fieldnames:
            raise ValueError(f"Missing path column: {path_column}")

        if label_column not in reader.fieldnames:
            raise ValueError(f"Missing label column: {label_column}")

        for row in reader:
            label = row[label_column].strip().lower()

            if label not in LABEL_TO_INDEX:
                raise ValueError(f"Unknown image quality label: {label}")

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

    for label, label_rows in label_to_rows.items():
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

def clean_redivis_dicom_path(path):
    path = str(path).strip()

    if path.startswith("train/"):
        path = path.removeprefix("train/")

    return path


def dicom_to_pil_image(file_obj):
    ds = pydicom.dcmread(file_obj)

    image = ds.pixel_array
    image = apply_modality_lut(image, ds)
    image = image.astype(np.float32)

    photometric = getattr(ds, "PhotometricInterpretation", "")

    if photometric == "MONOCHROME1":
        image = np.max(image) - image

    lower = np.percentile(image, 1)
    upper = np.percentile(image, 99)

    if upper <= lower:
        image = np.zeros(image.shape, dtype=np.float32)
    else:
        image = np.clip((image - lower) / (upper - lower), 0.0, 1.0)

    image = (image * 255.0).astype(np.uint8)

    return Image.fromarray(image).convert("RGB")


def load_image(dicom_path, local_dicom_root, dicom_table, cache_dir):
    dicom_path = clean_redivis_dicom_path(dicom_path)

    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_name = dicom_path.replace("/", "__").replace(".dcm", ".png")
    cache_path = cache_dir / cache_name

    if cache_path.exists():
        try:
            with Image.open(cache_path) as cached_image:
                cached_image.load()
                return cached_image.convert("RGB")

        except Exception:
            print(f"Removing corrupted cache file: {cache_path}", flush=True)
            cache_path.unlink(missing_ok=True)

    if local_dicom_root is not None:
        local_path = local_dicom_root / dicom_path

        if not local_path.exists():
            raise FileNotFoundError(f"Local DICOM not found: {local_path}")

        with local_path.open("rb") as file_obj:
            image = dicom_to_pil_image(file_obj)

    else:
        dicom_file = dicom_table.file(dicom_path)

        with dicom_file.open("rb") as file_obj:
            image = dicom_to_pil_image(file_obj)

    tmp_cache_path = cache_path.with_suffix(".tmp.png")
    image.save(tmp_cache_path)
    tmp_cache_path.replace(cache_path)

    return image
    
class CheXpertQualityDataset(Dataset):
    def __init__(
        self,
        rows,
        local_dicom_root,
        dicom_table,
        image_cache_dir,
        path_column,
        label_column,
        transform,
    ):
        self.rows = rows
        self.local_dicom_root = local_dicom_root
        self.dicom_table = dicom_table
        self.image_cache_dir = image_cache_dir
        self.path_column = path_column
        self.label_column = label_column
        self.transform = transform

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, index):
        row = self.rows[index]

        image = load_image(
            dicom_path=row[self.path_column],
            local_dicom_root=self.local_dicom_root,
            dicom_table=self.dicom_table,
            cache_dir=self.image_cache_dir,
        )

        label_name = row[self.label_column].strip().lower()
        label = LABEL_TO_INDEX[label_name]

        if self.transform is not None:
            image = self.transform(image)

        return {
            "image": image,
            "label": torch.tensor(label, dtype=torch.long),
            "path": clean_redivis_dicom_path(row[self.path_column]),
        }

def build_model(num_classes):
    weights = ConvNeXt_Tiny_Weights.IMAGENET1K_V1
    model = convnext_tiny(weights=weights)

    in_features = model.classifier[2].in_features
    model.classifier[2] = nn.Linear(in_features, num_classes)

    return model


def class_weights(rows, label_column, device):
    counts = torch.zeros(len(INDEX_TO_LABEL), dtype=torch.float32)
    for row in rows:
        label = row[label_column].strip().lower()
        counts[LABEL_TO_INDEX[label]] += 1

    weights = counts.sum() / torch.clamp(counts, min=1.0)
    weights = weights / weights.mean()

    return weights.to(device)


def run_epoch(model, loader, criterion, optimizer, device, train):
    if train:
        model.train()
    else:
        model.eval()

    total_loss = 0.0
    total_correct = 0
    total_examples = 0
    all_targets = []
    all_predictions = []

    for batch_index, batch in enumerate(loader, start=1):
        images = batch["image"].to(device)
        labels = batch["label"].to(device)

        with torch.set_grad_enabled(train):
            logits = model(images)
            loss = criterion(logits, labels)

            if train:
                optimizer.zero_grad()
                loss.backward()
                optimizer.step()

        predictions = logits.argmax(dim=1)

        total_loss += float(loss.item()) * images.size(0)
        total_correct += int((predictions == labels).sum().item())
        total_examples += images.size(0)

        all_targets.extend(labels.detach().cpu().tolist())
        all_predictions.extend(predictions.detach().cpu().tolist())

        if batch_index == 1 or batch_index % 10 == 0 or batch_index == len(loader):
            phase = "train" if train else "val"
            print(
                f"{phase} batch {batch_index}/{len(loader)} | "
                f"loss={loss.item():.4f}",
                flush=True,
            )

    avg_loss = total_loss / max(total_examples, 1)
    accuracy = total_correct / max(total_examples, 1)

    return avg_loss, accuracy, all_targets, all_predictions


def macro_f1(targets, predictions):
    scores = []

    for class_index in range(len(INDEX_TO_LABEL)):
        tp = sum(1 for t, p in zip(targets, predictions) if t == class_index and p == class_index)
        fp = sum(1 for t, p in zip(targets, predictions) if t != class_index and p == class_index)
        fn = sum(1 for t, p in zip(targets, predictions) if t == class_index and p != class_index)

        precision = tp / max(tp + fp, 1)
        recall = tp / max(tp + fn, 1)

        if precision + recall == 0:
            scores.append(0.0)
        else:
            scores.append(2 * precision * recall / (precision + recall))

    return sum(scores) / len(scores)


def print_confusion_matrix(targets, predictions):
    num_classes = len(INDEX_TO_LABEL)
    matrix = np.zeros((num_classes, num_classes), dtype=int)

    for target, prediction in zip(targets, predictions):
        matrix[target, prediction] += 1

    print("Confusion matrix rows=true, cols=predicted")
    print("labels:", [INDEX_TO_LABEL[i] for i in range(num_classes)])
    print(matrix)


def main():
    args = parse_args()
    seed_everything(args.seed)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    local_dicom_root = Path(args.local_dicom_root) if args.local_dicom_root else None
    dicom_table = None if local_dicom_root is not None else redivis.table(args.dicom_table_ref)
    
    rows = read_csv_rows(args.csv_path, args.path_column, args.label_column)
    train_rows, val_rows = stratified_split(
        rows=rows,
        label_column=args.label_column,
        val_fraction=args.val_fraction,
        seed=args.seed,
    )

    print("Total rows:", len(rows))
    print("Train rows:", len(train_rows))
    print("Val rows:", len(val_rows))

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


    train_dataset = CheXpertQualityDataset(
        rows=train_rows,
        path_column=args.path_column,
        label_column=args.label_column,
        transform=transform,
        local_dicom_root=local_dicom_root,
        dicom_table=dicom_table,
        image_cache_dir=args.image_cache_dir,
    )
    
    val_dataset = CheXpertQualityDataset(
        rows=val_rows,
        path_column=args.path_column,
        label_column=args.label_column,
        transform=transform,
        local_dicom_root=local_dicom_root,
        dicom_table=dicom_table,
        image_cache_dir=args.image_cache_dir,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=args.batch_size,
        shuffle=True,
        num_workers=0,
    )

    val_loader = DataLoader(
        val_dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    device = get_device()
    print("Device:", device)

    model = build_model(num_classes=len(INDEX_TO_LABEL)).to(device)
    
    criterion = nn.CrossEntropyLoss(
        weight=class_weights(train_rows, args.label_column, device)
    )

    optimizer = torch.optim.AdamW(
        model.parameters(),
        lr=args.learning_rate,
        weight_decay=1e-4,
    )

    best_val_loss = float("inf")
    best_path = args.output_dir / "best_convnext_tiny_quality_label.pt"

    for epoch in range(1, args.epochs + 1):
        train_loss, train_acc, _, _ = run_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
            device=device,
            train=True,
        )

        val_loss, val_acc, val_targets, val_predictions = run_epoch(
            model=model,
            loader=val_loader,
            criterion=criterion,
            optimizer=None,
            device=device,
            train=False,
        )

        val_macro_f1 = macro_f1(val_targets, val_predictions)

        print(
            f"Epoch {epoch:03d} | "
            f"train_loss={train_loss:.4f} train_acc={train_acc:.4f} | "
            f"val_loss={val_loss:.4f} val_acc={val_acc:.4f} val_macro_f1={val_macro_f1:.4f}"
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss

            torch.save(
                {
                    "model_state_dict": model.state_dict(),
                    "label_to_index": LABEL_TO_INDEX,
                    "index_to_label": INDEX_TO_LABEL,
                    "val_loss": val_loss,
                    "val_accuracy": val_acc,
                    "val_macro_f1": val_macro_f1,
                    "args": vars(args),
                },
                best_path,
            )

            print("Saved best checkpoint:", best_path)

    print()
    print("Best validation loss:", best_val_loss)
    print("Best checkpoint:", best_path)
    print_confusion_matrix(val_targets, val_predictions)


if __name__ == "__main__":
    main()