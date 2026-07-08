import argparse
import sys
from pathlib import Path

import pandas as pd
import torch
from torch.utils.data import DataLoader


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from data.transforms import ConvNeXtDataPreprocess
from src.medagentx.helpers.chexpert_plus_dataset import CheXpertPlusDicomDataset
from src.medagentx.models.convnext_baseline import ConvNeXtQualityRegressor


def parse_args():
    parser = argparse.ArgumentParser(
        description="Export raw pretrained ConvNeXt outputs for CheXpert Plus studies."
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
        "--output-path",
        type=Path,
        default=PROJECT_ROOT
        / "outputs"
        / "chexpert_plus"
        / "chexpert_plus_50_raw_convnext_outputs.csv",
    )

    parser.add_argument("--batch-size", type=int, default=4)

    return parser.parse_args()


def get_batch_value(batch, key, index):
    value = batch[key]

    if torch.is_tensor(value):
        return value[index].item()

    return value[index]


def chexpert_export_collate(samples):
    batch = {
        "image": torch.stack([sample["image"] for sample in samples], dim=0)
    }

    for key in samples[0].keys():
        if key == "image":
            continue

        values = []

        for sample in samples:
            value = sample.get(key, "")

            if value is None:
                value = ""

            values.append(value)

        batch[key] = values

    return batch

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
        collate_fn=chexpert_export_collate,
    )

    model = ConvNeXtQualityRegressor(pretrained=True)
    model = model.to(device)
    model.eval()

    output_rows = []

    with torch.no_grad():
        for batch_index, batch in enumerate(dataloader):
            images = batch["image"].to(device)
            raw_outputs = model(images).detach().cpu()

            for i in range(len(raw_outputs)):
                report_text = str(get_batch_value(batch, "report", i))
                impression_text = str(get_batch_value(batch, "section_impression", i))

                output_rows.append(
                    {
                        "study_key": get_batch_value(batch, "study_key", i),
                        "dicom_path": get_batch_value(batch, "dicom_path", i),
                        "deid_patient_id": get_batch_value(batch, "deid_patient_id", i),
                        "age": get_batch_value(batch, "age", i),
                        "sex": get_batch_value(batch, "sex", i),
                        "split": get_batch_value(batch, "split", i),
                        "image_count": get_batch_value(batch, "image_count", i),
                        "view_position": get_batch_value(batch, "view_position", i),
                        "photometric": get_batch_value(batch, "photometric", i),
                        "raw_model_output": float(raw_outputs[i]),
                        "report_available": bool(report_text.strip()),
                        "impression_available": bool(impression_text.strip()),
                    }
                )

            print(f"Processed batch {batch_index + 1}")

    output_df = pd.DataFrame(output_rows)

    args.output_path.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(args.output_path, index=False)

    print()
    print("Export complete.")
    print("Rows exported:", len(output_df))
    print("Saved to:", args.output_path)
    print()
    print("Raw model output summary:")
    print(output_df["raw_model_output"].describe())


if __name__ == "__main__":
    main()