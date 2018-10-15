#!/home/stephan/.virtualenvs/cvp0/bin/python

import sys
sys.path.append("../../lib")

import ephem
import guckmongo
from bson.objectid import ObjectId
import cv2
import execnet
from execnet.gateway_base import RemoteError
from random import randint
import socket
import struct
import paramiko
import urllib.request
import urllib.parse
import posix_ipc
import telepot
from threading import Thread
from guckthread import Detection
import logging
import logging.handlers
import os
import guckthread
import guckmsg
import datetime
import dill
import time
import threading
import numpy as np
import signal
import configparser
from Sunset import Sun
from git import Repo
import keras
import tensorflow as tf
from keras.utils import np_utils
# import keras_retinanet
from keras_retinanet import models
# from keras_retinanet.models.resnet import custom_objects
from keras_retinanet.utils.image import read_image_bgr, preprocess_image, resize_image


__author__ = "Stephan Untergrabner"
__license__ = "GPLv3"


def get_session():
    config = tf.ConfigProto()
    config.gpu_options.allow_growth = True
    return tf.Session(config=config)


def overlap_rects(r1, r2):
    x11, y11, x12, y12 = r1
    w = abs(x12 - x11)
    h = abs(y12 - y11)
    area1 = w * h
    x21, y21, x22, y22 = r2
    w = abs(x22 - x21)
    h = abs(y22 - y21)
    area2 = w * h
    x_overlap = max(0, min(x12, x22) - max(x11, x21))
    y_overlap = max(0, min(y12, y22) - max(y11, y21))
    overlapArea = x_overlap * y_overlap
    return overlapArea, overlapArea/area1, overlapArea/area2


keras.backend.tensorflow_backend.set_session(get_session())

# try to get config for DB
try:
    dbconfig = configparser.ConfigParser()
    dbconfig.read("../../data/mongo_default/mongo_url.cfg")
    dburl = dbconfig["CONFIG"]["DB_URL"].rstrip()
    dbname = dbconfig["CONFIG"]["DB_NAME"].rstrip()
    _DB = guckmongo.ConfigDB(dburl, dbname)
except Exception as e:
    print(str(e) + ": Cannot get config for mongoDB, exiting ...")
    sys.exit()

# get & set GUCK_HOME & VERSION
try:
        _guck_home = _DB.db_query("basic", "guck_home")
except Exception as e:
        print("Mongo DB Error(" + str(e) + "), quitting ...")
        sys.exit()
if _guck_home == -1:
        print("Mongo DB Error, quitting ...")
        sys.exit()
if _guck_home[-1] != "/":
        _guck_home += "/"
try:
    __version__ = str(Repo(_guck_home).active_branch)
    os.environ["GUCK_VERSION"] = __version__
except:
    __version__ = "current"
    os.environ["GUCK_VERSION"] = __version__
os.environ["GUCK_HOME"] = _guck_home

GUCK_HOME = os.environ["GUCK_HOME"]

# Init Logger
logger = logging.getLogger("guck")
logger.setLevel(logging.INFO)
fh = logging.FileHandler(GUCK_HOME + "log/guck_main.log", mode="w")
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)
logger.info("Initialized DB, setting $GUCK_HOME to '" + GUCK_HOME + "'")

format = struct.Struct('!I')

# Init semaphores
SEMAPHORE_NAME = "/gucksemaphore1"
SEMAPHORE = posix_ipc.Semaphore(SEMAPHORE_NAME, posix_ipc.O_CREAT)
SEMAPHORE.release()

SEM_CAM = posix_ipc.Semaphore("SEM_CAM", posix_ipc.O_CREAT)
SEM_CAM.release()


# CameraData: contains setup data of a given camera as given by config file
class CameraDataClass:
        def __init__(self, enable, channel, gateway, status, inputmode, videofile, recordfile, camurl, camname, hostip,
                     hostvenv, minarearect, haarpath, haarpath2, haarscale, hogscale, hogthresh, scanrate, ptzmode,
                     ptzright, ptzleft, ptzup, ptzdown, reboot, mog2sens):
            self.CHANNEL = channel
            self.GATEWAY = gateway

            self.ENABLE = enable

            self.INPUT_MODE = inputmode
            self.VIDEOFILE = videofile
            self.RECORDFILE = recordfile
            self.STATUS = status
            self.CAMURL = camurl
            self.CAMNAME = camname
            self.HOSTIP = hostip
            self.HOSTVENV = hostvenv

            self.MIN_AREA_RECT = minarearect
            self.HAAR_PATH = haarpath
            self.HAAR_PATH2 = haarpath2
            self.HAAR_SCALE = haarscale
            self.HOG_SCALE = hogscale
            self.HOG_THRESH = hogthresh
            self.SCANRATE = scanrate
            self.MOG2SENS = mog2sens

            self.PTZMODE = ptzmode
            self.PTZRIGHT = ptzright
            self.PTZLEFT = ptzleft
            self.PTZUP = ptzup
            self.PTZDOWN = ptzdown

            self.REBOOT = reboot

            self.DO_RECORD = True
            self.TSLIST = []
            self.OUTVIDEO = None

            self.AI_MODE = "cnn"

        def getall(self):
            ret = (self.INPUT_MODE, self.CAMNAME, self.CAMURL, self.VIDEOFILE, self.MIN_AREA_RECT, self.HAAR_PATH,
                   self.HAAR_PATH2, self.HAAR_SCALE, self.HOG_SCALE, self.HOG_THRESH, self.SCANRATE, self.MOG2SENS,
                   self.AI_MODE)
            return ret


