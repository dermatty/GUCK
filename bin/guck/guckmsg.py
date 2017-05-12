import zmq, ftplib
import time, threading
import subprocess
import psutil, smtplib
from threading import Thread
from email.utils import formatdate
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
import queue, cv2, requests, posix_ipc
import telepot , sensors, logging
import os
import dill

ALARM_BREAK = False
ALARM_QUIT = False
TG_MODE = "verbose"
RECORDING = False
ALARM_PHOTO = None
ALARM_CLEAR = False
AIMODE = "cv2"
FPS = {}
MOGSENS = None
SHMLIST = []
FPSLIST = []
INITDATA = None
AISENS = None
HCLIMIT = 1
NIGHTMODE = False

ln = "guck.msg"
logger = logging.getLogger(ln)


def getstatus(shmlist, recording, alarmrunning):
        global TG_MODE
        global AIMODE
        global HCLIMIT
        global NIGHTMODE
        ret = "------- General -------"
        ret += "\nVersion: " + os.environ["GUCK_VERSION"]
        ret += "\nRecording: "
        ret += "YES" if recording else "NO"
        ret += "\nPaused: "
        ret += "YES" if not alarmrunning else "NO"
        ret += "\nTelegram Mode: " + TG_MODE
        ret += "\nAI Mode: " + AIMODE.upper()
        ret += "\nAI Sens.: " + str(AISENS)
        ret += "\nHCLIMIT: " + str(HCLIMIT)
        ret += "\nNIGHTMODE: "
        ret += "YES" if NIGHTMODE else "NO"
        ret += "\n------- System -------"
        overall_mem = round(psutil.virtual_memory()[0] / float(2 ** 20) / 1024, 2)
        free_mem = round(psutil.virtual_memory()[1] / float(2 ** 20) / 1024, 2)
        used_mem = round(overall_mem - free_mem, 2)
        perc_used = round((used_mem / overall_mem) * 100, 2)
        mem_crit = False
        if perc_used > 85:
            mem_crit = True
        cpu_perc = psutil.cpu_percent(interval=0.25, percpu=False)
        cpu_crit = False
        if cpu_perc > 0.8:
            cpu_crit = True
        ret += "\nRAM: " + str(perc_used) + "% ( =" + str(used_mem) + " GB) of overall " + str(overall_mem) + \
               " GB used"
        ret += "\nCPU: " + str(cpu_perc) + "% utilized"
        sensors.init()
        cpu_temp = []
        for chip in sensors.iter_detected_chips():
                for feature in chip:
                    if feature.label[0:4] == "Core":
                        temp0 = feature.get_value()
                        cpu_temp.append(temp0)
                        ret += "\nCPU " + feature.label + " temp.: " + str(round(temp0, 2)) + "°"
        sensors.cleanup()
        if len(cpu_temp) > 0:
            avg_cpu_temp = sum(c for c in cpu_temp)/len(cpu_temp)
        else:
            avg_cpu_temp = 0
        if avg_cpu_temp > 52.0:
            cpu_crit = True
        else:
            cpu_crit = False
        # gpu info
        gputemp = subprocess.Popen(["/usr/bin/nvidia-smi", "--query-gpu=temperature.gpu", "--format=csv"],
                                   stdout=subprocess.PIPE).stdout.readlines()[1]
        gpuutil = subprocess.Popen(["/usr/bin/nvidia-smi", "--query-gpu=utilization.gpu", "--format=csv"],
                                   stdout=subprocess.PIPE).stdout.readlines()[1]
        gputemp_str = gputemp.decode("utf-8").rstrip()
        gpuutil_str = gpuutil.decode("utf-8").rstrip()
        ret += "\nGPU temp.: " + gputemp_str + "C"
        ret += "\nGPU util.: " + gpuutil_str
        if float(gputemp_str) > 70.0:
            gpu_crit = True
        else:
            gpu_crit = False

        ret += "\n------- Cameras -------"
        camstate = []
        for key, value in FPS.items():
            ctstatus0 = "n/a"
            dt = 0.0
            mog = -1
            j = 0
            for i in shmlist:
                try:
                    sname, frame, ctstatus, _, tx0 = i
                    if key == sname:
                        mog = MOGSENS[j]
                        dt = time.time() - tx0
                        if dt > 30:
                            ctstatus0 = "DOWN"
                        elif dt > 3:
                            ctstatus0 = "DELAYED"
                        else:
                            ctstatus0 = "running"
                        camstate.append(ctstatus0)
                except:
                    pass
                j += 1
            ret += "\n" + key + " " + ctstatus0 + " @ %3.1f fps\r" % value + ", sens.=" + str(mog) + " (%.2f" % dt + " sec. ago)"
        cam_crit = False
        if len([c for c in camstate if c != "running"]) > 0:
            cam_crit = True
        ret += "\n------- System Summary -------"
        ret += "\nRAM: "
        ret += "CRITICAL!" if mem_crit else "OK!"
        ret += "\nCPU: "
        ret += "CRITICAL!" if cpu_crit else "OK!"
        ret += "\nGPU: "
        ret += "CRITICAL!" if gpu_crit else "OK!"
        ret += "\nCAMs: "
        ret += "CRITICAL!" if cam_crit else "OK!"
        return ret, mem_crit, cpu_crit, gpu_crit, cam_crit


