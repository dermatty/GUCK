#!/home/stephan/.virtualenvs/cvp0/bin/python

import numpy as np
np.random.seed(1337)  # for reproducibility

import cv2, sys, os, glob, dill
from random import randint
import pymongo

img_rows = 128
img_cols = 128

CWD0 = os.getcwd()

# the data, shuffled and split between train and test sets
classifiction_path = "/media/nfs/NFS_Projekte/GIT/GUCK/data/photos/classification_photos"
os.chdir(classifiction_path)

class_dirs = [x for x in glob.glob("*/")]
classes = [x.split("/")[0] for x in class_dirs]
nb_classes = len(classes)

# scan dirs for no. of jpgs
nr0 = 0
for cd in class_dirs:
    full_class_dir = classifiction_path + "/" + cd
    os.chdir(full_class_dir)
    nr_photos = len(glob.glob("*.jpg"))
    nr0 += nr_photos

os.chdir(classifiction_path)
X_all = np.zeros((nr0, img_rows, img_cols, 1),dtype=np.uint8)
Y_all = np.zeros((nr0),dtype=np.uint8)

# read all data
print("Reading data from .jpg files in classification dir ...")
idx = 0
for cd in class_dirs:
    y = cd.split("/")[0]
    full_class_dir = classifiction_path + "/" + cd
    os.chdir(full_class_dir)
    for jpgfile in glob.glob("*.jpg"):
        img0 = cv2.cvtColor(cv2.imread(jpgfile),cv2.COLOR_BGR2GRAY)
        img = img0.reshape(img_rows, img_cols,1)
        X_all[idx,:] = img
        Y_all[idx] = int(y)
        idx += 1
        print("Dir:",full_class_dir,", processing img #", idx,"with label:",cd,"\r",end="")
    print("\n")

print("shuffling ...")
shufflelist = []
X_shuffle = np.zeros((nr0, img_rows, img_cols, 1),dtype=np.uint8)
Y_shuffle = np.zeros((nr0),dtype=np.uint8)
for l in range(nr0):
    i = randint(0,nr0-1)
    while i in shufflelist:
        i = randint(0,nr0-1)
    shufflelist.append(i)
    X_shuffle[l] = X_all[i]
    Y_shuffle[l] = Y_all[i]

os.chdir(CWD0)

fn = "/media/nfs/NFS_Projekte/GIT/GUCK/data/cnn/classification_raw_data.pickle"
print("writing file:", fn)
with open(fn, "wb") as f:
    dill.dump((X_shuffle, Y_shuffle), f)
f.close()

print("done")
