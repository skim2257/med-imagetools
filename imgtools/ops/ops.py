import numpy as np

from .functional import *


class BaseOp:
    def __call__(self, *args, **kwargs):
        raise NotImplementedError


class Resample(BaseOp):
    def __init__(self, spacing, interpolation="linear", anti_alias=True, anti_alias_sigma=2., transform=None):
        self.spacing = spacing
        self.interpolation = interpolation
        self.anti_alias = anti_alias
        self.anti_alias_sigma = anti_alias_sigma
        self.transform = transform

    def __call__(self, image):
        return resample(image,
                        spacing=self.spacing,
                        interpolation=self.interpolation,
                        anti_alias=self.anti_alias,
                        anti_alias_sigma=self.anti_alias_sigma,
                        transform=self.transform)

class Resize(BaseOp):
    def __init__(self, size, interpolation="linear", anti_alias=True):
        self.size = size
        self.interpolation = interpolation
        self.anti_alias = anti_alias

    def __call__(self, image):
        return resize(image, new_size=self.size, interpolation=self.interpolation)

class Rotate(BaseOp):
    def __init__(self, rotation_centre, angles, interpolation="linear"):
        self.rotation_centre = rotation_centre
        self.angles = angles
        self.interpolation = interpolation

    def __call__(self, image):
        return rotate(image, rotation_centre=self.rotation_centre, angles=self.angles, interpolation=self.interpolation)


class InPlaneRotate(BaseOp):
    def __init__(self, angle, interpolation="linear"):
        self.angle = angle
        self.interpolation = interpolation

    def __call__(self, image):
        image_size = np.array(image.GetSize())
        image_centre = image_size // 2
        angles = (0., 0., self.angle)
        return rotate(image, rotation_centre=image_centre, angles=angles, interpolation=self.interpolation)

class Crop(BaseOp):
    def __init__(self, crop_centre, size):
        self.crop_centre = crop_centre
        self.size = size

    def __call__(self, image):
        return crop(image, crop_centre=self.crop_centre, size=self.size)

class CentreCrop(BaseOp):
    def __init__(self, size):
        self.size = size

    def __call__(self, image):
        image_size = np.array(image.GetSize())
        image_centre = image_size // 2
        return crop(image, crop_centre=image_centre, size=self.size)


def constant_pad(image, size, cval=0.):
    if isinstance(size, int):
        size_lower = size_upper = [size for _ in image.GetSize()]
    elif isinstance(size, (tuple, list, np.ndarray)):
        if isinstance(size[0], int):
            size_lower = size_upper = size
        elif isinstance(size[0], (tuple, list, np.ndarray)):
            size_lower = [s[0] for s in size]
            size_upper = [s[1] for s in size]
    else:
        raise ValueError(f"Size must be either int, sequence of int or sequence of sequences of ints, got {size}.")
    return sitk.ConstantPad(image, size_lower, size_upper, cval)


def centre_on_point(image, centre):
    pass


# def resize_by_cropping_or_padding(image, size, centre=None, cval=0.):
#     original_size = np.array(image.GetSize())
#     size = np.asarray(size)
#     centre = np.asarray(centre) if centre is not None else original_size / 2 # XXX is there any benefit to not using floor div here?

#     crop_dims = np.where(size < original_size)


def clip(image, lower, upper):
    pass


def window(image, window, level):
    pass


def mean(image, mask=None, labels=None):
    if mask is not None:
        pass
    pass

def var(image, mask=None, labels=None):
    if mask is not None:
        pass
    pass

def standard_scale(image, dataset_mean=0., dataset_var=1.):
    return (image - dataset_mean) / dataset_var