class MessageHandler:
    def __init__(self, do_debug, initdata):
        global MOGSENS
        SEMAPHORE_NAME = "/gucksemaphore1"
        self.SEMAPHORE = posix_ipc.Semaphore(SEMAPHORE_NAME)
        self.DO_DEBUG = do_debug
        self.SEMAPHORE.acquire()
        self.PTZ_INIT, self.REBOOT_INIT, MOGSENS = initdata
        self.SEMAPHORE.release()
        logger.info("MessageHandler initiated")

    def set_fps(self, cn, fps):
        global FPS
        FPS[cn] = fps

    def get_fps(self, cn):
        global FPS
        return FPS[cn]

    def set_hclimit(self, hc):
        global HCLIMIT
        HCLIMIT = hc

    def get_hclimit(self):
        global HCLIMIT
        return HCLIMIT

    def set_nightmode(self, nm):
        global NIGHTMODE
        NIGHTMODE = nm

    def get_nightmode(self):
        global NIGHTMODE
        return NIGHTMODE

    def set_aisens(self, a):
        global AISENS
        AISENS = a

    def get_aisens(self):
        global AISENS
        return AISENS

    def get_aimode(self):
        global AIMODE
        return AIMODE

    def set_aimode(self, a):
        global AIMODE
        if a.lower() == "cnn":
            AIMODE = "cnn"
        else:
            AIMODE = "cv2"

    def set_tgmode(self, flg):
        global TG_MODE
        if flg == "verbose" or flg == "silent":
            TG_MODE = flg
            return True
        return False

    def get_tgmode(self):
        global TG_MODE
        return TG_MODE

    def set_recording(self, flg):
        global RECORDING
        if RECORDING != flg:
            ret = True
        else:
            ret = False
        RECORDING = flg
        return ret

    def set_mogsens(self, i, m):
        global MOGSENS
        self.SEMAPHORE.acquire()
        try:
            if int(m) <= 10 and int(m) >= 0:
                MOGSENS[i] = int(m)
        except:
            logger.info("Cannot set mogsens, either cam index " + str(i) + " or mog value " + str(m) + " out of range!")
        self.SEMAPHORE.release()

    def get_mogsens_(self, i):
        global MOGSENS
        self.SEMAPHORE.acquire()
        res = MOGSENS[i]
        self.SEMAPHORE.release()
        return res

    def set_alarmclear(self, boolFlg):
        global ALARM_CLEAR
        self.SEMAPHORE.acquire()
        try:
            if boolFlg == True:
                ALARM_CLEAR = True
            else:
                ALARM_CLEAR = False
        except:
            ALARM_CLEAR = False
        self.SEMAPHORE.release()

    def get_alarmclear(self):
        global ALARM_CLEAR
        self.SEMAPHORE.acquire()
        res = ALARM_CLEAR
        self.SEMAPHORE.release()
        return res

    def set_alarmbreak(self, flg):
        global ALARM_BREAK
        if ALARM_BREAK != flg:
            ret = True
        else:
            ret = False
        ALARM_BREAK = flg
        return ret

    def alarmrunning(self):
        global ALARM_BREAK
        if ALARM_BREAK:
            ret = False
        else:
            ret = True
        return ret

    def set_alarmquit(self):
        global ALARM_QUIT
        ALARM_QUIT = True

    def set_alarmphoto(self, flg):
        global ALARM_PHOTO
        ALARM_PHOTO = flg

    def get_alarmphoto(self):
        global ALARM_PHOTO
        res = ALARM_PHOTO
        return res

    def get_alarmquit(self):
        global ALARM_QUIT
        res = ALARM_QUIT
        return res

    def recording(self):
        global RECORDING
        if RECORDING:
            ret = True
        else:
            ret = False
        return ret

    def set_SHMLIST(self, shmlist):
        global SHMLIST
        global FPSLIST
        SHMLIST = shmlist
        return

    def get_SHMLIST(self):
        global SHMLIST
        return SHMLIST

    def Manage(self, req0):
        global SHMLIST
        self.SEMAPHORE.acquire()
        # self.CAMERADATA[i].CAMNAME, frame0, ctstatus, objlist, framefull, tx0, cr, objlist
        shmlist = self.get_SHMLIST()
        self.SEMAPHORE.release()
        repframe = None
        repname = None
        r0s = req0.split(" ")
        r0s0 = r0s[0].lower()
        rep0 = "N/A"
        if r0s0 == "help":
            rep0 = "help \npause \nresume \nquit \nstatus\nphoto <cam>\nrecord start/stop \nptz <cam> r/l/u/d" \
                   "\nclear\nreboot <cam>\nsens <cam> <int 0 - 10>\nping\ntgmode <silent/verbose>\naisens <0...10>"
            logger.info("help printed!")
        elif r0s0 == "pause":
            res = self.set_alarmbreak(True)
            if res:
                rep0 = "GUCK paused!"
            else:
                rep0 = "GUCK already paused before!"
            logger.info("GUCK paused!")
        elif r0s0 == "clear":
            self.set_alarmclear(True)
            rep0 = "Clearing detection queue ..."
            logger.info("Setting alarm clear flag!")
        elif r0s0 == "resume":
            res = self.set_alarmbreak(False)
            if res:
                rep0 = "GUCK resumed!"
            else:
                rep0 = "GUCK already running"

            logger.info("GUCK resumed!")
        elif r0s0 == "tgmode":
            try:
                tgmode = r0s[1].lower()
                ret = self.set_tgmode(tgmode)
                if ret:
                    rep0 = "Set Telegram mode to: " + tgmode
                else:
                    rep0 = "Wrong Telegram mode, must be <silent> or <verbose>!"
            except Exception as e:
                logger.error("Error in setting Telegram mode:" + str(e))
        elif r0s0 == "reboot":
            try:
                camnr = int(r0s[1])
                rep0 = "Rebooting camera ..."
                httpstr = self.REBOOT_INIT[camnr]
                r = requests.get(httpstr)
            except Exception as e:
                logger.error("Error in rebooting:" + str(e))
        elif r0s0 == "aisens":
            try:
                aisens = int(r0s[1])
                if aisens < 0 or aisens > 10:
                    raise Exception("Wrong value for AI sensitivity!")
                self.set_aisens(aisens)
                rep0 = "Set sensitivity for AI to " + str(aisens) + "!"
            except Exception as e:
                rep0 = "Set AI sensitivy error: " + str(e)
        elif r0s0 == "sens":
            try:
                camnr = int(r0s[1])
                mogsens = int(r0s[2])
                dum = MOGSENS[camnr]
                if mogsens < 0 or mogsens > 10:
                    raise Exception("Wrong value for mog sensitivity!")
                self.set_mogsens(camnr, mogsens)
                rep0 = "Set sensitivity for cam # " + str(camnr) + " to " + str(mogsens) + " !"
            except Exception as e:
                rep0 = "Set mog sensitivy error: " + str(e)
        elif r0s0 == "ptz":
            try:
                camnr = int(r0s[1])
                ptzstr = r0s[2]
                # self.set_ptz(camnr, ptz)
                rep0 = "Moving camera ..."
                ptzm, ptzr, ptzl, ptzu, ptzd = self.PTZ_INIT[camnr]
                httpstr = ""
                if ptzstr == "r":
                    httpstr = ptzr
                elif ptzstr == "l":
                    httpstr = ptzl
                elif ptzstr == "d":
                    httpstr = ptzd
                elif ptzstr == "u":
                    httpstr = ptzu
                if httpstr != "":
                    r = requests.get(httpstr)
                    if ptzm == "STARTSTOP":
                        httpstr = httpstr.replace("start", "stop")
                        time.sleep(0.5)
                        r = requests.get(httpstr)

                rep0 = rep0 + ": " + ptzstr
            except Exception as e:
                # self.set_ptz(-1, "x")
                rep0 = "Ptz error: " + str(e)

        elif r0s0 == "ftplogin":
            rep0 = "Logging in to FTP server not implemented yet..."
            repname, repframe = None, None
        elif r0s0 == "photo":
            try:
                rep0 = "Sending photo via Telegram ..."
                repname, repframe, _, _, _ = shmlist[int(r0s[1].lower())]
            except:
                repname, repframe = None, None
                rep0 = "Wrong channel!"
        elif r0s0 == "quit":
            self.set_alarmquit()
            rep0 = "Exiting GUCK ..."
            logger.info("GUCK quit!")
        elif r0s0 == "status":
            answ, _, _, _, _ = getstatus(SHMLIST, self.recording(), self.alarmrunning())
            rep0 = answ
            logger.info("GUCK get status!")
        elif r0s0 == "record":
            try:
                r0s1 = r0s[1].lower()
                if r0s1 == "start":
                    res = self.set_recording(True)
                    if res:
                        rep0 = "Recording started!"
                    else:
                        rep0 = "Recording already running!"
                    logger.info("recording started")
                elif r0s1 == "stop":
                    res = self.set_recording(False)
                    if res:
                        rep0 = "Recording stopped!"
                    else:
                        rep0 = "Recording not running!"
                    logger.info("recording stopped")
                else:
                    rep0 = "unknown command " + r0s0 + " " + r0s1
            except:
                rep0 = "unknown command " + r0s0
        else:
            rep0 = "unknown command " + r0s0
        return rep0, repname, repframe


