from torch.utils.data import DataLoader

dataset = LDCTIQAC2023Dataset(root_dir="data/raw/ldctiqac2023")

print(len(dataset))

sample = dataset[0]

print(sample["filename"])
print(sample["image"].shape)
print(sample["raw_score"])
print(sample["quality_score"])
print(sample["clinical_level"])

loader = DataLoader(dataset, batch_size=8, shuffle=True)

batch = next(iter(loader))

print(batch["filename"])
print(batch["raw_score"])
print(batch["quality_score"])
print(batch["clinical_level"])