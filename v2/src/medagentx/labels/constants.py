"""CheXpert label inventory and versioned policy identifiers."""

DISEASE_LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
    "Pneumonia",
    "Pneumothorax",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "Enlarged Cardiomediastinum",
    "Pleural Other",
)

CHEXPERT_COMPETITION_LABELS: tuple[str, ...] = (
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Pleural Effusion",
)

NON_DISEASE_LABELS: tuple[str, ...] = (
    "Support Devices",
    "No Finding",
)

ALL_CHEXPERT_LABELS: tuple[str, ...] = DISEASE_LABELS + NON_DISEASE_LABELS

CHEXPERT_TRAINING_POLICY_VERSION = "chexpert_training_policy_v1"