# Telegram Server

class TelegramServerV2(MessageHandler):
    def __init__(self, token, do_debug, chatid, initdata):
        MessageHandler.__init__(self, do_debug, initdata)
        self.TOKEN = token
        self.MESSAGE_ID = None
        self.init_telegram(chatid)

    def init_telegram(self, chatid):
        try:
            self.BOT = telepot.Bot(self.TOKEN)

            self.CHAT_ID = None
            if chatid != 0:

                self.CHAT_ID = chatid
                resp = self.BOT.getUpdates()
                if resp == []:
                    self.MESSAGE_ID = 0
                else:
                    resp0 = resp[-1]
                    self.MESSAGE_ID = resp0["message"]["message_id"]
                logger.info("Message id:" + str(self.MESSAGE_ID))
            else:
                resp = self.BOT.getUpdates()
                if resp == []:
                    logger.error("Cannot start Telegram, cannot obtain chat id")
                    self.BOT = None
                else:
                    try:
                        resp0 = resp[-1]
                        self.CHAT_ID = resp0["message"]["chat"]["id"]
                        self.MESSAGE_ID = resp0["message"]["message_id"]
                        logger.ifno("Message id:" + str(self.MESSAGE_ID))
                    except:
                        logger.error("Cannot start Telegram, cannot obtain chat id")
                        self.BOT = None
            if self.BOT:
                self.BOT.setWebhook()
                self.BOT.message_loop(self.loophandle)
        except:
            self.BOT = None
            logger.error("Cannot start telegram, either bot does not exist or you have to initiate chat with bot!")

    def loophandle(self, msg):
        content_type, chat_type, chat_id = telepot.glance(msg)
        if content_type != "text":
            logger.warning("Wrong telegram content type!")
            return
        msg0 = msg["text"]
        msgid = msg["message_id"]
        if not msgid > self.MESSAGE_ID:
            return
        self.msgid = msgid
        if self.CHAT_ID == None:
            try:
                self.CHAT_ID = chat_id
            except KeyError:
                logger.error("Cannot get Telegram chat id!")
                return
        rep0, repname, repfr = self.Manage(msg0.lower())
        self.sendtext(rep0)
        if repfr is not None:
            cv2.imwrite("alarmphoto.jpg", repfr)
            msg = "Photo from cam # " + repname
            self.sendtext(msg)
            self.sendphoto("alarmphoto.jpg")

    def sendtext(self, msg):
        txt = msg
        try:
            self.BOT.sendMessage(self.CHAT_ID, txt)
            return True
        except Exception as e:
            logger.error("Cannot send text msg, Telegram error!" + str(e))
            return False

    def sendphoto(self, fn):
        try:
            self.BOT.sendPhoto(self.CHAT_ID, open(fn, "rb"))
            return True
        except Exception as e:
            logger.error("Cannot send photo, Telegram error!" + str(e))
            return False


