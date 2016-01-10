"""Preprocessing script.

Note, much of this was taken from: https://raw.githubusercontent.com/dmlc/mxnet/master/example/kaggle-ndsb2/Preprocessing.py
"""
import os
import csv
import sys
import random
import scipy
import numpy as np
import dicom
from skimage import io, transform

class MRIDataIterator(object):
    """ Iterates over the fMRI scans and returns batches of test and validation
    data. Needed to load into memory one batch at a time."""

    def __init__(self, frame_root_path = None, label_path = None, percent_validation = .8):
        """Walk the directory and randomly split the data"""
        if frame_root_path:
            self.frames = self.get_frames(frame_root_path)
        if label_path:
            self.labels = self.get_label_map(label_path)
        self.current_iter_position = 0
        self.PATIENT_RANGE_INCLUSIVE = (1,500)
        self.last_training_index = int(percent_validation * self.PATIENT_RANGE_INCLUSIVE[1])

    def get_frames(self, root_path):
       """Get path to all the frame in view SAX and contain complete frames"""
       ret = {}
       for root, _, files in os.walk(root_path):
           if len(files) == 0 or not files[0].endswith(".dcm") or root.find("sax") == -1:
               continue
           prefix = files[0].rsplit('-', 1)[0]
           data_index = int(root.rsplit('/', 3)[1])
           fileset = set(files)
           expected = ["%s-%04d.dcm" % (prefix, i + 1) for i in range(30)]
           if all(x in fileset for x in expected):
               if data_index in ret:
                   ret[data_index].append([root + "/" + x for x in expected])
               else:
                   ret[data_index] = [[root + "/" + x for x in expected]]

       return ret

    def one_hot(self, label):
        """
        Returns a 1-hot encoding of the label
        """
        return np.eye(600, dtype=np.int32)[int(label)]

    def get_label_map(self, fname):
       labelmap = {}
       fi = open(fname)
       fi.readline()
       for line in fi:
           arr = line.split(',')
           labelmap[int(arr[0])] = [float(x) for x in arr[1:]]
       return labelmap

    def preproc(self, img, size):
       """crop center and resize"""
       if img.shape[0] < img.shape[1]:
           img = img.T
       # we crop image from center
       short_egde = min(img.shape[:2])
       yy = int((img.shape[0] - short_egde) / 2)
       xx = int((img.shape[1] - short_egde) / 2)
       crop_img = img[yy : yy + short_egde, xx : xx + short_egde]
       # resize to 64, 64
       resized_img = transform.resize(crop_img, (size, size))
       resized_img *= 255
       return resized_img.astype("uint8")

    def has_more_training_data(self, index = None):
        if not index:
            index = self.current_iter_position
        return index <= self.last_training_index

    def has_more_validation_data(self, index):
        return index <= self.PATIENT_RANGE_INCLUSIVE[1]

    def retrieve_data_batch(self, index = None):
        """ Minibatched data retrieval of fMRI images, returns a numpy array
        of (num_sax_images x 30 x 64 x 64) and the equivalent label (arr, label)
        loaded into memory with the 30 being the channel related to fMRI slices
        and num_sax_images being the sequence images of the heart cycle
        to find systole and diastole"""
        if not self.labels or not self.frames:
            raise ValueError("Frames or labels not set")
        if not index:
            index = self.current_iter_position
            self.current_iter_position += 1

        if self.PATIENT_RANGE_INCLUSIVE[0] > index > self.PATIENT_RANGE_INCLUSIVE[1]:
            raise ValueError("Index out of bounds for data.")

        patient_frames = self.frames[index]
        data_array = np.zeros((len(patient_frames), 30, 64, 64))
        sax_index = 0
        for sax_set in patient_frames:
            data = []
            for path in sax_set:
                f = dicom.read_file(path)
                img = self.preproc(f.pixel_array.astype(float) / np.max(f.pixel_array), 64)
                data.append(img)
            data = np.array(data, dtype=np.int32)
            # data = data.reshape(data.size)
            data_array[sax_index][:][:][:] = data
            sax_index += 1

        # systole_repeated = np.zeros((len(patient_frames), 600), dtype=np.int32)
        # systole_repeated[:,:] = self.one_hot(self.labels[index][0])

        # diastole_repeated = np.zeros((len(patient_frames), 600), dtype=np.int32)
        # diastole_repeated[:,:] = self.one_hot(self.labels[index][1])

        return data_array, [ np.full(len(patient_frames), int(x), dtype=np.int32) for x in self.labels[index]]

    # TODO: modify this for writing the validation labels
    def write_label_csv(self, fname, frames, label_map):
       fo = open(fname, "w")
       for lst in frames:
           index = int(lst[0].split("/")[3])
           if label_map != None:
               fo.write(label_map[index])
           else:
               fo.write("%d,0,0\n" % index)
       fo.close()



# # Load the list of all the training frames, and shuffle them
# # Shuffle the training frames
# random.seed(10)
# train_frames = get_frames("./data/train")
# random.shuffle(train_frames)
#
# # Write the corresponding label information of each frame into file.
# write_label_csv("./train-label.csv", train_frames, get_label_map("./data/train.csv"))
# # write_label_csv("./validate-label.csv", validate_frames, None)
#
# # Dump the data of each frame into a CSV file, apply crop to 64 preprocessor
# train_lst = write_data_csv("./train-64x64-data.csv", train_frames, lambda x: crop_resize(x, 64))
# # valid_lst = write_data_csv("./validate-64x64-data.csv", validate_frames, lambda x: crop_resize(x, 64))
#
# # Generate local train/test split, which you could use to tune your model locally.
# train_index = np.loadtxt("./train-label.csv", delimiter=",")[:,0].astype("int")
# train_set, test_set = local_split(train_index)
# split_to_train = [x in train_set for x in train_index]
# split_csv("./train-label.csv", split_to_train, "./local_train-label.csv", "./local_test-label.csv")
# split_csv("./train-64x64-data.csv", split_to_train, "./local_train-64x64-data.csv", "./local_test-64x64-data.csv")