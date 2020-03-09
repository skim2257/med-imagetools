import os
import glob
import re
from typing import Optional
from collections import namedtuple
from itertools import chain

import numpy as np
import pandas as pd
import SimpleITK as sitk
from pydicom import dcmread
from pydicom.misc import is_dicom

from ..utils import image_to_array
from ..structureset import StructureSet
from ..utils.imageutils import image_to_array


def read_image(path):
    return sitk.ReadImage(path)


def read_numpy_array(path):
    return np.load(path)


def read_dicom_series(path: str,
                      recursive: bool = False,
                      series_id: Optional[str] = None) -> sitk.Image:
    """Read DICOM series as SimpleITK Image.

    Parameters
    ----------
    path
       Path to directory containing the DICOM series.

    recursive, optional
       Whether to recursively parse the input directory when searching for
       DICOM series,

    series_id, optional
       Specifies the DICOM series to load if multiple series are present in
       the directory. If None and multiple series are present, loads the first
       series found.


    Returns
    -------
    The loaded image.

    """
    reader = sitk.ImageSeriesReader()
    dicom_names = reader.GetGDCMSeriesFileNames(path,
                                                seriesID=series_id if series_id else "",
                                                recursive=recursive)
    reader.SetFileNames(dicom_names)
    return reader.Execute()


def read_dicom_rtstruct(path):
    return StructureSet.from_dicom_rtstruct(path)


def find_dicom_paths(root_path: str, yield_directories: bool = False) -> str:
    """Find DICOM file paths in the specified root directory file tree.

    Parameters
    ----------
    root_path
        Path to the root directory specifying the file hierarchy.

    yield_directories, optional
        Whether to yield paths to directories containing DICOM files
        or separately to each file (default).


    Yields
    ------
    The paths to DICOM files or DICOM-containing directories (if
    `yield_directories` is True).

    """
    # TODO add some filtering options
    for root, dirs, files in os.walk(root_path):
        if yield_directories:
            if any((is_dicom(os.path.join(root, f)) for f in files)):
                yield root
        else:
            for f in files:
                fpath = os.path.join(root, f)
                if is_dicom(fpath):
                    yield fpath