# Telegram send thread
class MsgSendThread(Thread):
    # self.FTP_SERVER_URL, self.FTP_USER, self.FTP_PASSWORD, self.FTP_DIR,self.FTP_SET_PASSIVE)
    def __init__(self, smtpserver, mailfrom, mailto, bot, chatids, ftptuple):
        Thread.__init__(self)
        self.daemon = True
        self.MAIL_FROM = mailfrom
        self.MAIL_TO = mailto
        self.SMTPSERVER = smtpserver
        self.CHATIDS = chatids
        self.BOT = bot

        # FTP
        self.FTP = None
        if ftptuple != None:
            self.FTP_URL, self.FTP_USER, self.FTP_PASSWORD, self.FTP_DIR, self.FTP_PASSIVE = ftptuple
            self.FTP_RETRY = 0          # max. 5
            self.FTP = FTPServer(self.FTP_URL, self.FTP_USER, self.FTP_PASSWORD, self.FTP_DIR, self.FTP_PASSIVE)

        self.MSGQUEUE = []
        self.SEMAPHORE2 = posix_ipc.Semaphore("/guck_semaphore2", posix_ipc.O_CREAT)
        self.SEMAPHORE2.release()

    def sendstatus(self, proto, subj, msg, param):
        self.SEMAPHORE2.acquire()
        self.MSGQUEUE.append((proto, subj, msg, "status", param))
        self.SEMAPHORE2.release()

    def sendtext(self, proto, subj, msg, param):
        self.SEMAPHORE2.acquire()
        self.MSGQUEUE.append((proto, subj, msg, "text", param))
        self.SEMAPHORE2.release()

    def sendphoto(self, proto, subj, msg, param):
        self.SEMAPHORE2.acquire()
        self.MSGQUEUE.append((proto, subj, msg, "photo", param))
        self.SEMAPHORE2.release()

    def run(self):
        global SHMLIST
        while True:
            if len(self.MSGQUEUE) > 0:
                self.SEMAPHORE2.acquire()
                proto, subj, msg, msgtype, param = self.MSGQUEUE.pop(0)
                self.SEMAPHORE2.release()
                if proto == "telegram":
                    if msgtype == "text":
                        try:
                            for c in self.CHATIDS:
                                self.BOT.sendMessage(c, msg)
                        except Exception as e:
                            logger.error("Error in sending Telegram text msg: " + str(e))
                    elif msgtype == "status":
                        recording, alarmrunning = param
                        rep0 = "*** HEARTBEAT ***\n"
                        answ, _, _, _, _ = getstatus(SHMLIST, recording, alarmrunning)
                        rep0 += answ
                        try:
                            for c in self.CHATIDS:
                                self.BOT.sendMessage(c, rep0)
                        except Exception as e:
                            logger.error("Error in sending Telegram heartbeat msg: " + str(e))
                    elif msgtype == "photo":
                        try:
                            for c in self.CHATIDS:
                                self.BOT.sendPhoto(c, open(msg, "rb"))
                        except Exception as e:
                            logger.error("Error in sending photo via Telegram: " + str(e))
                elif proto == "ftp" and self.FTP:
                    # only file upload
                    try:
                        if not self.FTP.FTPOK and self.FTP_RETRY < 6:
                            del self.FTP
                            self.FTP = None
                            self.FTP = FTPServer(self.FTP_URL, self.FTP_USER, self.FTP_PASSWORD, self.FTP_DIR, self.FTP_PASSIVE)
                            self.FTP_RETRY += 1
                        if self.FTP.FTPOK:
                            fp = open(msg, "rb")
                            self.FTP.FTPC.storbinary("STOR " + subj, fp)
                            fp.close()
                            self.FTP_RETRY = 0
                    except Exception as e:
                            logger.error("Error in FTP upload: " + str(e))
                            self.FTP.FTPOK = False

                elif proto == "smtp":
                    if msgtype == "text":
                        try:
                            msg0 = MIMEText(msg)
                            msg0["Subject"] = subj
                            msg0["From"] = self.MAIL_FROM
                            msg0["To"] = self.MAIL_TO
                            msg0["Date"] = formatdate(localtime=1)
                            self.SMTPSERVER.send_message(msg0)
                        except Exception as e:
                            logger.error("Error in sending e-mail: " + str(e))
                    elif msgtype == "status":
                        try:
                            recording, alarmrunning = param
                            rep0 = "*** HEARTBEAT ***\n"
                            answ, _, _, _, _ = getstatus(SHMLIST, recording, alarmrunning)
                            rep0 += answ
                            msg0 = MIMEText(rep0)
                            msg0["Subject"] = subj
                            msg0["From"] = self.MAIL_FROM
                            msg0["To"] = self.MAIL_TO
                            msg0["Date"] = formatdate(localtime=1)
                            self.SMTPSERVER.send_message(msg0)
                        except Exception as e:
                            logger.error("Error in sending Telegram heartbeat msg: " + str(e))
                    elif msgtype == "photo":
                        try:
                            msg0 = MIMEMultipart()
                            msg0["Subject"] = subj
                            msg0["From"] = self.MAIL_FROM
                            msg0["To"] = self.MAIL_TO
                            msg0["Date"] = formatdate(localtime=1)
                            body = MIMEText("Hi, I detected an object moving around ...")
                            msg0.attach(body)
                            fp = open(msg, "rb")
                            att = MIMEImage(fp.read(), _subtype="jpg")
                            #   MIMEApplication(fp.read())
                            fp.close()
                            att.add_header("Content-Disposition", "attachment", filename=msg)
                            msg0.attach(att)
                            self.SMTPSERVER.sendmail(self.MAIL_FROM, self.MAIL_TO, msg0.as_string())
                            time.sleep(1)
                        except Exception as e:
                            logger.error("Error in sending photo via e-mail: " + str(e))
            time.sleep(0.01)


