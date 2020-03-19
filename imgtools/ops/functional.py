import SimpleITK as sitk
import numpy as np

from typing import Sequence, Union, Tuple, Optional

INTERPOLATORS = {
    "linear": sitk.sitkLinear,
    "nearest": sitk.sitkNearestNeighbor,
    "bspline": sitk.sitkBSpline,
}


def resample(image: sitk.Image,
             spacing: Union[float, Sequence[float], np.ndarray],
             interpolation: str = "linear",
             anti_alias: bool = True,
             anti_alias_sigma: float = 2.,
             transform: sitk.Transform = None) -> sitk.Image:
    """Resample image to a given spacing, optionally applying a transformation.

    Parameters
    ----------
    image
        The image to be resampled.

    spacing
        The new image spacing. If float, assumes the same spacing in all directions.
        Alternatively, a sequence of floats can be passed to specify spacing along
        x, y and z dimensions. Passing 0 at any position will keep the original
        spacing along that dimension (useful for in-plane resampling).

    interpolation, optional
        The interpolation method to use. Valid options are:
        - "linear" for bi/trilinear interpolation (default)
        - "nearest" for nearest neighbour interpolation
        - "bspline" for order-3 b-spline interpolation

    anti_alias, optional
        Whether to smooth the image with a Gaussian kernel before resampling.
        Only used when downsampling, i.e. when `spacing < image.GetSpacing()`.
        This should be used to avoid aliasing artifacts.

    anti_alias_sigma, optional
        The standard deviation of the Gaussian kernel used for anti-aliasing.

    Returns
    -------
    sitk.Image
        The resampled image.
    """

    try:
        interpolator = INTERPOLATORS[interpolation]
    except KeyError:
        raise ValueError(
            f"interpolator must be one of {list(INTERPOLATORS.keys())}, got {interpolator}."
        )

    original_spacing = np.array(image.GetSpacing())
    original_size = np.array(image.GetSize())

    if isinstance(spacing, (float, int)):
        new_spacing = np.repeat(spacing,
                                len(original_spacing)).astype(np.float64)
    else:
        spacing = np.asarray(spacing)
        new_spacing = np.where(spacing == 0, original_spacing, spacing)
    new_size = np.floor(original_size * original_spacing / new_spacing).astype(
        np.int)

    rif = sitk.ResampleImageFilter()
    rif.SetOutputOrigin(image.GetOrigin())
    rif.SetOutputSpacing(new_spacing)
    rif.SetOutputDirection(image.GetDirection())
    rif.SetSize(new_size.tolist())

    if transform is not None:
        rif.SetTransform(transform)

    downsample = new_spacing > original_spacing
    if downsample.any() and anti_alias:
        sigma = np.where(downsample, anti_alias_sigma, 1e-11)
        image = sitk.SmoothingRecursiveGaussian(
            image, sigma)  # TODO implement better sigma computation

    rif.SetInterpolator(interpolator)
    resampled_image = rif.Execute(image)

    return resampled_image


def resize(image: sitk.Image,
           size: Union[int, Sequence[int], np.ndarray],
           anti_alias: bool = True,
           anti_alias_sigma: float = 2.,
           interpolation: str = "linear") -> sitk.Image:
    """Resize image to a given size by resampling coordinates.

    Parameters
    ----------
    image
        The image to be resize.

    size
        The new image size. If float, assumes the same size in all directions.
        Alternatively, a sequence of floats can be passed to specify size along
        x, y and z dimensions. Passing 0 at any position will keep the original
        size along that dimension.

    interpolation, optional
        The interpolation method to use. Valid options are:
        - "linear" for bi/trilinear interpolation (default)
        - "nearest" for nearest neighbour interpolation
        - "bspline" for order-3 b-spline interpolation

    anti_alias, optional
        Whether to smooth the image with a Gaussian kernel before resampling.
        Only used when downsampling, i.e. when `size < image.GetSize()`.
        This should be used to avoid aliasing artifacts.

    anti_alias_sigma, optional
        The standard deviation of the Gaussian kernel used for anti-aliasing.

    Returns
    -------
    sitk.Image
        The resized image.
    """

    original_size = np.array(image.GetSize())
    original_spacing = np.array(image.GetSpacing())

    if isinstance(size, (float, int)):
        new_size = np.repeat(size, len(original_size)).astype(np.float64)
    else:
        size = np.asarray(size)
        new_size = np.where(size == 0, original_size, size)

    new_spacing = original_spacing * original_size / new_size

    return resample(image,
                    new_spacing,
                    anti_alias=anti_alias,
                    anti_alias_sigma=anti_alias_sigma,
                    interpolation=interpolation)