# Camera2: Thread for processing data from guckthread
class Camera2(Thread):
        def __init__(self, channel, name, status, aimode0, cnnmodel0):
            Thread.__init__(self)
            self.daemon = True
            self.channel = channel
            self.outdata = []           # data sent to guckthread
            self.indata = []
            self.camstatus = status
            self.name = name
            self.aimode = aimode0
            self.cnnmodel = cnnmodel0
            self.objlist = []

        def set_objlist(self, o):
            global SEM_CAM
            SEM_CAM.acquire()
            self.objlist = o
            SEM_CAM.release()

        def set_outdata(self, od):
            global SEM_CAM
            SEM_CAM.acquire()
            self.outdata.append(od)
            if len(self.outdata) > 30:
                del self.outdata[0]
            SEM_CAM.release()

        def get_outdata(self):
            global SEM_CAM
            SEM_CAM.acquire()
            if len(self.outdata) > 0:
                ret = self.outdata.pop(0)
            else:
                ret = None
            SEM_CAM.release()
            return ret

        def set_status(self, cs):
            global SEM_CAM
            SEM_CAM.acquire()
            self.camstatus = cs
            SEM_CAM.release()

        def get_status(self):
            global SEM_CAM
            SEM_CAM.acquire()
            ret = self.camstatus
            SEM_CAM.release()
            return ret

        def get_indata(self):
            global SEM_CAM
            SEM_CAM.acquire()
            if len(self.indata) > 0:
                ret = self.indata.pop(0)
            else:
                ret = None
            SEM_CAM.release()
            return ret

        def set_indata(self, id):
            global SEM_CAM
            SEM_CAM.acquire()
            _, s1, _, s4 = id
            if s1 is None or s4 is None:
                self.indata.append(None)
            else:
                self.indata.append(id)
            if len(self.indata) > 30:
                del self.indata[0]
            SEM_CAM.release()

        def run(self):
            while True:
                od = self.get_outdata()
                if od is not None:
                    try:
                        a, b, c = od
                        od = (self.objlist, a, b, c)
                        self.channel.send(dill.dumps(od))
                    except Exception as e:
                        ermsg = "Cannot send data to channel" + self.name + ": " + str(e)
                        logger.error(ermsg)
                    try:
                        exp1 = self.channel.receive(3)
                        self.set_indata(dill.loads(exp1))
                    except Exception as e:
                        ermsg = "Cannot receive data from channel" + self.name + ": " + str(e)
                        logger.error(ermsg)
                time.sleep(0.01)


