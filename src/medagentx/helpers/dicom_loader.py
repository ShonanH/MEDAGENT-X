import numpy as np
import pydicom
from pydicom.pixels import apply_modality_lut

def read_dicom_dataset(file_obj, stop_before_pixels=False):
   return pydicom.dcmread(
      file_obj, stop_before_pixels=stop_before_pixels,
   )

def load_dicom_pixel_array(file_obj):
   ds = read_dicom_dataset(file_obj, stop_before_pixels=False)

   image = ds.pixel_array
   image = apply_modality_lut(image, ds)
   image = image.astype(np.float32)

   photometric = getattr(ds, "PhotometricInterpretation", "")

   if photometric == "MONOCHROME1":
      image = np.max(image) - image

   return image, ds

def normalize_image_minmax(image):
   image = image.astype(np.float32)

   image_min = float(np.min(image))
   image_max = float(np.max(image))

   if image_max <= image_min:
      return np.zeros(image.shape, dtype=np.float32)

   image = (image - image_min) / (image_max - image_min)

   return image.astype(np.float32)

def load_normalized_dicom_image(file_obj):
   image, ds = load_dicom_pixel_array(file_obj)
   image = normalize_image_minmax(image)

   return image, ds