def rotate(image: sitk.Image,
           rotation_centre: Sequence[float],
           angles: Sequence[float],
           interpolation: str = "linear") -> sitk.Image:
    """Rotate an image around a given centre.

    Parameters
    ----------
    image
        The image to rotate.

    rotation_centre
        The centre of rotation in image coordinates.

    angles 
        The angles of rotation around x, y and z axes.

    Returns
    -------
    sitk.Image
        The rotated image.
    """

    rotation_centre = image.TransformIndexToPhysicalPoint(rotation_centre)
    x_angle, y_angle, z_angle = angles

    rotation = sitk.Euler3DTransform(
        rotation_centre,
        x_angle,  # the angle of rotation around the x-axis, in radians -> coronal rotation
        y_angle,  # the angle of rotation around the y-axis, in radians -> saggittal rotation
        z_angle,  # the angle of rotation around the z-axis, in radians -> axial rotation
        (0., 0., 0.)  # optional translation (shift) of the image, here we don't want any translation
    )
    return resample(image,
                    spacing=image.GetSpacing(),
                    interpolation=interpolation,
                    transform=rotation)


def crop(image: sitk.Image,
         crop_centre: Sequence[float],
         size: Union[int, Sequence[int], np.ndarray]) -> sitk.Image:
    """Crop an image to the desired size around a given centre.

    Note that the cropped image might be smaller than size in a particular
    direction if the cropping window exceeds image boundaries.
    
    Parameters
    ----------
    image
        The image to crop.

    crop_centre
        The centre of the cropping window in image coordinates.

    size
        The size of the cropping window along each dimension in pixels. If
        float, assumes the same size in all directions. Alternatively, a
        sequence of floats can be passed to specify size along x, y and z
        dimensions. Passing 0 at any position will keep the original size along
        that dimension.

    Returns
    -------
    sitk.Image
        The cropped image.
    """
    crop_centre = np.asarray(crop_centre, dtype=np.float64)
    original_size = np.asarray(image.GetSize())

    if isinstance(size, int):
        size = np.array([size for _ in image.GetSize()])
    else:
        size = np.asarray(size) 
    
    if (crop_centre < 0).any() or (crop_centre > original_size).any():
        raise ValueError(
            f"Crop centre outside image boundaries. Image size = {original_size}, crop centre = {crop_centre}"
        )

    min_coords = np.clip(
        np.floor(crop_centre - size / 2).astype(np.int64), 0,
        original_size)
    min_coords = np.where(size == 0, 0, min_coords)

    max_coords = np.clip(
        np.floor(crop_centre + size / 2).astype(np.int64), 0,
        original_size)
    max_coords = np.where(size == 0, original_size, max_coords)

    min_x, min_y, min_z = min_coords
    max_x, max_y, max_z = max_coords

    return image[min_x:max_x, min_y:max_y, min_z:max_z]


# def constant_pad(image, size, cval=0.):
#     if isinstance(size, int):
#         size_lower = size_upper = [size for _ in image.GetSize()]
#     elif isinstance(size, (tuple, list, np.ndarray)):
#         if isinstance(size[0], int):
#             size_lower = size_upper = size
#         elif isinstance(size[0], (tuple, list, np.ndarray)):
#             size_lower = [s[0] for s in size]
#             size_upper = [s[1] for s in size]
#     else:
#         raise ValueError(
#             f"Size must be either int, sequence of int or sequence of sequences of ints, got {size}."
#         )
#     return sitk.ConstantPad(image, size_lower, size_upper, cval)


# def centre_on_point(image, centre):
#     pass


# def resize_by_cropping_or_padding(image, size, centre=None, cval=0.):
#     original_size = np.array(image.GetSize())
#     size = np.asarray(size)
#     centre = np.asarray(centre) if centre is not None else original_size / 2 # XXX is there any benefit to not using floor div here?

#     crop_dims = np.where(size < original_size)


def bounding_box(mask: sitk.Image, label: int = 1) -> tuple:
    """Find the axis-aligned bounding box of a region descriibed by a
    segmentation mask.

    Parameters
    ----------
    mask
        Segmentation mask describing the region of interest.

    label, optional
        Label to use when computing bounding box if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    tuple
        The bounding box location and size. For an N-dimensional image,
        the first N elements are the location of the bounding box and the next
        N elements describe the size along each dimension.
    """

    filter_ = sitk.LabelShapeStatisticsImageFilter()
    filter_.Execute(mask)
    return filter_.GetBoundingBox(label)


def centroid(mask: sitk.Image,
             label: int = 1,
             world_coordinates: bool = False) -> tuple:
    """Find the centroid of a labelled region specified by a segmentation mask.

    Parameters
    ----------
    mask
        Segmentation mask describing the region of interest.

    label, optional
        Label to use when computing the centroid if segmentation mask contains
        more than 1 labelled region.

    world_coordinates, optional
        If True, return centroid in world coordinates, otherwise in image
        (voxel) coordinates (default).

    Returns
    -------
    tuple
        The centroid coordinates.
    """
    filter_ = sitk.LabelShapeStatisticsImageFilter()
    filter_.Execute(mask)
    centroid_coords = filter_.GetCentroid(label)
    if not world_coordinates:
        centroid_coords = mask.TransformPhysicalPointToIndex(centroid_coords)
    return centroid_coords


