import torch
import torch.nn.functional as F

class ConvNeXtDataPreprocess:
   def __init__(self, image_size=224):
      self.image_size = image_size
      self.mean = torch.tensor([0.485, 0.456, 0.406]).view(3,1,1)
      self.std = torch.tensor([0.229, 0.224, 0.225]).view(3,1,1)

   
   def __call__(self, image):
      if image.shape[0] == 1:
         image = image.repeat(3,1,1)

      image = image.unsqueeze(0)

      image = F.interpolate(
         image, 
         size=(self.image_size, self.image_size),
         mode="bilinear",
         align_corners=False,
      )

      image = image.squeeze(0)

      image = (image - self.mean) / self.std


      return image