# GControl: main processing class, everything is an instance/member of this
class GControl:

    def __init__(self, _db):
        # configfile path
        self.DB = _db
        self.HCLIMIT = 1

        # nightmode
        # Pressbaum Koordinaten
        self.NIGHTMODE = False
        self.OEPHEM = ephem.Observer()
        self.OEPHEM.lat = self.DB.db_query("ephem", "lat")
        self.OEPHEM.long = self.DB.db_query("ephem", "long")
        self.SUN = ephem.Sun()
        # just for logging
        logger.info("Latitude: " + self.DB.db_query("ephem", "lat"))
        logger.info("Long: " + self.DB.db_query("ephem", "long"))
        sunset0 = ephem.localtime(self.OEPHEM.next_setting(self.SUN))
        logger.info("Sunset: " + str(sunset0.hour + sunset0.minute/60))
        sunrise0 = ephem.localtime(self.OEPHEM.next_rising(self.SUN))
        logger.info("Sunrise: " + str(sunrise0.hour + sunrise0.minute/60))

        # telegram
        self.DO_TELEGRAM = self.DB.db_query("telegram", "do_telegram")
        self.TELEGRAM_MODE = self.DB.db_query("telegram", "mode")
        self.TELEGRAM_TOKEN = self.DB.db_query("telegram", "token")
        self.TELEGRAM_CHATID = [int(x) for x in self.DB.db_query("telegram", "chatidlist")]
        self.MAXT_TELEGRAM = self.DB.db_query("telegram", "maxt")
        self.NO_CHATIDS = len(self.TELEGRAM_CHATID)
        self.LASTTELEGRAM = None

        # basic + heartbeat
        self.DO_LOGFPS = self.DB.db_query("basic", "do_logfps")
        self.DO_CRIT = self.DB.db_query("basic", "warn_on_status")
        self.DO_HEARTBEAT = self.DB.db_query("basic", "do_heartbeat")
        self.SHOW_FRAMES = self.DB.db_query("basic", "show_frames")
        self.MAXT_HEARTBEAT = self.DB.db_query("basic", "maxt_heartbeat")
        self.LASTHEARTBEAT = None
        self.HEARTBEAT_DEST = self.DB.db_query("basic", "heartbeat_dest")
        self.LASTCRIT = None
        self.LASTPROC = None

        # ftp
        self.DO_FTP = self.DB.db_query("ftp", "enable")
        self.FTP_SERVER_URL = self.DB.db_query("ftp", "server_url")
        self.FTP_USER = self.DB.db_query("ftp", "user")
        self.FTP_PASSWORD = self.DB.db_query("ftp", "password")
        self.FTP_DIR = self.DB.db_query("ftp", "dir")
        self.FTP_SET_PASSIVE = self.DB.db_query("ftp", "set_passive")
        self.FTP_MAXT = self.DB.db_query("ftp", "maxt")

        # mail
        self.DO_MAIL = self.DB.db_query("mail", "enable")
        self.MAIL_FROM = self.DB.db_query("mail", "from")
        self.MAIL_TO = self.DB.db_query("mail", "to")
        self.MAIL_USER = self.DB.db_query("mail", "user")
        self.MAIL_PASSWORD = self.DB.db_query("mail", "password")
        self.SMTPSERVER = self.DB.db_query("mail", "server")
        self.SMTPPORT = self.DB.db_query("mail", "smtport")
        self.MAXT_MAIL = self.DB.db_query("mail", "maxt")
        self.MAIL_ONLYTEXT = self.DB.db_query("mail", "only_text")
        self.LASTMAIL = None
        self.MAIL = None
        if self.DO_MAIL:
            logger.info("Starting STMTP server ...")
            self.MAIL = guckmsg.SMTPServer(self.MAIL_FROM, self.MAIL_TO, self.SMTPSERVER, self.SMTPPORT, self.MAIL_USER,
                                           self.MAIL_PASSWORD)
            if not self.MAIL.MAILOK:
                logger.warning("Mail credentials wrong or smtp server down or some other bs with mail ...")
                self.MAIL = None
                self.DO_MAIL = False
        else:
            self.MAIL = None

        # sms
        self.DO_SMS = self.DB.db_query("sms", "enable")
        self.SMS_USER = self.DB.db_query("sms", "user")
        self.SMS_HASHCODE = self.DB.db_query("sms", "hashcode")
        self.SMS_SENDER = self.DB.db_query("sms", "sender")
        self.SMS_DESTNUMBER = self.DB.db_query("sms", "destnumber")
        self.SMS_MAXTSMS = self.DB.db_query("sms", "maxt")
        self.LASTSMS = None

        # check heartbeat vs mail / telegram
        if self.DO_HEARTBEAT and self.HEARTBEAT_DEST == "mail" and not self.DO_MAIL:
            logger.warning("You chose mail for heartbeat but mail is disabled. Switching off heartbeat ...")
            self.DO_HEARTBEAT = False
        elif self.DO_HEARTBEAT and self.HEARTBEAT_DEST == "telegram" and not self.DO_TELEGRAM:
            logger.warning("You chose Telegram for hearbeat but Telegram is disabled. Switching off heartbeat ...")
            self.DO_HEARTBEAT = False

        # photo
        self.DO_PHOTO = self.DB.db_query("photo", "enable")
        self.DO_AI_PHOTO = self.DB.db_query("photo", "enable_aiphoto")
        self.APHOTO_DIR = os.environ["GUCK_HOME"] + self.DB.db_query("photo", "aphoto_dir")
        self.AIPHOTO_DIR = os.environ["GUCK_HOME"] + self.DB.db_query("photo", "aiphoto_dir")
        self.AIPHOTO_DIR_NEG = os.environ["GUCK_HOME"] + self.DB.db_query("photo", "aiphoto_dir_neg")
        self.MAXT_DETECTPHOTO = self.DB.db_query("photo", "maxt")
        self.LASTPHOTO = None
        self.PHOTO_CUTOFF = self.DB.db_query("photo", "cutoff")
        self.PHOTO_CUTOFF_LEN = self.DB.db_query("photo", "cutoff_len")

        # AI
        self.AI_MODE = "cnn"
        self.CNN_PATH = os.environ["GUCK_HOME"] + self.DB.db_query("ai", "cnn_path")
        self.CNN_PATH2 = os.environ["GUCK_HOME"] + self.DB.db_query("ai", "cnn_path2")
        self.CNN_PATH3 = os.environ["GUCK_HOME"] + self.DB.db_query("ai", "cnn_path3")
        self.CNNMODEL = None
        self.CNNMODEL2 = None
        self.CNNMODEL3 = None
        self.AI_SENS = self.DB.db_query("ai", "ai_sens")
        thaarpath = self.HAAR_PATH = os.environ["GUCK_HOME"] + self.DB.db_query("ai", "haar_path")
        thaarpath2 = self.HAAR_PATH2 = os.environ["GUCK_HOME"] + self.DB.db_query("ai", "haar_path2")
        self.LASTAIPHOTO = None
        self.AIC = None
        self.AIDATA = []
        self.AI = None
        self.CPUHOG = cv2.HOGDescriptor()
        self.CPUHOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        try:
            self.CNNMODEL = keras.models.load_model(self.CNN_PATH)
            self.CNNMODEL2 = keras.models.load_model(self.CNN_PATH2)
            self.CNNMODEL3 = keras.models.load_model(self.CNN_PATH3)
            logger.info("Created Keras CNN model for people detection")
        except Exception as e:
            logger.warning(str(e) + ": cannot load CNN model, applying fallback to CV2 GPU, exiting ...")
            sys.exit()
        self.RETINA_PATH = os.environ["GUCK_HOME"] + "data/cnn/resnet50_coco_best_v2.1.0.h5"
        try:
            self.RETINAMODEL = models.load_model(self.RETINA_PATH, backbone_name='resnet50')
            # self.RETINAMODEL = keras.models.load_model(self.RETINA_PATH, custom_objects=custom_objects)
            logger.info("Created Keras Retina model for people detection")
        except Exception as e:
            logger.warning(str(e) + ": cannot load retina model, setting it to None!")
            self.RETINAMODEL = None
            sys.exit()
        # cameras
        self.PTZ = {}
        self.REBOOT = {}
        self.MOGSENS = {}
        self.DETECTIONDICT = {}
        self.CAMERADATA = []
        self.VIDEO_INPUT = {}
        cursor = self.DB.db_getall("cameras")
        i = 0
        for cn in cursor:
            tenable = cn["enable"]
            if tenable:
                tchannel = "N/A"
                tgateway = "N/A"
                tstatus = "N/A"
                tinputmode = "camera"   # hardcoded: change to "video" for testing
                tvideofile = os.environ["GUCK_HOME"] + cn["videofile"]
                trecordfile = os.environ["GUCK_HOME"] + cn["recordfile"]
                tcamurl = cn["url"]
                tcamname = cn["name"]
                thostip = cn["host_ip"]
                thostvenv = cn["host_venv"]
                tminarearect = int(cn["min_area_rect"])
                thaarscale = float(cn["haarscale"])
                thogscale = float(cn["hog_scale"])
                thogthresh = float(cn["hog_thresh"])
                tscanrate = int(cn["scanrate"])
                treboot = cn["reboot"]
                tmog2sens = int(cn["mog2_sensitivity"])
                self.MOGSENS[i] = tmog2sens
                self.REBOOT[i] = treboot
                tptzm = cn["ptz_mode"]
                tptzr = cn["ptz_mode"]
                tptzl = cn["ptz_mode"]
                tptzu = cn["ptz_mode"]
                tptzd = cn["ptz_mode"]
                self.PTZ[i] = (tptzm, tptzr, tptzl, tptzu, tptzd)
                try:
                    self.CAMERADATA.append(CameraDataClass(tenable, tchannel, tgateway, tstatus, tinputmode,
                                                           tvideofile, trecordfile, tcamurl, tcamname,
                                                           thostip, thostvenv, tminarearect, thaarpath, thaarpath2,
                                                           thaarscale, thogscale, thogthresh, tscanrate, tptzm,
                                                           tptzr, tptzl, tptzu, tptzd, treboot, tmog2sens))
                except:
                    logger.error("Wrong keys/data for camera" + str(i + 1) + ", exiting ...")
                    sys.exit()
                i += 1
        self.NR_CAMERAS = i - 1

        # init pyzmq server for ssh remote query ("gq")

        shm_initdata = self.PTZ, self.REBOOT, self.MOGSENS
        self.SSHSERVER = guckmsg.SSHServer(False, shm_initdata, threading.Lock())

        # init WastAlarmServer
        self.WAS = guckmsg.WastlAlarmServer(threading.Lock())

        # init telegram
        if self.DO_TELEGRAM:
            logger.info("Initializing Telegram ...")
            try:
                self.TELEGRAMBOT = telepot.Bot(self.TELEGRAM_TOKEN)
            except Exception as e:
                logger.error(e)
                self.DO_TELEGRAM = False
                self.TELEGRAMBOT = None
                logger.info("Please initiate telegram chat with your alarmbot!")

        # send thread
        logger.info("Initializing sendthread ...")
        sd_1 = None
        sd_2 = None
        sd_3 = None
        sd_4 = None
        sd_5 = None
        sd_6 = None     # FTP - Tuple
        if self.DO_MAIL:
            sd_1 = self.MAIL.SMTPSERVER
            sd_2 = self.MAIL.MAIL_FROM
            sd_3 = self.MAIL.MAIL_TO
        if self.DO_TELEGRAM:
            sd_4 = self.TELEGRAMBOT
            sd_5 = self.TELEGRAM_CHATID
        if self.DO_FTP:
            sd_6 = self.FTP_SERVER_URL, self.FTP_USER, self.FTP_PASSWORD, self.FTP_DIR, self.FTP_SET_PASSIVE

        if self.DO_TELEGRAM or self.DO_MAIL or self.DO_FTP:
            self.SENDMSG = guckmsg.MsgSendThread(sd_1, sd_2, sd_3, sd_4, sd_5, sd_6)
            self.SENDMSG.start()
        if self.DO_FTP:
            if not self.SENDMSG.FTP.FTPOK:
                self.DO_FTP = None
                logger.warning("Cannot login to FTP server, disabling FTP!")
            else:
                logger.info("Login to FTP successfull")

    def setNightMode(self):
        sunset0 = ephem.localtime(self.OEPHEM.next_setting(self.SUN))
        sunset = sunset0.hour + sunset0.minute/60
        sunrise0 = ephem.localtime(self.OEPHEM.next_rising(self.SUN))
        sunrise = sunrise0.hour + sunrise0.minute/60
        n0 = datetime.datetime.now()
        timedec = n0.hour + n0.minute/60
        if timedec > sunset and not self.NIGHTMODE:
            self.NIGHTMODE = True
            self.HCLIMIT = 1
            logger.info("Night comes, switching to Night Mode ...")
        if timedec > sunrise and timedec < sunset and self.NIGHTMODE:
            self.NIGHTMODE = False
            if self.CNNMODEL == "cnn":
                self.HCLIMIT = 1
            logger.info("Day comes, turning off Night Mode ...")
        self.SSHSERVER.set_hclimit(self.HCLIMIT)
        self.SSHSERVER.set_nightmode(self.NIGHTMODE)

    def get_cnn_classification(self, frame, objlist):
        objlist_ret = []
        if self.AI_MODE == "cnn":
            YMAX0, XMAX0 = frame.shape[:2]
            for o in objlist:
                o_ret = o
                id, rect, class_ai, class_ai_lt = o
                if time.time() - class_ai_lt >= 2:
                    try:
                        frame_faktor = 0.60 + (self.AI_SENS-10)*0.05    # 0.10 ... 0.35 ... 0.6
                        x, y, w, h = rect
                        x0 = int(max(0, x - w * frame_faktor))
                        y0 = int(max(0, y - h * frame_faktor))
                        w0 = int(min(XMAX0,  x + w + w * frame_faktor)) - x0
                        h0 = int(min(YMAX0, y + h + h * frame_faktor)) - y0
                        frame_c = frame[y0:y0+h0, x0:x0+w0]
                        x = cv2.cvtColor(frame_c, cv2.COLOR_BGR2GRAY)
                        x = cv2.resize(x, (128, 128))
                        X = x.reshape(x.shape[0], x.shape[1], 1)
                        X = X.astype('float32')
                        X /= 255
                        img = np.expand_dims(X, axis=0)
                        logger.info("---- CNN classification ----")
                        pred = self.CNNMODEL.predict(img)
                        max_pred = np.argmax(pred)
                        prob1_human = pred[0][1]
                        prob1_nothuman = pred[0][0]
                        prob1_faktor = 0.999 - self.AI_SENS * 0.001
                        classified = False
                        # FIRST: double check positives
                        # if CNN1 sufficient, test it also against second model
                        if self.NIGHTMODE:
                            pred2 = self.CNNMODEL2.predict(img)
                            max_pred2 = np.argmax(pred2)
                            prob2_human = pred2[0][1]
                            pred3 = self.CNNMODEL3.predict(img)
                            max_pred3 = np.argmax(pred3)
                            prob3_human = pred3[0][1]
                            if max_pred == 1 or max_pred2 == 1 or max_pred3 == 1:
                                logger.info("Night pass: Detected human with prob " + str(prob1_human) + " / " +
                                            str(prob2_human) + " / " + str(prob3_human) + "!")
                                classified = True
                        else:
                            if prob1_human > prob1_nothuman and prob1_human >= prob1_faktor:
                                logger.info("1st pass: SUFFICIENT with prob " + str(prob1_human) + "vs. threshold "
                                            + str(prob1_faktor) + ", performing 2nd pass ...")
                                pred2 = self.CNNMODEL2.predict(img)
                                prob2_human = pred2[0][1]
                                prob2_nothuman = pred2[0][0]
                                pred3 = self.CNNMODEL3.predict(img)
                                prob3_human = pred3[0][1]
                                prob3_nothuman = pred3[0][0]
                                prob2_faktor = 0.99 - (self.AI_SENS) * 0.03
                                prob3_faktor = 0.99 - self.AI_SENS * 0.03
                                # check if with CNN2 also above threshhold
                                if (prob2_human > prob2_nothuman and prob2_human > prob2_faktor) or \
                                   (prob3_human > prob3_nothuman and prob3_human > prob3_faktor):
                                    logger.info("2nd pass: CLASSIFIED as human with prob " + str(prob2_human) + "vs. threshold "
                                                + str(prob2_faktor))
                                    classified = True
                                else:
                                    logger.info("2nd pass: NOT SUFFICIENT as human" + str(prob3_human) + "vs. threshold "
                                                + str(prob3_faktor))
                            # SECOND: triple check weak positives -> has to be confirmed by at least another model
                            else:
                                if prob1_human > prob1_nothuman and prob1_human < prob1_faktor:
                                    logger.info("1st pass: WEAKLY NOT SUFFICIENT with prob " + str(prob1_human) +
                                                "vs. threshold " + str(prob1_faktor) +
                                                ", now performing checks vs. model 2 and 3 ...")
                                    # model 2 forecast
                                    pred2 = self.CNNMODEL2.predict(img)
                                    prob2_human = pred2[0][1]
                                    prob2_nothuman = pred2[0][0]
                                    prob2_faktor = 0.99 - (self.AI_SENS) * 0.001
                                    # model 3 forecast
                                    pred3 = self.CNNMODEL3.predict(img)
                                    prob3_human = pred3[0][1]
                                    prob3_nothuman = pred3[0][0]
                                    prob3_faktor = 0.99 - self.AI_SENS * 0.001
                                    if (prob2_human > prob2_nothuman and prob2_human > prob2_faktor) or \
                                            (prob3_human > prob3_nothuman and prob3_human > prob3_faktor):
                                        logger.info("2nd pass: CLASSIFIED as human with prob. " + str(prob2_human) + "/" +
                                                    str(prob3_human) + " vs. threshold of " + str(prob2_faktor) + "/" +
                                                    str(prob3_faktor))
                                        classified = True
                                    else:
                                        logger.info("2nd pass: NOT SUFFICIENT with prob. " + str(prob2_human) + "/" +
                                                    str(prob3_human) + " vs. threshold of " + str(prob2_faktor) + "/" +
                                                    str(prob3_faktor))
                                else:
                                    logger.info("1st pass: NOT SUFFICIENT with prob " + str(prob1_human) + "vs. threshold "
                                                + str(prob1_faktor))
                        if classified:
                            found = True
                            if self.RETINAMODEL:
                                image = preprocess_image(frame)
                                image, scale = resize_image(image)
                                pred_boxes, pred_scores, pred_labels = self.RETINAMODEL.predict_on_batch(np.expand_dims(image, axis=0))
                                # print("--> predicted!")
                                pred_boxes /= scale
                                found = False
                                for box, score, label in zip(pred_boxes[0], pred_scores[0], pred_labels[0]):
                                    # print("--> ", label, score)
                                    if label != 0 or score < 0.5:
                                        continue
                                    b = box.astype(int)
                                    r1 = (b[0], b[1], b[2], b[3])
                                    x, y, w, h = rect
                                    r2 = (x, y, x + w, y + h)
                                    overlapArea, ratio1, ratio2 = overlap_rects(r1, r2)
                                    if (ratio1 > 0.70 or ratio2 > 0.70):
                                        # print(" Human detected with score " + str(score) + " and overlap " + str(ratio1) + " / " + str(ratio2))
                                        logger.info(" Human detected with score " + str(score) + " and overlap " + str(ratio1) + " / " + str(ratio2))
                                        found = True
                                        break
                            if found:
                                class_ai_lt = time.time()
                                class_ai += 1
                                logger.info("!! CLASSIFIED !!")
                        else:
                            class_ai = max(0, class_ai - 0.15)
                            logger.info("## not classified ##")
                        o_ret = (id, rect, class_ai, class_ai_lt)

                    except Exception as e:
                        logger.warning("CNN model: cannot classify error: " + str(e))
                objlist_ret.append(o_ret)
        else:
            objlist_ret = objlist
        return objlist_ret

    def startupcamthread(self, idx=-1):
        if idx == -1:
            ri = range(len(self.CAMERADATA))
        else:
            ri = range(idx, idx+1)
        for i in ri:
            fourcc = cv2.VideoWriter_fourcc('X', 'V', 'I', 'D')
            # wait for caption
            ret = False
            for jj in range(10):
                cap = cv2.VideoCapture(self.CAMERADATA[i].CAMURL)
                ret, frame = cap.read()
                if ret:
                    ymax, xmax = frame.shape[:2]
                    break
            if not ret:
                xmax = 640
                ymax = 352
            logger.info("Camera " + str(i) + ": resolution set to " + str(xmax) + "x" + str(ymax))
            self.CAMERADATA[i].OUTVIDEO = cv2.VideoWriter(self.CAMERADATA[i].RECORDFILE, fourcc, 20.0, (xmax, ymax))
            if not self.CAMERADATA[i].ENABLE:
                self.CAMERADATA[i].STATUS = 0
                continue
            bhost = self.CAMERADATA[i].HOSTIP
            benv = self.CAMERADATA[i].HOSTVENV
            if bhost == "localhost":
                bstr = "popen//python=" + benv
            else:
                bstr = "ssh=" + bhost + "//python=" + benv
            msg = "Starting up process " + str(i+1) + " @ " + bstr + " ... "
            logger.info(msg)
            try:
                self.CAMERADATA[i].GATEWAY = execnet.makegateway(bstr)
                self.CAMERADATA[i].CHANNEL = self.CAMERADATA[i].GATEWAY.remote_exec(guckthread)
                logger.info("done!")
                self.CAMERADATA[i].STATUS = 1
            except:
                logger.error("Failed!")
                self.CAMERADATA[i].STATUS = 0
                self.CAMERADATA[i].ENABLE = False
            i += 1
        return

    def getcamthreadstates(self, targetstate):
        return [i for i in range(len(self.CAMERADATA)) if self.CAMERADATA[i].STATUS == targetstate]

    def restartcamthread(self, idx0, retry=3):
        if idx0 == -1:
            ri = range(len(self.CAMERADATA))
        else:
            ri = range(idx0, idx0+1)
        alloklist = []
        for i in ri:
            try:
                self.CAMERADATA[i].GATEWAY.exit()
                self.CAMERADATA[i].OUTVIDEO.release()
            except Exception as e:
                logger.warning("Cannot exit bridge gateway: " + str(e))
            j = 1
            allok = False
            while j <= retry and not allok:
                self.startupcamthread(idx=i)
                if self.CAMERADATA[i].STATUS != 1:
                    logger.warning("Bridge " + str(i) + " startup failed!")
                    logger.info("Will try again ...")
                    allok = False
                else:
                    self.initcamthread(idx=i)
                    if self.CAMERADATA[i].STATUS != 2:
                        logger.warning("Handshake with bridge " + str(i) + " failed")
                        logger.info("Will try again ...")
                        allok = False
                    else:
                        allok = True
                j += 1
            alloklist.append(allok)
        for ao in alloklist:
            if not ao:
                return False
        return True

    def initcamthread(self, idx=-1):
        if idx == -1:
            ri = range(len(self.CAMERADATA))
        else:
            ri = range(idx, idx+1)
        for i in ri:
            if not self.CAMERADATA[i].ENABLE:
                continue
            ch = self.CAMERADATA[i].CHANNEL
            bd = dill.dumps(self.CAMERADATA[i].getall())
            try:
                ch.send(bd)
                result = ch.receive()
                logger.info(result)
                if result == self.CAMERADATA[i].CAMNAME + ":#hostok":
                    self.CAMERADATA[i].STATUS = 2
                    ch.send("#start!")
                else:
                    logger.warning(self.CAMERADATA[i].CAMNAME + ": Camera thread handshake fail!")
                    self.CAMERADATA[i].STATUS = 0
                    self.CAMERADATA[i].ENABLE = False
            except:
                logger.warning(self.CAMERADATA[i].CAMNAME + ": Camera thread handshake fail!")
                self.CAMERADATA[i].STATUS = 0
                self.CAMERADATA[i].ENABLE = False

    def interpret_status(self, statuscode):
        ret = None
        if statuscode == 2:
            ret = "Running ..."
        elif statuscode == 1:
            ret = "Started up successfully, init pending!"
        else:
            ret = "Problem here!"
        return ret

    def adaptaiframe(self, frame0_orig, c, dxy):
        ys, xs, _ = np.shape(frame0_orig)
        x, y, w, h = c
        xr = x + w + w * dxy
        yu = y + h + h * dxy
        x = max(0, x - dxy*w)
        y = max(0, y - dxy*h)
        x1 = min(xs, xr)
        y1 = min(ys, yu)
        w = x1 - x
        h = y1 - y
        retframe = frame0_orig[y:y+h, x:x+w].copy()
        return retframe

    def siginthandler(self, signum, frame):
        self.shutdown()
        sys.exit()

    def shutdown(self):
        if self.DO_FTP:
            try:
                self.FTP.FTPC.quit()
            except:
                pass
        if self.DO_MAIL:
            self.SENDMSG.sendtext("smtp", "GUCK - Shutdown", "Shutting down guck ...", None)
            self.MAIL.close()
        if self.DO_TELEGRAM:
            self.SENDMSG.sendtext("telegram", None, "Shutting down, byebye ...", None)
        logger.info("Shutting down gateways ...")
        for i in range(len(self.CAMERADATA)):
            try:
                self.CAMERADATA[i].GATEWAY.exit()
            except Exception as e:
                logger.warning("An error occurred in thread shut down ...")
            try:
                self.CAMERADATA[i].OUTVIDEO.release()
            except Exception as e:
                logger.warning("An error occurred in video shut down ...")
                pass
        try:
            os.system("killall -9 python")
        except:
            pass
        logger.info("System shut down!")
        cv2.destroyAllWindows()
        return

    # -----------------------------------------------------------------------------------------------------------------
    # ---   guck main loop
    # -----------------------------------------------------------------------------------------------------------------

    # @profile
    def framereadloop(self):

        global SEMA

        signal.signal(signal.SIGINT, self.siginthandler)

        tt0 = time.time()

        self.LASTTELEGRAM = tt0
        self.LASTPHOTO = tt0
        self.LASTHEARTBEAT = tt0
        self.LASTMAIL = tt0
        self.LASTSMS = tt0
        self.LASTFTP = tt0
        self.LASTPROC = tt0
        self.LASTLOG = tt0
        self.LASTAIPHOTO = tt0
        self.LASTCRIT = tt0
        self.LASTWASTL = tt0

        self.WAS.start()

        # start ssh server
        logger.info("Starting SSH server ...")
        self.SSHSERVER.start()
        ret = self.SSHSERVER.set_tgmode(self.TELEGRAM_MODE)
        logger.info("Set TG Mode to " + str(ret) + "/" + str(self.TELEGRAM_MODE))
        self.SSHSERVER.set_aimode(self.AI_MODE)
        self.SSHSERVER.set_aisens(self.AI_SENS)
        self.SSHSERVER.set_nightmode(self.NIGHTMODE)

        if self.DO_MAIL:
            self.SENDMSG.sendtext("smtp", "GUCK - Started", "GUCK home surveillance started!", None)

        if self.DO_TELEGRAM and self.TELEGRAMBOT:
            self.SENDMSG.sendtext("telegram", None, "GUCK home surveillance started!", None)

        logger.info("Starting up local threads for cameras")
        camthread = []
        for i in range(len(self.CAMERADATA)):
            camthread.append(Camera2(self.CAMERADATA[i].CHANNEL, self.CAMERADATA[i].CAMNAME, 2, self.AI_MODE, self.CNNMODEL))
            if self.CAMERADATA[i].ENABLE:
                camthread[i].start()
            self.SSHSERVER.set_mogsens(i, self.CAMERADATA[i].MOG2SENS)

        shmlist = [[] for i in range(len(self.CAMERADATA))]
        logger.info("Entering main loop")

        if self.NIGHTMODE:
            self.HCLIMIT = 1
        self.SSHSERVER.set_hclimit(self.HCLIMIT)

        while True:

            self.setNightMode()

            self.TELEGRAM_MODE = self.SSHSERVER.get_tgmode()
            self.AI_SENS = self.SSHSERVER.get_aisens()

            # Heartbeat
            if self.DO_HEARTBEAT and time.time() - self.LASTHEARTBEAT >= self.MAXT_HEARTBEAT * 60:
                self.LASTHEARTBEAT = time.time()
                rec0 = False
                for i in range(len(self.CAMERADATA)):
                    if self.SSHSERVER.recording():
                        rec0 = True
                        break
                ar0 = self.SSHSERVER.alarmrunning()
                if self.HEARTBEAT_DEST == "mail":
                        self.SENDMSG.sendstatus("smtp", "GUCK - Heartbeat", None, (rec0, ar0))
                elif self.HEARTBEAT_DEST == "telegram" and self.DO_TELEGRAM and self.TELEGRAMBOT:
                        self.SENDMSG.sendstatus("telegram", None, None, (rec0, ar0))
                logger.info("Heartbeat sent!")

            # skip main loop if paused
            try:
                if self.SSHSERVER.get_alarmquit():
                    logger.info("Receiving quit ...")
                    break
                if not self.SSHSERVER.alarmrunning():
                    self.WAS.set_paused(True)
                    self.LASTPROC = time.time()
                    time.sleep(0.1)
                    continue
                else:
                    self.WAS.set_paused(False)
            except AttributeError:
                pass

            # clear detection queues if flag is set
            clearflag = False
            if self.SSHSERVER.get_alarmclear():
                clearflag = True
                self.SSHSERVER.set_alarmclear(False)

            i = 0
            camlist = []

            for cmtr in camthread:
                camlist.append((None, None, None, None, None))
                if not self.CAMERADATA[i].ENABLE:
                    camlist[i] = (self.CAMERADATA[i].CAMNAME, None, None, None, None)
                    i += 1
                    continue
                mogsens = self.SSHSERVER.get_mogsens_(i)
                cmtr.set_outdata((clearflag, mogsens, self.NIGHTMODE))
                exp00 = cmtr.get_indata()
                if exp00 is not None:
                    ret, frame0, objlist, tx0 = exp00
                    if self.AI_MODE == "cnn":
                        objlist = self.get_cnn_classification(frame0, objlist)
                    ctstatus = self.interpret_status(self.CAMERADATA[i].STATUS)
                    camlist[i] = (self.CAMERADATA[i].CAMNAME, frame0, ctstatus, objlist, tx0)
                    cmtr.set_objlist(objlist)
                self.CAMERADATA[i].STATUS = cmtr.get_status()
                i += 1

            # processing loop: draw detections, send messages
            for i in range(len(self.CAMERADATA)):
                if self.CAMERADATA[i].ENABLE:
                    camname, frame0, ctstatus, objlist, tx0 = camlist[i]
                    if self.CAMERADATA[i].STATUS == 2 and camname is not None:
                        shmlist[i] = camlist[i]
                        frame0copy = frame0.copy()
                        humancount = len([o for o in objlist if o[2] >= self.HCLIMIT])
                        # Draw detection
                        for o in objlist:
                            o_id, o_rect, o_class_ai, _ = o
                            if o_class_ai >= self.HCLIMIT:
                                x, y, w, h = o_rect
                                outstr = "{:.1f}".format(o_class_ai) + " : " + "HUMAN"
                                cv2.rectangle(frame0, (x, y), (x + w, y + h), (255, 0, 0), 2)
                                cv2.putText(frame0, outstr, (x + 3, y+h-10), cv2.FONT_HERSHEY_DUPLEX, 0.3, (0, 255, 0))
                         # output
                        tstr = time.strftime("%a, %d %b %H:%M:%S", time.localtime(tx0))

                        self.CAMERADATA[i].TSLIST.append(time.time())
                        if len(self.CAMERADATA[i].TSLIST) > 30:
                            del self.CAMERADATA[i].TSLIST[0]
                        if len(self.CAMERADATA[i].TSLIST) > 1:
                            a = [self.CAMERADATA[i].TSLIST[j+1]-self.CAMERADATA[i].TSLIST[j]
                                 for j in range(0, len(self.CAMERADATA[i].TSLIST)-1)]
                            fps = 1/(sum(a)/len(a))
                        else:
                            fps = 0
                        outstr = tstr + " : " + str(int(fps)) + " fps"
                        self.SSHSERVER.set_fps(camname, fps)
                        cv2.putText(frame0, outstr, (5, 20), cv2.FONT_HERSHEY_DUPLEX, 0.3, (0, 255, 0))

                        # log
                        if humancount >= self.HCLIMIT and time.time()-self.LASTLOG >= 10:
                            logger.info(camname + " / " + tstr + ": HUMAN detected!")
                            self.LASTLOG = time.time()
                        # ftp
                        if (humancount >= self.HCLIMIT) and self.DO_FTP and time.time()-self.LASTFTP >= self.FTP_MAXT:
                                self.LASTFTP = time.time()
                                tm = time.strftime("%a, %d %b %Y %H:%M:%S")
                                photoname = "guck" + tm + ".jpg"
                                cv2.imwrite("alarmphoto.jpg", frame0)
                                self.SENDMSG.sendphoto("ftp", photoname, "alarmphoto.jpg")
                                logger.info("FTP uploaded!")
                        # mail
                        if (humancount >= self.HCLIMIT) and self.DO_MAIL and time.time()-self.LASTMAIL >= self.MAXT_MAIL:
                                self.LASTMAIL = time.time()
                                res0 = str(humancount) + " humans(s) detected!"
                                if self.MAIL_ONLYTEXT:
                                    self.SENDMSG.sendtext("smtp", res0, "Pls see FTP or Telegram for photos ...", None)
                                else:
                                    cv2.imwrite("alarmphoto.jpg", frame0)
                                    self.SENDMSG.sendphoto("smtp", res0, "alarmphoto.jpg", None)
                                # rr = self.MAIL.sendmail("GUCK - Object detected!", res0)
                                logger.info("Mail sent!")
                        # SMS
                        if (humancount >= self.HCLIMIT) and self.DO_SMS and time.time()-self.LASTSMS >= self.SMS_MAXTSMS:
                                self.LASTSMS = time.time()
                                res0 = str(humancount) + " human(s) detected!"
                                data = urllib.parse.urlencode({'username': self.SMS_USER, 'hash': self.SMS_HASHCODE,
                                                               'numbers': self.SMS_DESTNUMBER, 'message': res0,
                                                               'sender': self.SMS_SENDER})
                                data = data.encode('utf-8')
                                request = urllib.request.Request("http://api.txtlocal.com/send/?")
                                f = urllib.request.urlopen(request, data)
                                logger.info("SMS sent!")

                        # Telegram system critical
                        if (time.time() - self.LASTCRIT) > 60 and self.DO_CRIT and self.DO_TELEGRAM and self.TELEGRAMBOT:
                            answ, mem_crit, cpu_crit, gpu_crit, cam_crit = guckmsg.getstatus(shmlist, self.SSHSERVER.recording(),
                                                                                             self.SSHSERVER.alarmrunning())
                            logger.info("System status: MEM - " + str(mem_crit) + "; CPU - " + str(cpu_crit) + "; GPU - "
                                        + str(gpu_crit) + "; CAMS - " + str(cam_crit))
                            self.LASTCRIT = time.time()
                            if mem_crit or cpu_crit or gpu_crit or cam_crit:
                                self.SENDMSG.sendtext("telegram", None, answ, None)

                        # wastl
                        if (humancount >= self.HCLIMIT and tx0 - self.LASTWASTL >= self.MAXT_TELEGRAM):
                            tm = time.strftime("%a, %d %b %Y %H:%M:%S")
                            self.WAS.push((frame0, tm))
                            self.LASTWASTL = tx0

                        # Telegram
                        if (humancount >= self.HCLIMIT) and self.DO_TELEGRAM and self.TELEGRAMBOT and\
                           self.TELEGRAM_MODE == "verbose" and tx0-self.LASTTELEGRAM >= self.MAXT_TELEGRAM:
                            cv2.imwrite("alarmphoto.jpg", frame0)
                            msg = str(humancount) + " human(s) detected!"
                            self.SENDMSG.sendtext("telegram", None, msg, None)
                            self.SENDMSG.sendphoto("telegram", None, "alarmphoto.jpg", None)
                            tm = time.strftime("%a, %d %b %Y %H:%M:%S")
                            logger.info("Telegramm msg. sent at " + tm)
                            self.LASTTELEGRAM = tx0    # time.time()

                        # photo
                        if (humancount >= self.HCLIMIT) and self.DO_PHOTO and time.time()-self.LASTPHOTO >= self.MAXT_DETECTPHOTO:
                            tm = time.strftime("%a, %d %b %Y %H:%M:%S")
                            photoname = self.APHOTO_DIR + "/AP" + tm + ".jpg"
                            try:
                                cv2.imwrite(photoname, frame0)
                                logger.info("Photo saved @ " + tm)
                                if self.PHOTO_CUTOFF:
                                    if len(os.listdir(str(self.APHOTO_DIR))) > self.PHOTO_CUTOFF_LEN:
                                        oldest = self.APHOTO_DIR + "/" + min(os.listdir(str(self.APHOTO_DIR)), key=lambda
                                                                             f: os.path.getctime(self.APHOTO_DIR + "/" + f))
                                        os.remove(oldest)
                                        logging.info("Photo removed: " + oldest)
                            except Exception as e:
                                logger.error("Cannot save photo: " + str(e))
                                self.DO_PHOTO = False
                            self.LASTPHOTO = time.time()
                        # ai_photo
                        if self.DO_AI_PHOTO and time.time() - self.LASTAIPHOTO > 2:
                            tm = time.strftime("%a, %d %b %Y %H:%M:%S")
                            frame_height = frame0copy.shape[0]
                            frame_width = frame0copy.shape[1]
                            # print(frame_height, frame_width)
                            new_w = 128
                            new_h = 128
                            # if detection -> resize/crop detection to 128 x 128
                            j = 1
                            for o in objlist:
                                    o_id, o_rect, o_class_ai, _ = o
                                    x, y, w, h = o_rect
                                    if w == max(w, h):
                                            if y + w > frame_height:
                                                y0 = y
                                                y = y - (y + w - frame_height)
                                                if y < 0:
                                                    img = cv2.resize(frame0copy[y0:y0+h, x:x+w], (new_w, new_h))
                                                else:
                                                    img = cv2.resize(frame0copy[y:y+w, x:x+w], (new_w, new_h))
                                            else:
                                                img = cv2.resize(frame0copy[y:y+w, x:x+w], (new_w, new_h))
                                    else:
                                            if x + h > frame_width:
                                                x0 = x
                                                x = x - (x + h - frame_width)
                                                if x < 0:
                                                    img = cv2.resize(frame0copy[y:y+h, x0:x0+w], (new_w, new_h))
                                                else:
                                                    img = cv2.resize(frame0copy[y:y+h, x:x+w], (new_w, new_h))
                                            else:
                                                img = cv2.resize(frame0copy[y:y+h, x:x+w], (new_w, new_h))
                                    img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                                    photoname = None
                                    if o_class_ai >= self.HCLIMIT:
                                        photoname = self.AIPHOTO_DIR + "/AP" + str(j) + tm + ".jpg"
                                    elif o_class_ai == 0:
                                        photoname = self.AIPHOTO_DIR_NEG + "/AP" + str(j) + tm + ".jpg"
                                    if photoname:
                                        try:
                                            cv2.imwrite(photoname, img)
                                        except Exception as e:
                                            logger.error("Cannot save ai photo: " + str(e))
                                            self.DO_AI_PHOTO = False
                                        self.LASTAIPHOTO = time.time()
                                        j += 1

                        # recording
                        try:
                            if self.SSHSERVER.recording():    # and self.CAMERADATA[i].DO_RECORD:
                                self.CAMERADATA[i].OUTVIDEO.write(frame0)
                                pass
                        except AttributeError:
                            logger.warning("Cannot write video frame for camera " + str(i) + ", disabling recording ...")
                            self.CAMERADATA[i].DO_RECORD = False

                        if self.SHOW_FRAMES:
                            cv2.imshow(camname, frame0)

                        # fps logging every min
                        if self.DO_LOGFPS and time.time() - self.LASTPROC > 60:
                            fpslist = []
                            ret = "Processing @ "
                            for i in range(len(self.CAMERADATA)):
                                a = [self.CAMERADATA[i].TSLIST[j+1]-self.CAMERADATA[i].TSLIST[j]
                                     for j in range(0, len(self.CAMERADATA[i].TSLIST)-1)]
                                fps = 1/(sum(a)/len(a))
                                fpslist.append(fps)
                                if i < len(self.CAMERADATA) - 1:
                                    ret += "{0:4.1f}".format(fps) + "/ "
                                else:
                                    ret += "{0:4.1f}".format(fps) + "fps"
                            self.LASTPROC = time.time()
                            logger.info(ret)

            ch = cv2.waitKey(1) & 0xFF
            if ch == 27 or ch == ord("q"):
                break

            allcamsok = (True if len([shm for shm in shmlist if shm == []]) == 0 else False)

            if allcamsok:
                SEMAPHORE.acquire()
                self.SSHSERVER.set_SHMLIST(shmlist)
                SEMAPHORE.release()

            time.sleep(0.05)

        self.shutdown()
        return


# ------------------------------------- main -------------------------------------------

if __name__ == "__main__":

    gc = GControl(_DB)

    # start threads
    logger.info("Starting up camera processes ...")
    nbcams = len(gc.CAMERADATA)
    gc.startupcamthread()
    brstatelist = gc.getcamthreadstates(1)
    logger.info("Starting up " + str(len(brstatelist)) + " out of " + str(nbcams) + " cameras!")
    if len(brstatelist) == 0:
        logger.warning("No camera running, starting guck in idle state ...")

    # threads send init data and start up sequence
    logger.info("Sending init sequence to camera processes ...")
    gc.initcamthread()
    brstatelist = []
    brstatelist = gc.getcamthreadstates(2)
    logger.info("Initializing up " + str(len(brstatelist)) + " out of " + str(nbcams) + " cameras!")
    if len(brstatelist) == 0:
        logger.warning("No camera running/initialized, starting guck in idle state ...")

    logger.info("STARTUP COMPLETED SUCCESSFULLY !")

    # read loop
    gc.framereadloop()
