import sys
sys.path.append("../../lib")

import os
import cv2
import numpy as np
import time
import execnet
import dill
import signal
from random import randint
import logging, datetime

def siginthandler(signum, frame):
    sys.exit()

def auto_canny(image, sigma=0.33):
    v = np.median(image)
    lower = int(max(0, (1.0 - sigma) * v))
    upper = int(min(255, (1.0 + sigma) * v))
    edged = cv2.Canny(image,lower,upper)
    return edged

def overlap_rects(r1,r2):
    x11, y11, w, h = r1
    x12 = x11 + w
    y12 = y11 + h
    area1 = w * h
    x21, y21, w, h = r2
    x22 = x21 + w
    y22 = y21 + h
    area2 = w * h
    x_overlap = max(0, min(x12, x22) - max(x11, x21))
    y_overlap = max(0, min(y12, y22) - max(y11, y21))
    overlapArea = x_overlap * y_overlap
    return overlapArea, overlapArea/area1, overlapArea/area2

class Detection:
    def __init__(self, id, frame, t, rect, descr, cd, ca):
        self.id = id
        self.rect = rect
        self.class_detection = cd
        self.class_detection_lt = t
        self.class_ai = ca
        self.class_ai_lt = 0
        self.frame = frame
        self.t = t
        self.descrkp = None
        self.descrdes = None
        self.descriptor = descr
        self.calcHog_descr()

    def calcHog_descr(self):
        x, y, w, h = self.rect
        self.descrkp, self.descrdes = self.descriptor.detectAndCompute(self.frame[y:y+h, x:x+w], None)
        return