# WastlAlarmServer
class WastlAlarmServer(Thread):
    def __init__(self, lock):
        Thread.__init__(self)
        self.daemon = True
        self.port = "7001"
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:7001")
        self.lock = lock
        self.inqueue = []

    def pop(self):
        if len(self.inqueue) > 0:
            with self.lock:
                ret, r = True, self.inqueue.pop()
        else:
            ret, r = False, None
        return ret, r

    def push(self, p):
        with self.lock:
            if len(self.inqueue) > 10:
                del self.inqueue[0]
            self.inqueue.append(dill.dumps(p))

    def run(self):
        while True:
            self.socket.recv_string()
            ret, r = self.pop()
            self.socket.send_pyobj((ret, r))


# SSH Server
class SSHServer(Thread, MessageHandler):

    def __init__(self, do_debug, initdata, lock):
        Thread.__init__(self)
        MessageHandler.__init__(self, do_debug, initdata)
        self.daemon = True
        self.port = "5558"
        self.context = zmq.Context()
        self.LOCK = lock
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:%s" % self.port)

    def run(self):
        while True:
            #  Wait for next request from client
            req0 = self.socket.recv_string()
            with self.LOCK:
                rep0, repname, repfr = self.Manage(req0.lower())
            self.socket.send_pyobj((rep0, repname, repfr))
            logger.info("SSHServer received: " + str(req0))
            logger.info("SSHServer answer sent")