def crop_to_mask_bounding_box(image: sitk.Image,
                              mask: sitk.Image,
                              margin: Union[int, Sequence[int], np.ndarray] = 0,
                              label: int = 1) -> Tuple[sitk.Image]:
    """Crop the image using the bounding box of a region of interest specified
    by a segmentation mask.

    Parameters
    ----------
    image
        The image to crop.

    mask
        Segmentation mask describing the region of interest.

    margin, optional
        A margin that will be added to each dimension when cropping. If int,
        add the same margin to each dimension. A sequence of ints can also be
        passed to specify the margin separately along each dimension.

    label, optional
        Label to use when computing the centroid if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    tuple of sitk.Image
        The cropped image and mask.
    """
    if isinstance(margin, Sequence):
        margin = np.asarray(margin)

    mask_bbox = np.array(bounding_box(mask, label=label))
    bbox_location, bbox_size = mask_bbox[:2], mask_bbox[2:]
    crop_centre = (bbox_location + bbox_size) / 2
    crop_size = bbox_size // 2 + margin

    image = crop(image, crop_centre, crop_size)
    mask = crop(mask, crop_centre, crop_size)

    return image, mask


def clip_intensity(image: sitk.Image,
                   lower: float,
                   upper: float):
    """Clip image gray level intensities to specified range.

    The gray level intensities in the resulting image will fall in the range
    [lower, upper].

    Parameters
    ----------
    image
        The intensity image to clip.

    lower
        The lower bound on gray level intensity. Voxels with lower intensity
        will be set to this value.

    upper 
        The upper bound on gray level intensity. Voxels with higer intensity
        will be set to this value.

    Returns
    -------
    sitk.Image
        The clipped intensity image.
    """
    return sitk.Clamp(image, image.GetPixelID(), lower, upper)


def window_intensity(image: sitk.Image,
                     window: float,
                     level: float) -> sitk.Image:
    """Restrict image gray level intensities to a given window and level.

    The gray level intensities in the resulting image will fall in the range
    [level - window / 2, level + window / 2]. 

    Parameters
    ----------
    image
        The intensity image to window.

    window 
        The width of the intensity window.

    level
        The mid-point of the intensity window.

    Returns
    -------
    sitk.Image
        The windowed intensity image.
    """
    lower = level - window / 2
    upper = level + window / 2
    return clip_intensity(image, lower, upper)


def mean(image: sitk.Image,
         mask: sitk.Image = None,
         label: int = None) -> float:
    """Compute the mean gray level intensity in an image.

    This function also supports computing the mean intensity in a specific
    region of interest if `mask` and `label` are passed.

    Parameters
    ----------
    image
        The image used to compute the mean.

    mask, optional
        Segmentation mask specifying a region of interest used in computation.
        Only voxels falling within the ROI will be considered. If None, use the
        whole image.

    label, optional
        Label to use when computing the mean if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    float
        The mean gray level intensity in the image or region.
    """
    if mask is not None:
        filter_ = sitk.LabelStatisticsImageFilter()
        filter_.Execute(image, mask)
        result = filter_.GetMean(label)
    else:
        filter_ = sitk.StatisticsImageFilter()
        filter_.Execute(image)
        result = filter_.GetMean()
    return result


def variance(image, mask=None, label=None):
    """Compute the variance of gray level intensities in an image.

    This function also supports computing the variance in a specific
    region of interest if `mask` and `label` are passed.

    Parameters
    ----------
    image
        The image used to compute the variance.

    mask, optional
        Segmentation mask specifying a region of interest used in computation.
        Only voxels falling within the ROI will be considered. If None, use the
        whole image.

    label, optional
        Label to use when computing the variance if segmentation mask contains
        more than 1 labelled region.

    Returns
    -------
    float
        The variance of gray level intensities in the image or region.
    """
    if mask is not None:
        filter_ = sitk.LabelStatisticsImageFilter()
        filter_.Execute(image, mask)
        result = filter_.GetVariance(label)
    else:
        filter_ = sitk.StatisticsImageFilter()
        filter_.Execute(image)
        result = filter_.GetVariance()
    return result


def standard_scale(image: sitk.Image,
                   mask: sitk.Image = None,
                   rescale_mean: float = None,
                   rescale_variance: float = None,
                   label: int = 1) -> sitk.Image:
    """Rescale image intensities by subtracting the mean and dividing by variance.

    If `rescale_mean` and `rescale_variance` are None, image mean and variance
    will be used, i.e. the resulting image intensities will have 0 mean and
    unit variance. Alternatively, a specific mean and variance can be passed to
    e.g. standardize a whole dataset of images. If a segmentation mask is passed,
    only the voxels falling within the mask will be considered when computing
    mean and variance. However, the whole image will still be normalized using
    the computed values.

    Parameters
    ----------
    image
        The image to rescale.

    mask, optional
        Segmentation mask specifying a region of interest used in computation.
        Only voxels falling within the ROI will be considered. If None, use the
        whole image.

    label, optional
        Label to use when computing the mean and variance if segmentation mask
        contains more than 1 labelled region.

    Returns
    -------
    sitk.Image
        The rescaled image.
    """
    if not rescale_mean or not rescale_variance:
        rescale_mean = mean(image, mask=mask, label=label)
        rescale_variance = variance(image, mask=mask, label=label)
    return (image - rescale_mean) / rescale_variance
