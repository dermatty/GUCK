#!/home/stephan/.virtualenvs/cvp0/bin/python

from __future__ import print_function
import numpy as np
import time
import keras
from keras.models import Sequential, Model
from keras.layers import Flatten, Dense, Dropout, Reshape, Permute, Activation, Input, merge
from keras.layers import Convolution2D, MaxPooling2D, ZeroPadding2D
from keras.utils import np_utils
import cv2
import os
import dill
import sys
from random import randint

np.random.seed(int(time.time()))


def show_images(nr, x, y):
    n0 = x.shape[0]
    for i in range(nr):
        idx = randint(0, n0 - 1)
        img = x[idx]
        label = y[idx]
        cv2.imshow("IMG", img)
        print(label, " / press <space> !")
        ch = cv2.waitKey(1) & 0xFF
        while ch != 32:
            ch = cv2.waitKey(1) & 0xFF


def VGG_16(input_shape, nb_classes, nb_ActivationNodes):
    model = Sequential()

    model.add(ZeroPadding2D((1, 1), input_shape=input_shape))
    model.add(Convolution2D(32, 3, 3, activation='relu', name='conv1_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(32, 3, 3, activation='relu', name='conv1_2'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(32, 3, 3, activation='relu', name='conv2_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(32, 3, 3, activation='relu', name='conv2_2'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv3_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv3_2'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv3_3'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv4_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv4_2'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv4_3'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(128, 3, 3, activation='relu', name='conv5_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(128, 3, 3, activation='relu', name='conv5_2'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(128, 3, 3, activation='relu', name='conv5_3'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(Flatten(name="flatten"))
    model.add(Dense(nb_ActivationNodes, activation='relu', name='dense_1'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_ActivationNodes, activation='relu', name='dense_2'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_classes, name='dense_3'))
    model.add(Activation("softmax", name="softmax"))
    return model


def CIFAR(input_shape, nb_classes, nb_ActivationNodes):
    model = Sequential()
    nb_filters = 32
    # size of pooling area for max pooling
    pool_size = (2, 2)
    # convolution kernel size
    kernel_size = (3, 3)
    model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1],
                            border_mode='valid', input_shape=input_shape))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1]))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Convolution2D(64, 3, 3, border_mode='same'))
    model.add(Activation('relu'))
    model.add(Convolution2D(64, 3, 3))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=(2, 2)))
    model.add(Dropout(0.25))

    model.add(Flatten())
    model.add(Dense(512))
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_classes))
    model.add(Activation('softmax'))
    return model


def CIFAR_medium(input_shape, nb_classes, nb_ActivationNodes):
    model = Sequential()
    nb_filters = 32
    # size of pooling area for max pooling
    pool_size = (2, 2)
    # convolution kernel size
    kernel_size = (5, 5)
    model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1],
                            border_mode='valid', input_shape=input_shape))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1]))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Convolution2D(nb_filters * 2, kernel_size[0], kernel_size[1], border_mode='same'))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters * 2, kernel_size[0], kernel_size[1]))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Convolution2D(nb_filters * 3, kernel_size[0], kernel_size[1], border_mode='same'))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters * 3, kernel_size[0], kernel_size[1], border_mode='same'))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Flatten())
    model.add(Dense(nb_ActivationNodes))
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_classes))
    model.add(Activation('softmax'))
    return model


def CIFAR_extended(input_shape, nb_classes, nb_ActivationNodes):
    model = Sequential()
    nb_filters = 32
    # size of pooling area for max pooling
    pool_size = (2, 2)
    # convolution kernel size
    kernel_size = (7, 7)
    model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1], border_mode='valid',
                            input_shape=input_shape))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters, kernel_size[0], kernel_size[1]))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Convolution2D(nb_filters * 2, kernel_size[0], kernel_size[1], border_mode='same'))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters * 2, kernel_size[0], kernel_size[1]))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Convolution2D(nb_filters * 4, kernel_size[0], kernel_size[1], border_mode='same'))
    model.add(Activation('relu'))
    model.add(Convolution2D(nb_filters * 4, kernel_size[0], kernel_size[1], border_mode='same'))
    model.add(Activation('relu'))
    model.add(MaxPooling2D(pool_size=pool_size))
    model.add(Dropout(0.25))

    model.add(Flatten())
    model.add(Dense(nb_ActivationNodes))
    model.add(Activation('relu'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_classes))
    model.add(Activation('softmax'))
    return model