# FTP Server (=Client)
class FTPServer:
    def __init__(self, url, user, passwd, dir, passive):
        self.URL = url
        self.USER = user
        self.PASSWD = passwd
        self.DIR = dir
        self.PASSIVE = passive
        self.FTPC = None
        self.FTPOK = False
        self.login()

    def login(self):
        try:
            self.FTPC = ftplib.FTP(self.URL)
            self.FTPC.login(self.USER, self.PASSWD)
            self.FTPC.set_pasv(self.PASSIVE)
            self.FTPC.cwd(self.DIR)
            self.FTPOK = True
        except Exception as e:
            logger.error("FTP login error: " + str(e))
            self.FTPOK = False

    def logout(self):
        self.FTPC.quit()


# SMTP server
class SMTPServer:

        def __init__(self, mailfrom, mailto, addr, port, user, password):
            self.MAIL_FROM = mailfrom
            self.MAIL_TO = mailto
            self.SMTPADDR = addr
            self.SMTPPORT = port
            self.MAIL_USER = user
            self.MAIL_PASSWORD = password
            self.MAILOK = True
            self.QUEUE = queue.Queue()
            self.LASTTIME_TS = 0
            try:
                self.SMTPSERVER = smtplib.SMTP(self.SMTPADDR + ":" + str(self.SMTPPORT))
                self.SMTPSERVER.ehlo()
                self.SMTPSERVER.starttls()
                self.SMTPSERVER.ehlo()
                self.SMTPSERVER.login(self.MAIL_USER, self.MAIL_PASSWORD)
            except:
                self.MAILOK = False

        def getstatus(self):
            overall_mem = round(psutil.virtual_memory()[0] / float(2 ** 20) / 1024,2)
            free_mem = round(psutil.virtual_memory()[1] / float(2 ** 20) / 1024,2)
            used_mem = round(overall_mem - free_mem, 2)
            perc_used = round((used_mem / overall_mem) * 100, 2)
            cpu_perc = psutil.cpu_percent(interval=0.25,percpu=False)
            ret = "RAM: " + str(perc_used) + "% ( =" + str(used_mem) + " GB) of overall " + str(overall_mem) + \
                    " GB used"
            ret += "\nCPU: " + str(cpu_perc) + "% utilized"
            return ret

        def close(self):
            self.SMTPSERVER.close()

        def sendmail(self, subj, msgx):
            try:
                msg = MIMEText(msgx)
                msg["Subject"] = subj
                msg["From"] = self.MAIL_FROM
                msg["To"] = self.MAIL_TO
                msg["Date"] = formatdate(localtime=1)
                self.SMTPSERVER.send_message(msg)
                return True
            except:
                return False

if __name__ == "__main__":
    pass
