from ..pipeline import Pipeline
from ..ops import Resample
from ..io import ImageDirectoryLoader, read_dicom_series, read_dicom_rtstruct


class RADCUREPipeline(Pipeline):
    def __init__(self, root_directory="/cluster/projects/radiomics/RADCURE_images/", spacing=(1., 1., 1.)):
        self.root_directory = root_directory
        self.image_loader = ImageDirectoryLoader(self.root_directory, index_by="parent", subdir_path="*/ImageSet_*", reader=read_dicom_series)
        self.structure_set_loader = ImageDirectoryLoader(self.root_directory, index_by="parent", subdir_path="*/structures", reader=read_dicom_rtstruct)
        self.resample = Resample(spacing=spacing)

    def process_one_case(self, key):
        image = self.image_loader[key]
        structure_set = self.structure_set_loader[key]
        image = self.resample(image)
        mask = structure_set.to_mask(image, roi_names="GTV")
        self.image_writer.add(key, image)
        self.mask_writer.add(key, mask)