def VGG_19(input_shape, nb_classes, nb_ActivationNodes):
    model = Sequential()

    model.add(ZeroPadding2D((1, 1), input_shape=input_shape))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv1_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(64, 3, 3, activation='relu', name='conv1_2'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(128, 3, 3, activation='relu', name='conv2_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(128, 3, 3, activation='relu', name='conv2_2'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(256, 3, 3, activation='relu', name='conv3_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(256, 3, 3, activation='relu', name='conv3_2'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(256, 3, 3, activation='relu', name='conv3_3'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(256, 3, 3, activation='relu', name='conv3_4'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv4_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv4_2'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv4_3'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv4_4'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv5_1'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv5_2'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv5_3'))
    model.add(ZeroPadding2D((1, 1)))
    model.add(Convolution2D(512, 3, 3, activation='relu', name='conv5_4'))
    model.add(MaxPooling2D((2, 2), strides=(2, 2)))

    model.add(Flatten())
    model.add(Dense(nb_ActivationNodes, activation='relu', name='dense_1'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_ActivationNodes, activation='relu', name='dense_2'))
    model.add(Dropout(0.5))
    model.add(Dense(nb_classes, name='dense_3'))
    model.add(Activation("softmax"))

    return model


CNN_MODEL = None
CNN_MODEL_LIST = []
while CNN_MODEL_LIST == []:
    print("CHOOSE MODEL:")
    print("  1 --> CIFAR (32 / 64 - 3 x 3)")
    print("  2 --> CIFAR_medium (32 / 64 / 96 - 5 x 5)")
    print("  3 --> CIFAR_extended (32 / 64 / 128 - 7 x 7")
    print("  5 --> all 3 CIFARS")
    print("  9 --> exit")
    ch = input()
    if ch == "1":
        CNN_MODEL_LIST = ["CIFAR"]
    elif ch == "2":
        CNN_MODEL_LIST = ["CIFAR_medium"]
    elif ch == "3":
        CNN_MODEL_LIST = ["CIFAR_extended"]
    elif ch == "5":
        CNN_MODEL_LIST = ["CIFAR", "CIFAR_medium", "CIFAR_extended"]
    elif ch == "9":
        sys.exit()

if len(CNN_MODEL_LIST) > 1:
    NB_EPOCH_LIST = [25, 30, 35]
else:
    nbe = 0
    while nbe < 1 or nbe > 100:
        nbe = int(input("Number of epochs (1 - 100): "))
    NB_EPOCH_LIST = [nbe]


batch_size = 64
nb_classes = 2
# 20 für VGG16, 40 für CIFAR

# input image dimensions
img_rows, img_cols = 128, 128

CWD0 = os.getcwd()

# the data, shuffled and split between train and test sets
fn = "/media/nfs/NFS_Projekte/GIT/GUCK/data/cnn/classification_raw_data.pickle"
print("Loading raw data from: " + fn)
with open(fn, "rb") as f:
    X, Y = dill.load(f)
f.close()
nr0 = X.shape[0]

# get testing data from shuffle list
nr_test = int(nr0/6)
x_test = X[0:nr_test]
y_test = Y[0:nr_test]

# get_trainig data
nr_train = nr0 - nr_test - 1
x_train = X[nr_test:]
y_train = Y[nr_test:]

# show_images(25,X_train, Y_train)

input_shape = (img_rows, img_cols, 1)

X_train = x_train.astype('float32')
X_test = x_test.astype('float32')
X_train /= 255
X_test /= 255
print('X_train shape:', X_train.shape)
print(X_train.shape[0], 'train samples')
print(X_test.shape[0], 'test samples')

# convert class vectors to binary class matrices
Y_train = np_utils.to_categorical(y_train, nb_classes)
Y_test = np_utils.to_categorical(y_test, nb_classes)

NB_ACTIVATIONS = 512
OPT = "ADADELTA"

if OPT == "ADAM":
    opt = keras.optimizers.Adam(lr=0.001, beta_1=0.9, beta_2=0.999,
                                epsilon=1e-08, decay=0.0)
elif OPT == "ADADELTA":
    opt = keras.optimizers.adadelta(lr=1.0, rho=0.95, epsilon=1e-08, decay=0.0)
elif OPT == "SGD":
    opt = keras.optimizers.SGD(lr=0.1, decay=1e-6, momentum=0.9, nesterov=True)
else:
    print("Wrong optimizer!")
    sys.exit()

for (CNN_MODEL, NB_EPOCH) in zip(CNN_MODEL_LIST, NB_EPOCH_LIST):
    if CNN_MODEL == "CIFAR_extended":
        model = CIFAR_extended(input_shape, nb_classes, NB_ACTIVATIONS)
    elif CNN_MODEL == "CIFAR":
        model = CIFAR(input_shape, nb_classes, NB_ACTIVATIONS)
    elif CNN_MODEL == "CIFAR_medium":
        model = CIFAR_medium(input_shape, nb_classes, NB_ACTIVATIONS)
    else:
        print("Please specify correct model!")
        sys.exit()
    model.compile(optimizer=opt, loss="categorical_crossentropy",
                  metrics=['accuracy'])
    print("-------------------------------------------------")
    print("Training Model: " + CNN_MODEL + "_" + OPT + " on " +
          str(NB_EPOCH) + " epochs!")
    print("-------------------------------------------------")
    model.fit(X_train, Y_train, batch_size=batch_size,
              nb_epoch=NB_EPOCH, verbose=1,
              validation_data=(X_test, Y_test))
    fn = "/media/nfs/NFS_Projekte/GIT/GUCK/data/cnn/guck_cnn_" + CNN_MODEL + "_" + OPT + ".h5"
    model.save(fn)
    score = model.evaluate(X_test, Y_test, verbose=0)
    print(score)
