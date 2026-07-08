import argparse
import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.transforms import ConvNeXtDataPreprocess
from src.medagentx.helpers.chexpert_plus_dataset import CheXpertPlusDicomDataset
from src.medagentx.models.convnext_baseline import ConvNeXtQualityRegressor


def parse_args():
    parser = argparse.ArgumentParser(
        description="Test pretrained ConvNeXt forward pass on CheXpert Plus DICOM images."
    )

    parser.add_argument(
        "--manifest-path",
        type=Path,
        default=PROJECT_ROOT
        / "data"
        / "processed"
        / "chexpert_plus_50_study_manifest.csv",
    )

    parser.add_argument(
        "--batch-size",
        type=int,
        default=2,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    print("Device:", device)

    transform = ConvNeXtDataPreprocess(image_size=224)

    dataset = CheXpertPlusDicomDataset(
        manifest_path=args.manifest_path,
        transform=transform,
    )

    dataloader = DataLoader(
        dataset,
        batch_size=args.batch_size,
        shuffle=False,
        num_workers=0,
    )

    print("Dataset length:", len(dataset))

    batch = next(iter(dataloader))

    images = batch["image"].to(device)

    print("Input batch shape:", tuple(images.shape))
    print("Input dtype:", images.dtype)

    model = ConvNeXtQualityRegressor(pretrained=True)
    model = model.to(device)
    model.eval()

    with torch.no_grad():
        scores = model(images)

    print()
    print("Forward pass passed.")
    print("Output shape:", tuple(scores.shape))
    print("Output dtype:", scores.dtype)
    print("Raw scores:", scores.detach().cpu().tolist())

    print()
    print("Batch study keys:", batch["study_key"])


if __name__ == "__main__":
    main()