import json
from pathlib import Path
from typing import Optional, Callable
import numpy as np
import torch
from PIL import Image
from torch.utils.data import Dataset

from typing import Optional, Callable
class LDCTIQAC2023Dataset(Dataset):
   def __init__(self, root_dir: Path, transform: Optional[Callable] = None):
      self.root_dir = root_dir
      self.transform = transform
      self.image_dir = root_dir / "images"
      self.labels_path = root_dir / "train.json"

      with open(self.labels_path, "r") as f:
         self.labels = json.load(f)
      
      self.filenames = list(self.labels.keys())


   def __len__(self):
      return len(self.filenames)

   def __getitem__(self, idx):
      filename = self.filenames[idx]
      image_path = self.image_dir / filename

      image = Image.open(image_path)
      image = np.array(image, dtype=np.float32)

      raw_score = float(self.labels[filename])

      quality_score = raw_score + 1.0 # shifting the score scale from 0-4 to 1-5

      clinical_level = self.raw_score_to_clinical_level(raw_score)

      image = torch.from_numpy(image)

      # Shape: [H, W] -> [1, H, W]

      image = image.unsqueeze(0)

      if self.transform is not None:
         image = self.transform(image)

      
      return {
         "image": image,
         "raw_score": torch.tensor(raw_score, dtype=torch.float32),
         "quality_score": torch.tensor(quality_score, dtype=torch.float32),
         "clinical_level": torch.tensor(clinical_level, dtype=torch.long),
         "filename": filename,
      }


   @staticmethod
   def raw_score_to_clinical_level(raw_score):
      if raw_score < 0.5:
         return 1
      if raw_score < 1.5:
         return 2
      if raw_score < 2.5:
         return 3
      if raw_score < 3.5:
         return 4
      return 5
      


   