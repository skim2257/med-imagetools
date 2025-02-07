from argparse import ArgumentParser
import os, pathlib
import glob
import json

import pandas as pd
from pydicom import dcmread
from tqdm import tqdm

from joblib import Parallel, delayed

def crawl_one(folder):
    database = {}
    for path, _, _ in os.walk(folder):
        # find dicoms
        dicoms = glob.glob(pathlib.Path(path, "*.dcm").as_posix())

        # instance (slice) information
        for dcm in dicoms:
            try:
                meta = dcmread(dcm, force=True)
                patient  = str(meta.PatientID)
                study    = str(meta.StudyInstanceUID)
                series   = str(meta.SeriesInstanceUID)
                instance = str(meta.SOPInstanceUID)

                reference_ct, reference_rs, reference_pl = " ", " ", " "
                try: #RTSTRUCT
                    reference_ct = str(meta.ReferencedFrameOfReferenceSequence[0].RTReferencedStudySequence[0].RTReferencedSeriesSequence[0].SeriesInstanceUID)
                except: 
                    try: #RTDOSE
                        reference_rs = str(meta.ReferencedStructureSetSequence[0].ReferencedSOPInstanceUID)
                    except:
                        pass
                    try:
                        reference_ct = str(meta.ReferencedImageSequence[0].ReferencedSOPInstanceUID)
                    except:
                        pass
                    try:
                        reference_pl = str(meta.ReferencedRTPlanSequence[0].ReferencedSOPInstanceUID)
                    except:
                        pass
                
                try:
                    reference_frame = str(meta.FrameOfReferenceUID)
                except:
                    try:
                        reference_frame = str(meta.ReferencedFrameOfReferenceSequence[0].FrameOfReferenceUID)
                    except:
                        reference_frame = ""
        
                try:
                    study_description = str(meta.StudyDescription)
                except:
                    study_description = ""

                try:
                    series_description = str(meta.SeriesDescription)
                except:
                    series_description = ""

                if patient not in database:
                    database[patient] = {}
                if study not in database[patient]:
                    database[patient][study] = {'description': study_description}
                if series not in database[patient][study]:
                    parent, _ = os.path.split(folder)
                    rel_path = pathlib.Path(os.path.split(parent)[1], os.path.relpath(path, parent)).as_posix()
                    database[patient][study][series] = {'instances': [],
                                                        'instance_uid': instance,
                                                        'modality': meta.Modality,
                                                        'description': series_description,
                                                        'reference_ct': reference_ct,
                                                        'reference_rs': reference_rs,
                                                        'reference_pl': reference_pl,
                                                        'reference_frame': reference_frame,
                                                        'folder': rel_path}
                database[patient][study][series]['instances'].append(instance)
            except:
                pass
    
    return database

def to_df(database_dict):
    df = pd.DataFrame()
    for pat in database_dict:
        for study in database_dict[pat]:
            for series in database_dict[pat][study]:
                if series != 'description':
                    columns = ['patient_ID', 'study', 'study_description', 'series', 'series_description', 'modality', 'instances', 'instance_uid', 'reference_ct', 'reference_rs', 'reference_pl', 'reference_frame', 'folder']
                    values = [pat, study, database_dict[pat][study]['description'], series, database_dict[pat][study][series]['description'], database_dict[pat][study][series]['modality'], len(database_dict[pat][study][series]['instances']),
                    database_dict[pat][study][series]['instance_uid'], database_dict[pat][study][series]['reference_ct'], database_dict[pat][study][series]['reference_rs'], database_dict[pat][study][series]['reference_pl'],
                    database_dict[pat][study][series]['reference_frame'], database_dict[pat][study][series]['folder']]
                    df_add = pd.DataFrame([values], columns=columns)
                    df = pd.concat([df, df_add], ignore_index=True)
    return df

def crawl(top, 
          n_jobs: int = -1):
    #top is the input directory in the argument parser from autotest.py
    database_list = []
    folders = glob.glob(pathlib.Path(top, "*").as_posix())
    
    database_list = Parallel(n_jobs=n_jobs)(delayed(crawl_one)(pathlib.Path(top, folder).as_posix()) for folder in tqdm(folders))

    # convert list to dictionary
    database_dict = {}
    for db in database_list:
        for key in db:
            database_dict[key] = db[key]
    
    # save one level above imaging folders
    parent, dataset  = os.path.split(top)

    parent_imgtools = pathlib.Path(parent, ".imgtools").as_posix()

    if not os.path.exists(parent_imgtools):
        try:
            os.makedirs(parent_imgtools)
        except:
            pass
    
    # save as json
    with open(pathlib.Path(parent_imgtools, f'imgtools_{dataset}.json').as_posix(), 'w') as f:
        json.dump(database_dict, f, indent=4)
    
    # save as dataframe
    df = to_df(database_dict)
    df_path = pathlib.Path(parent_imgtools, f'imgtools_{dataset}.csv').as_posix()
    df.to_csv(df_path)
    
    return database_dict

if __name__ == "__main__":
    parser = ArgumentParser("Dataset DICOM Crawler")
    parser.add_argument("directory",
                         type=str,
                         help="Top-level directory of the dataset.")
    parser.add_argument("--n_jobs",
                         type=int,
                         default=16,
                         help="Number of parallel processes for multiprocessing.")

    args = parser.parse_args()
    db = crawl(args.directory, n_jobs=args.n_jobs)
    print("# patients:", len(db))