class Matcher:

    def __init__(self, surl, minarea, hogscale, hogthresh, scanrate, mog2sens,
                 aimode, haarpath, haarpath2, haarscale):

        self.MATCHER_METHOD = "ORB"
        self.YMAX0 = self.XMAX0 = None
        self.SURL = surl
        self.MINAREA = minarea

        self.DETECTIONS = []
        self.IDCOUNTER = 0
        self.HOGSCALE = hogscale
        self.HOGTHRESH = hogthresh
        self.SCANRATE = scanrate
        self.MOG2SENS = min(max(mog2sens, 0), 10)
        self.CNNMODEL = None
        self.AI_MODE = aimode.lower()
        self.HIST = 800 + (5 - self.MOG2SENS) * 199
        self.NIGHTMODE = False

        if self.AI_MODE == "cv2":
            try:
                osversion = os.popen("cat /etc/os-release").read().split("\n")[2].split("=")[1].replace('"', '')
            except:
                osversion = "ubuntu"
            if osversion == "ubuntu":
                import pbcvt
            else:
                # this won't work as error in libboost python
                import pbcvt_arch as pbcvt
            self.GPUHOG = pbcvt.GPU_HOG(self.HOGSCALE, self.HOGTHRESH)

            try:
                cascade = pbcvt.CASCADE(haarpath, haarscale)
                cascade2 = pbcvt.CASCADE(haarpath2, haarscale)
                self.CASCADE = cascade
                self.CASCADE2 = cascade2
                logger.info("Created Haar-Cuda models for people detection")
            except Exception as e:
                logger.error("Cannot load HAAR models, exiting ...: " + str(e))
                sys.exit()
        cv2.ocl.setUseOpenCL(False)
        self.DESCR = cv2.ORB_create(edgeThreshold=10, fastThreshold=20)
        self.BF = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
        self.setFGBGMOG2(self.MOG2SENS)
        self.KERNEL2 = cv2.getStructuringElement(cv2.MORPH_RECT,(24,24))
        self.CAP = None
        self.CPUHOG = cv2.HOGDescriptor()
        self.CPUHOG.setSVMDetector(cv2.HOGDescriptor_getDefaultPeopleDetector())
        logger.info("Startup completed!")

    def setFGBGMOG2(self, ms):
        if not self.NIGHTMODE:
            hist = 800 + (5 - ms) * 100
            vart = 1500 + (5 - ms) * 250
        else:
            hist = 500 + (5 - ms) * 70
            vart = 400 + (5 - ms) * 60
        # --- for MOG2
        #vart = 20 + (5 - ms) * 4
        logger.info("Creating BackgroundSubtractorKNN(history=" + str(hist) + ", dist2Threshold=" + str(vart) + ", detectShadows=True)")
        #self.FGBG = cv2.createBackgroundSubtractorMOG2(history=hist, varThreshold=vart, detectShadows=True)
        # --- for KNN

        self.HIST = hist
        self.FGBG = cv2.createBackgroundSubtractorKNN(history=hist,dist2Threshold=vart,detectShadows=True)
        return

    def waitforcaption(self):
        ret = False
        for i in range(10):
            self.CAP = cv2.VideoCapture(self.SURL)
            ret, frame = self.CAP.read()
            if ret:
                self.YMAX0, self.XMAX0 = frame.shape[:2]
                break
        return ret

    def getcaptionandprocess(self):
        ret, frame = self.CAP.read()
        t0 = time.time()
        if ret:
            new_detections = []
            gray = cv2.cvtColor(frame.copy(), cv2.COLOR_BGR2GRAY)
            fggray = self.FGBG.apply(gray, 1 / self.HIST)
            #fggray = cv2.GaussianBlur(fggray, (3, 3), 0)
            fggray = cv2.medianBlur(fggray, 5)
            edged = auto_canny(fggray)
            closed = cv2.morphologyEx(edged, cv2.MORPH_CLOSE, self.KERNEL2)
            _, cnts, _ = cv2.findContours(closed.copy(), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cnts0 = [cv2.boundingRect(c) for c in cnts]
            rects = [ (x,y,w,h) for x,y,w,h in cnts0 if w * h > self.MINAREA]

            for r in rects:
                new_detections.append(Detection(-1, frame, t0, r, self.DESCR, 1, 0))

            return ret, new_detections, frame
        else:
            return ret, None, None

    def get_proximity_overlap_rect(self, rect1, rect2):
        _, perc_reo, perc_ren = overlap_rects(rect1,rect2)
        return (1-(perc_ren+perc_reo)/2)*10

    def get_proximity_overlap(self, qnew, qold):
        return self.get_proximity_overlap_rect(qold.rect,qnew.rect)

    def get_proximity_descriptor(self, qnew, qold):
        kpnew = qnew.descrkp
        desnew = qnew.descrdes
        kpold = qold.descrkp
        desold = qold.descrdes
        res1 = 5
        res2 = 5
        if len(kpnew) > 0 and len(kpold) > 0:
            matchesbf = self.BF.match(desnew, desold)
            detectratio = (len(matchesbf)/len(kpnew))
            matches = sorted(matchesbf, key=lambda x: x. distance)
            matches = matches[:20]
            minmatch = min(m.distance for m in matches)
            res1 = 1
            if detectratio < 0.2:
                res1 = 5
            elif detectratio < 0.4:
                res1 = 4
            elif detectratio < 0.6:
                res1 = 3
            elif detectratio < 0.8:
                res1 = 2
            res2 = 5
            if minmatch < 10:
                res2 = 1
            elif minmatch < 20:
                res2 = 2
            elif minmatch < 30:
                res2 = 3
            elif minmatch < 50:
                res2 = 4
            return res1*0.55 + res2*0.45
        else:
            return -1

    def homography_matcher(self, queryImage, trainImage, compute_rect):

        kp1, des1 = self.DESCR.detectAndCompute(queryImage,None)   # queryImage = old frame
        kp2, des2 = self.DESCR.detectAndCompute(trainImage,None)    # trainImage
        matches = self.BF.match(des1,des2)
        newrect = None
        avg_dist = float("inf")
        if matches != []:
            dist = [m.distance for m in matches]
            thres_dist = (sum(dist) / len(dist)) * 0.8
            good = [m for m in matches if m.distance < thres_dist]
            if len(good) >=7:
                avg_dist = sum([g.distance for g in good])/len(good)
                if compute_rect:
                    src_pts = np.float32([ kp1[m.queryIdx].pt for m in good ]).reshape(-1,1,2)
                    dst_pts = np.float32([ kp2[m.trainIdx].pt for m in good ]).reshape(-1,1,2)
                    M, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC,5.0)
                    #matchesMask = mask.ravel().tolist()
                    h,w, _ = queryImage.shape
                    pts = np.float32([ [0,0],[0,h-1],[w-1,h-1],[w-1,0] ]).reshape(-1,1,2)
                    dst = cv2.perspectiveTransform(pts,M)
                    min_x = int(max(0, min(d[0,0] for d in dst)))
                    max_x = int(min(w, max(d[0,0] for d in dst)))
                    w0 = max_x - min_x
                    min_y = int(max(0, min(d[0,1] for d in dst)))
                    max_y = int(min(h, max(d[0,1] for d in dst)))
                    h0 = max_y - min_y
                    newrect = min_x, min_y, w0, h0
        return newrect, avg_dist

    def process_detections(self, frame, detections):
        frame_height = frame.shape[0]
        frame_width = frame.shape[1]
        # if no detections: trotzdem in 1 von 10 Fällen nach humans scannen
        if (detections == [] or len([D for D in self.DETECTIONS if D.class_ai > 0]) == 0 and randint(0,self.SCANRATE) == 0):
                t0 = time.time()
                detections2 = []
                if self.AI_MODE == "cv2":
                    gpuhogrects = self.GPUHOG.detectMultiScale(frame)
                    hogrects = [(gg.x, gg.y, gg.w, gg.h) for gg in gpuhogrects]
                    if len(hogrects) > 0:
                        logger.info("Scan: Human classified with HOG!")
                        for r in hogrects:
                            detections2.append(Detection(self.IDCOUNTER, frame, t0, r, self.DESCR, 1, 1))
                            detections2[-1].class_ai_lt = t0
                            detections2[-1].class_detection_lt = t0
                            self.IDCOUNTER += 1
                            if self.IDCOUNTER > 65535:
                                self.IDCOUNTER = 0
                self.DETECTIONS += detections2
        new_detections = []
        for D in self.DETECTIONS:
            if (D.class_detection > 5 and D.class_ai == 0):
                continue
            results = []
            # search new detections for proximity to old detections
            for d in detections:
                pr_descr = self.get_proximity_descriptor(d, D)
                ol_descr = self.get_proximity_overlap(d, D)
                if pr_descr == -1:
                    measure = ol_descr
                else:
                    measure = 0.5 * pr_descr + 0.5 * ol_descr
                results.append((d, measure))
            # matches found!
            if len(results) > 0:
                d0, measure0 = min([r for r in results], key=lambda r0: r0[1 ])
                # best match is sufficient
                if measure0 <= 3:
                    # insert detection = old id, new frame, new rect, best of classification
                    new_detections.append(Detection(D.id, d0.frame, d0.t, d0.rect, self.DESCR,D.class_detection + 1,
                                                    D.class_ai))
                    # then: best rect already processed, should not be used for future merges
                    detections.remove(d0)
            # keine Übereinstimmung mit detection
            else:
                if D.class_ai > 0:
                    # zuerst mit template matching
                    x,y,w,h = D.rect
                    x0 = int(max(0, x - w * 0.15))
                    y0 = int(max(0, y - h * 0.15))
                    w0 = int(min (self.XMAX0,  x + w + w * 0.15)) - x0
                    h0 = int(min (self.YMAX0, y + h + h * 0.15)) - y0
                    # get new
                    frame_c = frame[y0:y0+h0, x0:x0+w0]     # neues Suchgebiet
                    template = D.frame[y:y+h, x:x+w]        # altes Objekt
                    if self.MATCHER_METHOD == "TEMPLATE":
                        res1 = cv2.matchTemplate(frame_c,template,cv2.TM_SQDIFF_NORMED)
                        min_val, max_val, min_loc, max_loc = cv2.minMaxLoc(res1)
                        top_left = min_loc
                        # match!
                        if min_val < 0.02:
                            newrect = top_left[0], top_left[1], w,h
                            new_detections.append(Detection(D.id, frame, D.t, newrect, self.DESCR,D.class_detection,
                                                    D.class_ai))
                            D0 = new_detections[-1]
                            # falls new detection damit overlapped -> raushaun!
                            results = [(d,self.get_proximity_overlap(d, D0)) for d in detections]
                            if results != []:
                                d0, mino = min([r for r in results], key=lambda r0: r0[1])
                                if mino < 3:
                                    detections.remove(d0)
                    elif self.MATCHER_METHOD == "ORB":
                        newrect_orig, dist = self.homography_matcher(template, frame_c, True)
                        if newrect_orig != None and dist < 30:
                            x1,y1,w1,h1 = newrect_orig
                            newrect = x1 + x0, y1 +y0, w1, h1
                            new_detections.append(Detection(D.id, frame, D.t, newrect, self.DESCR, D.class_detection,
                                                    D.class_ai))
                            D0 = new_detections[-1]
                            # falls new detection damit overlapped -> raushaun!
                            results = [(d,self.get_proximity_overlap(d, D0)) for d in detections]
                            if results != []:
                                d0, mino = min([r for r in results], key=lambda r0: r0[1])
                                if mino < 3:
                                    detections.remove(d0)
                    else:
                        pass

        # insert remaining rects
        for d in detections:
            id = self.IDCOUNTER
            new_detections.append(Detection(id, d.frame, d.t, d.rect, self.DESCR, d.class_detection,
                                  d.class_ai))
            self.IDCOUNTER += 1
            if self.IDCOUNTER > 65535:
                self.IDCOUNTER = 0

        self.DETECTIONS[:] = new_detections

        #update ai if necessary
        for D in self.DETECTIONS:
            # last haar check länger her als 2 sec and Anteil der haar results < 10% -> checken
            if time.time() - D.class_ai_lt >= 2  and D.class_ai/D.class_detection < 0.1:

                x,y,w,h = D.rect
                x0 = int(max(0, x - w * 0.50))
                y0 = int(max(0, y - h * 0.50))
                w0 = int(min (self.XMAX0,  x + w + w * 0.50)) - x0
                h0 = int(min (self.YMAX0, y + h + h * 0.50)) - y0
                frame_c = D.frame[y0:y0+h0, x0:x0+w0]
                if self.AI_MODE == "cv2":
                    hc = []
                    try:
                        if randint(0,1) == 0:
                            hc = self.CASCADE.detectMultiScale(frame_c)
                        else:
                            hc = self.CASCADE2.detectMultiScale(frame_c)
                        if len(hc) > 0:
                            D.class_ai_lt = time.time()
                            D.class_ai += 1
                            logger.info("Human classified with Haar!")
                    except Exception as e:
                        logger.error("Cannot classify with Haar: " + str(e))
                    if len(hc) == 0:
                        try:
                            # if no haar match: try GPUHOG
                            #hogrects, hogweights = self.CPUHOG.detectMultiScale(frame, winStride=(4, 4), padding=(8, 8), scale=1.10)
                            gpuhogrects = self.GPUHOG.detectMultiScale(frame)
                            hogrects = [(gg.x, gg.y, gg.w, gg.h)  for gg in gpuhogrects]
                            if len(hogrects) > 0:
                                results =min ([(h,  self.get_proximity_overlap_rect(D.rect, h)) for h in hogrects],
                                        key=lambda x: x[1])
                                if results != [] and results[0][1] <= 2:
                                    D.class_ai_lt = time.time()
                                    D.class_ai += 1
                                    logger.info("Human classified with HOG!")
                        except Exception as e:
                            logger.error("Cannot classify with HOG: " + str(e))

        return self.DETECTIONS

    def drawdetections(self, frame):
        frame0 = frame.copy()
        for D in self.DETECTIONS:
            if D.class_ai > 0:
                x, y, w, h = D.rect
                color = (0, 255, 0)
                frame0 = cv2.rectangle(frame0, (x, y), (x+w, y+h), color, 2)
                outstr = str(D.id) + " # det:" + str(D.class_detection) + "# ai:" + str(D.class_ai)
                cv2.putText(frame0, outstr, (x, y+20), cv2.FONT_HERSHEY_DUPLEX, 0.3, (0, 255, 0))
        return frame0

