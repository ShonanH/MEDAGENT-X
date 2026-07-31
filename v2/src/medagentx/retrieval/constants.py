"""Locked identifiers and defaults for RAD-DINO image retrieval."""

from __future__ import annotations

from medagentx.splits.constants import TRAIN_SPLIT
from medagentx.vision.constants import VISION_BACKEND_ID

RETRIEVAL_POLICY_VERSION = "raddino_image_retrieval_policy_v1"
RETRIEVAL_INDEX_ID = "raddino_train_v1"

# Offline index corpus: train split only (no val/test leakage).
INDEX_BUILD_SPLIT = TRAIN_SPLIT

# Chroma collection settings.
DEFAULT_COLLECTION_NAME = "medagentx_train_studies_v1"
CHROMA_DISTANCE_SPACE = "cosine"

# Query defaults for the Retrieval Agent.
DEFAULT_TOP_K = 5
QUERY_CANDIDATE_MULTIPLIER = 8
QUERY_CANDIDATE_MIN_EXTRA = 20

# Locked exclusion rules at query time.
EXCLUDE_SAME_STUDY = True
EXCLUDE_SAME_PATIENT = True

# Report payload stored per indexed study (no canonical GT labels).
REPORT_PAYLOAD_COLUMNS: tuple[str, ...] = (
    "section_findings",
    "section_impression",
)

# Chroma metadata fields required on every indexed study.
INDEX_METADATA_COLUMNS: tuple[str, ...] = (
    "study_key",
    "deid_patient_id",
)

# Default artifact location under a cohort root.
DEFAULT_RETRIEVAL_SUBDIR = f"retrieval/{RETRIEVAL_INDEX_ID}"

# Embedding extraction reuses the fine-tuned vision backend checkpoint.
EMBEDDING_BACKEND_ID = VISION_BACKEND_ID

# Index-build runtime defaults.
DEFAULT_EMBED_BATCH_SIZE = 16
DEFAULT_EMBED_NUM_WORKERS = 0
DEFAULT_PROGRESS_EVERY_BATCHES = 10

# Cached RAD-DINO study embeddings written after the first successful embed pass.
DEFAULT_EMBEDDINGS_CACHE_NAME = "study_embeddings.npz"

# Truncate long report payloads before writing to Chroma.
DEFAULT_MAX_DOCUMENT_CHARS = 12_000
