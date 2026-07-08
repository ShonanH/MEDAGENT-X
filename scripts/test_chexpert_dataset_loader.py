import argparse
import sys
from pathlib import Path

from torch.utils.data import DataLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.transforms import ConvNeXtDataPreprocess
from src.medagentx.helpers.chexpert_plus_dataset import CheXpertPlusDicomDataset

def parse_args():
    parser = argparse.ArgumentParser(
        description="Test the CheXpert Plus PyTorch Dataset loader."
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
        "--row-index",
        type=int,
        default=0,
    )

    return parser.parse_args()


def main():
    args = parse_args()

    transform = ConvNeXtDataPreprocess(image_size=224)

    dataset = CheXpertPlusDicomDataset(manifest_path=args.manifest_path, transform=transform)

    print("Dataset length: ", len(dataset))

    sample = dataset[args.row_index]

    print()
    print("Single sample test passed.")
    print("Study key:", sample["study_key"])
    print("DICOM path:", sample["dicom_path"])
    print("Image tensor shape:", tuple(sample["image"].shape))
    print("Image dtype:", sample["image"].dtype)
    print("Image min:", float(sample["image"].min()))
    print("Image max:", float(sample["image"].max()))
    print("Age:", sample["age"])
    print("Sex:", sample["sex"])
    print("Image count:", sample["image_count"])
    print("View position:", sample["view_position"])
    print("Photometric:", sample["photometric"])
    print("Report available:", bool(str(sample["report"]).strip()))
    print("Impression available:", bool(str(sample["section_impression"]).strip()))

    dataloader = DataLoader(dataset, batch_size=2, shuffle=False, num_workers=0)
    batch = next(iter(dataloader))

    print()
    print("Dataloader batch test passed!!")
    print("Batch image shape: ", tuple(batch["image"].shape))
    print("Batch study keys: ", batch["study_key"])

if __name__ == "__main__":
    main()