if __name__ == "__channelexec__":

    signal.signal(signal.SIGINT, siginthandler)
    # haarpath_cuda = "/home/stephan/Programme/opencv/data/haarcascades_cuda/haarcascade_upperbody.xml"
    # haarpath_cuda2 = "/home/stephan/Programme/opencv/data/haarcascades_cuda/haarcascade_fullbody.xml"
    # upper_body_cascade = cv2.CascadeClassifier(haarpath)
    # upper_body_cascade = pbcvt.CASCADE(haarpath_cuda, 1.05)

    (INPUT_MODE, SNAME, SURL, VIDEOFILE, MINAREA, HAARPATH, HAARPATH2, HAARSCALE, HOGSCALE, HOGTHRESH, SCANRATE, MOG2SENS,
     AIMODE) = dill.loads(channel.receive())

    GUCK_HOME = os.environ["GUCK_HOME"]
    ln = "guck_" + SNAME
    logger = logging.getLogger(ln)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(GUCK_HOME + "log/" + ln + ".log", mode="w")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.info("Camera thread started")

    logger.info(str(HAARPATH) + " " + str(HOGSCALE))

    if INPUT_MODE == "video":
        SURL = VIDEOFILE

    tm = Matcher(SURL, MINAREA, HOGSCALE, HOGTHRESH, SCANRATE, MOG2SENS, AIMODE, HAARPATH, HAARPATH2, HAARSCALE)

    # try to catch 1st frame
    ret = tm.waitforcaption()
    if not ret:
        channel.send(SNAME + ":#hostnotok")
        logger.error("Cannot initiate OpenCV videocapture, exiting ...")
        sys.exit()  # ???
    else:
        logger.info("OpenCV videocapture initiated")
        channel.send(SNAME + ":#hostok")
        while channel.receive() != "#start!":
            continue

    lasttt = time.time()
    while True:
        frame = None
        if time.time() - lasttt > 3:
            logger.warning("Restarting Videocapture ...")
            tm.CAP = cv2.VideoCapture(SURL)
            time.sleep(2)
            lasttt = time.time()
        try:
            # nur zwecks synchronisation
            objaidir, clearflag, mogsens, nightmode = dill.loads(channel.receive())
            if nightmode != tm.NIGHTMODE:
                tm.NIGHTMODE = nightmode
                tm.setFGBGMOG2(tm.MOG2SENS)
                logger.info("Setting Nightmode to " + str(nightmode))
            # objaidir: id, rect, class_ai
            if AIMODE.lower() == "cnn":
                for o in objaidir:
                    id, rect, class_ai, lt0 = o
                    for D in tm.DETECTIONS:
                        if id == D.id:
                            D.class_ai = class_ai
                            D.class_ai_lt = lt0
            if clearflag == True:
                tm.DETECTIONS = []
                logger.info("Detection queue cleared!")
            if mogsens != tm.MOG2SENS:
                if int(mogsens) >= 0 and int(mogsens) <= 10:
                    del tm.FGBG
                    tm.setFGBGMOG2(int(mogsens))
                    tm.MOG2SENS = int(mogsens)
                    logger.info("Set MOG2 sensitivity to " + str(int(mogsens)))
                else:
                    logger.warning("Cannot set MOG2 sensitivity in cam thread!")
            ret, detections, frame = tm.getcaptionandprocess()
            if ret:
                lasttt = time.time()
                detectionlist = tm.process_detections(frame, detections)
                # frame_detected = tm.drawdetections(frame)
                converted_list = [(d.id, d.rect, d.class_ai, d.class_ai_lt) for d in detectionlist]
                exp0 = dill.dumps((ret, frame, converted_list, time.time()))
            else:
                logger.error("Couldn't capture frame!")
                exp0 = exp0 = dill.dumps((ret, None, [], None))

        except Exception as e:
            logger.error("openCV error in thread" + str(e))
            exp0 = dill.dumps((ret, frame, [], None))
        channel.send(exp0)

