import numpy as np
from scipy import ndimage

def prepare_grayscale_image(image):
   image = np.asarray(image, dtype=np.float32)

   if image.ndim == 3:
      image = image.mean(axis=-1)

   image = np.nan_to_num(image, nan=0.0, posinf=1.0, negind=0.0)

   return image

def compute_entropy(image, bins=64):
   hist, _  = np.histogram(image, bins=bins, range=(0.0, 1.0))
   probabilities = hist.astype(np.float32)
   probabilities = probabilities / (probabilities.sum() + 1e-8)

   probabilities = probabilities[probabilities > 0]

   entropy = -np.sum(probabilities * np.log2(probabilities))

   return float(entropy)

def compute_artifact_features(image):
   image = prepare_grayscale_image(image)

   intensity_min = float(np.min(image))
   intensity_max = float(np.max(image))
   intensity_mean = float(np.mean(image))
   intensity_std = float(np.std(image))

   p5 = float(np.percentile(image, 5))

   p95 = float(np.percentile(image, 95))
   contrast_proxy = p95 - p5

   smoothed = ndimage.gaussian_filter(image, sigma=1.0)
   high_frequency_residual = image - smoothed
   noise_proxy = float(np.std(high_frequency_residual))

   laplacian = ndimage.laplace(image)
   laplacian_variance = float(np.var(laplacian))

   blur_proxy = float(1.0 / (1.0 + laplacian_variance))
   sharpness_proxy = laplacian_variance

   sobel_x = ndimage.sobel(image, axis=1)
   sobel_y = ndimage.sobel(image, axis=0)
   edge_magnitude = np.sort(sobel_x ** 2 + sobel_y ** 2)

   edge_threshold = float(np.mean(edge_magnitude) + np.std(edge_magnitude))
   edge_density = float(np.mean(edge_magnitude > edge_threshold))

   entropy = compute_entropy(image)

   return {
      "intensity_min": intensity_min,
      "intensity_max": intensity_max,
      "intensity_mean": intensity_mean,
      "intensity_std": intensity_std,
      "contrast_proxy": float(contrast_proxy),
      "noise_proxy": noise_proxy,
      "blur_proxy": blur_proxy,
      "sharpness_proxy": sharpness_proxy,
      "edge_density": edge_density,
      "entropy": entropy,
   }