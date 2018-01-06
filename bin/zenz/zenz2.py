import sys
sys.path.append("../../lib")

import cv2 
import time 
import zmq
import paramiko
import subprocess
import os
import posix_ipc
import configparser
import logging
import sensors
import psutil
from paramiko import SSHClient
import guckmongo
import zenzlib
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters
import signal
import sys
import sseclient   # Achtung: sseclient-py !!!
import urllib3
import http
from urllib.parse import urlparse
import certifi
from threading import Thread
import json
import zmq
import dill
import telepot

UPDATER = None
NESTSS = None

# try to get config & DB
try:
    dbconfig = configparser.ConfigParser()
    dbconfig.read("../../data/mongo_default/mongo_url.cfg")
    dburl = dbconfig["CONFIG"]["DB_URL"].rstrip()
    dbname = dbconfig["CONFIG"]["DB_NAME"].rstrip()
    DB = guckmongo.ConfigDB(dburl, dbname)
except Exception as e:
    print(str(e) + ": Cannot get ZENZ config for DB, exiting ...")
    sys.exit()

# NEST
urllib3.disable_warnings()
NEST_API_URL = "https://developer-api.nest.com"
NESTTOKEN = DB.db_query("nest", "token")

# get & set GUCK_HOME
try:
        _guck_home = DB.db_query("basic", "guck_home")
except Exception as e:
        print("Mongo DB Error(" + str(e) + "), quitting ...")
        sys.exit()
if _guck_home == -1:
        print("Mongo DB Error, quitting ...")
        sys.exit()
if _guck_home[-1] != "/":
        _guck_home += "/"

# replace for ubuntuserver
#guck_home = _guck_home.replace("/nfs/NFS_Projekte/", "/nfs_neu/")

# for ubuntuvm1
guck_home = _guck_home.replace("/nfs/NFS_Projekte/", "/nfs/")

#guck_home = _guck_home
#print(guck_home)
os.environ["GUCK_HOME"] = guck_home
GUCK_HOME = os.environ["GUCK_HOME"]


def sighandler(signum, frame):
    global NESTSS
    NESTSS.STATUS = -2


def send_to_guck(bot, update):
    update.message.reply_text("Don't know what to do with:" + update.message.text)


ZENZ_RUNNING = True


def chandler(bot, update):
    global REMOTE_HOST
    global REMOTE_HOST_MAC
    global INTERFACE
    global REMOTE_PORT
    global REMOTE_HOST_SHORT
    global REMOTE_SSH_PORT
    global GUCK_PATH
    global REMOTE_VIRTUALENV
    global ZENZL
    msg0 = update.message.text.lower()
    if msg0[:2] == "g.":
        if msg0[2:] == "stop" or msg0[2:] == "shutdown":
            ZENZL.killguck()
            update.message.reply_text("Killing guck on " + REMOTE_HOST_SHORT)
            if msg0[2:] == "shutdown":
                ZENZL.shutdown()
                update.message.reply_text("Shutting down " + REMOTE_HOST_SHORT)
        elif msg0[2:] == "ping":
            stat, ping_rep = ZENZL.ping()
            if stat == 0 or stat == 1:
                update.message.reply_text(ping_rep)
            else:
                update.message.reply_text("Error in ping to guck host: " + ping_rep)
        elif msg0[2:] == "start" or msg0[2:] == "restart":
            stat, ping_rep = ZENZL.ping()
            if stat == 0:
                ZENZL.lanwake()
                update.message.reply_text(ping_rep)
                update.message.reply_text("Guck host down, now booting up via WOL, pls try again in 1 min ...")
                return
            elif stat == 1:
                noservers = ZENZL.get_nr_instances()
                if noservers > 0:
                    ZENZL.killguck()
                    update.message.reply_text("Killing guck on " + REMOTE_HOST_SHORT)
                try:
                    ZENZL.startguck()
                    logger.info("Starting guck at: " + REMOTE_HOST_SHORT)
                    update.message.reply_text("Starting Guck, hope it works ... ;-)")
                except Exception as e:
                    update.message.reply_text("Error in guck start up: " + str(e))
            else:
                update.message.reply_text("Error in ping to guck host:" + ping_rep)
                return
        else:
            sendtext_toGuck(msg0[2:], bot, update, REMOTE_HOST, REMOTE_PORT)
    elif msg0[:4] == "bot.":
        logger.info("Received bot msg:" + msg0)
        if msg0[4:] == "exit":
            update.message.reply_text("Exiting Telegram Server, byebye!")
            logger.info("Killing Zenz!")
            global ZENZ_RUNNING
            ZENZ_RUNNING = False
            time.sleep(100)
        elif msg0[4:] == "status":
            logger.info("Status start")
            overall_mem = round(psutil.virtual_memory()[0] / float(2 ** 20) / 1024, 2)
            free_mem = round(psutil.virtual_memory()[1] / float(2 ** 20) / 1024, 2)
            used_mem = round(overall_mem - free_mem, 2)
            perc_used = round((used_mem / overall_mem) * 100, 2)
            cpu_perc = psutil.cpu_percent(interval=0.25, percpu=False)
            ret = "\nRAM: " + str(perc_used) + "% ( =" + str(used_mem) + " GB) of overall " + str(overall_mem) + " GB used"
            ret += "\nCPU: " + str(cpu_perc) + "% utilized"
            logger.info("status comp. finished, sending ...")
            update.message.reply_text(ret)
        else:
            update.message.reply_text("Do not know this bot command!")
    elif msg0[:5] == "nest.":
        logger.info("Received net msg:" + msg0)
        if msg0[5:] == "status":
            global CONNECTOR
            stat, txt = send_to_connector("nest", "getstatus", "")
            if stat:
                update.message.reply_text(txt)
            else:
                update.message.reply_text("Cannot get NEST status")
    else:
        update.message.reply_text("Don't know what to do with: " + msg0)


def send_to_connector(msgtype, typ, obj0, port="7014"):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        host = "localhost"
        socket.setsockopt(zmq.LINGER, 0)
        socketurl = "tcp://" + host + ":" + port
        socket.connect(socketurl)
        socket.RCVTIMEO = 1000
        try:
            socket.send_pyobj((msgtype, typ, dill.dumps(obj0)))
            oknok = socket.recv_string()
            socket.close()
            context.term()
            return True, oknok
        except zmq.ZMQError as e:
            logger.error("Send to connector: " + str(e))
            socket.close()
            context.term()
            time.sleep(0.1)
            return False


def sendtext_toGuck(msg, bot, update, host, port):
    # port = "5558"
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socketurl = "tcp://" + host + ":" + port
    socket.connect(socketurl)
    socket.RCVTIMEO = 1000
    socket.send_string(msg)
    try:
        rep0, repname, repfr = socket.recv_pyobj()
        socket.close()
        context.term()
        update.message.reply_text(rep0)
        if repfr is not None:
            cv2.imwrite("alarmphoto.jpg", repfr)
            msg = "Photo from cam # " + repname
            update.message.reply_text(msg)
            update.message.reply_photo(open("alarmphoto.jpg", "rb"))
        return True
    except zmq.ZMQError as e:
        msg0 = str(e)
        update.message.reply_text(msg0)
        msg0 = "Cannot send text msg, Telegram error!"
        update.message.reply_text(msg0)
        socket.close()
        context.term()
        time.sleep(0.1)
        return False


class Zenz_connector(Thread):
    def __init__(self, db, port="7014"):
        Thread.__init__(self)
        self.DB = db
        self.DATALIST = []
        try:
            self.do_telegram = self.DB.db_query("telegram", "do_telegram")
            self.telegram_token = self.DB.db_query("telegram", "token")
            self.telegram_chatids = [int(x) for x in self.DB.db_query("telegram", "chatidlist")]
            self.telegrambot = telepot.Bot(self.telegram_token)
        except Exception as e:
            logger.error("DB query error: " + str(e))
            self.do_telegram = False
        self.daemon = True
        self.port = port
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.REP)
        self.socket.bind("tcp://*:" + self.port)

    def get_data(self, msgtype):
        i = len(self.DATALIST)
        retdata = None
        while i > 0:
            typ, obj = self.DATALIST[i-1]
            if typ == msgtype:
                _, _, retdata = dill.loads(obj)
                break
            i -= 1
        if retdata:
            return 0, retdata
        else:
            return -1, None

    def run(self):
        while True:
            try:
                msgtype, typ, obj0 = self.socket.recv_pyobj()
                # NEST handler
                newmsg = None
                if msgtype == "nest":
                    # prepare text
                    if typ == "send":
                        status_changed, device_changed, nestlist = dill.loads(obj0)
                        newmsg = "*** NEST ***\n\n"
                        if status_changed != []:
                            newmsg += "STRUCTURE STATUS UPDATES:\n"
                            for ss0 in status_changed:
                                nm, it, st = ss0
                                newmsg += nm
                                if it == "new_structure":
                                    newmsg += ": NEW\n"
                                if it == "away":
                                    newmsg += ": Away (" + st.upper() + ")\n"
                            if device_changed != []:
                                newmsg += "\n"
                        if device_changed != []:
                            newmsg += "DEVICE STATUS UPDATES:\n"
                            for dd0 in device_changed:
                                nm, lc, it, st = dd0
                                newmsg += nm + " - " + lc + ": "
                                if it == "co_alarm_state":
                                    newmsg += "CO2 (" + st.upper() + ")\n"
                                if it == "smoke_alarm_state":
                                    newmsg += "smoke (" + st.upper() + ")\n"
                                if it == "battery_health":
                                    newmsg += "energy (" + st.upper() + ")\n"
                        self.DATALIST.append((msgtype, dill.dumps((status_changed, device_changed, nestlist))))
                        # send text to telegram, mail, ftp, sms etc
                        if self.do_telegram and newmsg:
                            for c in self.telegram_chatids:
                                self.telegrambot.sendMessage(c, newmsg)
                        # server answer depends of msgtype
                        self.socket.send_string("OK")
                    elif typ == "getstatus":
                        stat, nestlist = self.get_data("nest")
                        newmsg = "*** NEST ***\n"
                        if stat == 0:
                            newmsg += "\nSTRUCTURE STATUS:"
                            for structure in nestlist:
                                newmsg += "\nName: " + structure["name"] + "\n"
                                newmsg += "Away: " + structure["away"].upper() + "\n"
                                newmsg += "CO2:  " + structure["co_alarm_state"].upper() + "\n"
                                newmsg += "Smoke:" + structure["smoke_alarm_state"].upper() + "\n"
                                newmsg += "\nDEVICE STATUS:\n"
                                for item in structure["locations"]:
                                    newmsg += item["name"] + "\n"
                                    newmsg += "   CO2:    " + item["co_alarm_state"].upper() + "\n"
                                    newmsg += "   Smoke:  " + item["smoke_alarm_state"].upper() + "\n"
                                    newmsg += "   Energy: " + item["battery_health"].upper() + "\n"
                        self.socket.send_string(newmsg)
            except Exception as e:
                logger.error(str(e))
                try:
                    self.socket.send_string("NOOK")
                except Exception as e:
                    logger.error(str(e))
            if len(self.DATALIST) > 200:
                del self.DATALIST[0]
            time.sleep(0.2)


class Nest_sse(Thread):
    def __init__(self, token, api_endpoint):
        Thread.__init__(self)
        self.daemon = True
        self.TOKEN = token
        self.API_ENDPOINT = api_endpoint
        self.STATUS = 1
        self.client = None
        self.NESTLIST = []
        self.OLDNESTLIST = []
        self.STRUCTURE_STATUS_CHANGED = []
        self.DEVICE_STATUS_CHANGED = []

    # compares NESTLIST to OLDNESTLIST and returns differences:
    #     "away" status per structure
    #     "co_alarm_state", "smoke_alarm_state", "battery_health" per device
    def check_status(self):
        ssch = []
        dsch = []
        statuschanged = False
        for n0 in self.NESTLIST:
            locationfound = False
            for n1 in self.OLDNESTLIST:
                if n1["name"] == n0["name"]:
                    locationfound = True
                    if n1["away"] != n0["away"]:
                        ssch.append((n1["name"], "away", n0["away"]))
                        statuschanged = True
                    for ln0 in n0["locations"]:
                        devicefound = False
                        for ln1 in n1["locations"]:
                            if ln0["name"] == ln1["name"]:
                                devicefound = True
                                if ln0["co_alarm_state"] != ln1["co_alarm_state"]:
                                    statuschanged = True
                                    dsch.append((n1["name"], ln1["name"], "co_alarm_state", ln0["co_alarm_state"]))
                                if ln0["smoke_alarm_state"] != ln1["smoke_alarm_state"]:
                                    statuschanged = True
                                    dsch.append((n1["name"], ln1["name"], "smoke_alarm_state", ln0["smoke_alarm_state"]))
                                if ln0["battery_health"] != ln1["battery_health"]:
                                    statuschanged = True
                                    dsch.append((n1["name"], ln1["name"], "battery_health", ln0["battery_health"]))
                        if not devicefound:
                            statuschanged = True
                            dsch.append((n1["name"], ln0["name"], "new_device", ""))
                            dsch.append((n1["name"], ln0["name"], "co_alarm_state", ln0["co_alarm_state"]))
                            dsch.append((n1["name"], ln0["name"], "smoke_alarm_state", ln0["smoke_alarm_state"]))
                            dsch.append((n1["name"], ln0["name"], "battery_health", ln0["battery_health"]))
            if not locationfound:
                statuschanged = True
                ssch.append((n0["name"], "new_structure", ""))
                ssch.append((n0["name"], "away", n0["away"]))
                for ln0 in n0["locations"]:
                    dsch.append((n0["name"], ln0["name"], "co_alarm_state", ln0["co_alarm_state"]))
                    dsch.append((n0["name"], ln0["name"], "smoke_alarm_state", ln0["smoke_alarm_state"]))
                    dsch.append((n0["name"], ln0["name"], "battery_health", ln0["battery_health"]))
        self.STRUCTURE_STATUS_CHANGED = ssch
        self.DEVICE_STATUS_CHANGED = dsch
        return statuschanged

    def update_status(self, eventdata):
        try:
            nestlist = []
            structures = eventdata["data"]["structures"]
            for key, s in structures.items():
                structure = {}
                structure["name"] = s["name"]
                structure["away"] = s["away"]
                structure["co_alarm_state"] = s["co_alarm_state"]
                structure["smoke_alarm_state"] = s["smoke_alarm_state"]
                structure["locations"] = []
                for location in s["smoke_co_alarms"]:
                    loc = {}
                    s0 = eventdata["data"]["devices"]["smoke_co_alarms"][location]
                    loc["name"] = s0["name"]
                    loc["co_alarm_state"] = s0["co_alarm_state"]
                    loc["smoke_alarm_state"] = s0["smoke_alarm_state"]
                    loc["battery_health"] = s0["battery_health"]
                    structure["locations"].append(loc)
                nestlist.append(structure)
            self.OLDNESTLIST = self.NESTLIST
            self.NESTLIST = nestlist
            return True
        except Exception as e:
            logger.error("Nest update: " + str(e))
            return False

    def run(self):
        headers0 = {
            'Authorization': "Bearer " + self.TOKEN,
            'Accept': 'text/event-stream'
        }
        url = self.API_ENDPOINT

        # Test for redirect
        conn = http.client.HTTPSConnection("developer-api.nest.com")
        headers = {'authorization': "Bearer {0}".format(self.TOKEN)}
        conn.request("GET", "/", headers=headers)
        response = conn.getresponse()
        if response.status == 307:
            redirectLocation = urlparse(response.getheader("location"))
            conn = http.client.HTTPSConnection(redirectLocation.netloc)
            conn.request("GET", "/", headers=headers)
            response = conn.getresponse()
            if response.status != 200:
                self.STATUS = -2
                logger.error("Cannot connect to NEST, redirect with non 200 response, aborting ...")
                return
            url = "https://" + redirectLocation.netloc

        http0 = urllib3.PoolManager(cert_reqs='CERT_REQUIRED', ca_certs=certifi.where())
        response = http0.request('GET', url, headers=headers0, preload_content=False)

        if response.status != 200:
            self.STATUS = -2,
            logger.error("Cannot connect to redirected NEST, aborting ...")
            return
        try:
            self.client = sseclient.SSEClient(response)
        except Exception as e:
            self.STATUS = -2,
            logger.error(str(e))
        logger.info("NEST: Connected to " + url)
        self.STATUS = 1
        logger.info("Waiting for NEST events ...")

        self.smokeco = None
        self.away = None

        for event in self.client.events():  # returns a generator
            try:
                event_type = event.event
                # print("event: ", event_type)
                if event_type == 'open':  # not always received here
                    print("The event stream has been opened")
                elif event_type == 'put':
                    eventdata = json.loads(event.data)
                    self.update_status(eventdata)
                    if self.check_status():
                        logger.info("Nest status has changed, communicating ...")
                        send_to_connector("nest", "send", (self.STRUCTURE_STATUS_CHANGED, self.DEVICE_STATUS_CHANGED, self.NESTLIST))
                elif event_type == 'keep-alive':
                    pass
                elif event_type == 'auth_revoked':
                    # print("revoked token: ", event.data)
                    raise Exception("AUTH ERROR")
                elif event_type == 'error':
                    raise Exception(str(event.data))
                else:
                    raise Exception("unknown event, no handler for it")
            except Exception as e:
                if str(e) == "AUTH_ERROR":
                    self.STATUS = -2
                    logger.error("Nest loop error: " + str(e))
                else:
                    self.STATUS = -1
                    logger.warning("Nest loop warning: " + str(e))


if __name__ == '__main__':
    ln = "zenz"
    logger = logging.getLogger(ln)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(GUCK_HOME + "/log/zenz.log", mode="w")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info("Starting zenz2.py ...")
    logger.info("GUCK_HOME on zenz server: " + GUCK_HOME)

    # Get Config from DB
    TOKEN = DB.db_query("telegram", "token")
    CHATIDLIST = [int(x) for x in DB.db_query("telegram", "chatidlist")]
    GUCK_PATH = DB.db_query("remote", "guck_path")
    logger.info("GUCK_HOME on remote host for startup: " + GUCK_PATH)
    REMOTE_HOST = DB.db_query("remote", "remote_host")
    REMOTE_HOST_SHORT = DB.db_query("remote", "remote_host_short")
    REMOTE_PORT = DB.db_query("remote", "remote_port")
    REMOTE_SSH_PORT = DB.db_query("remote", "remote_ssh_port")
    REMOTE_HOST_MAC = DB.db_query("remote", "remote_host_mac")
    INTERFACE = DB.db_query("remote", "interface")
    REMOTE_VIRTUALENV = DB.db_query("remote", "remote_virtualenv")

    ZENZL = zenzlib.ZenzLib(REMOTE_HOST, REMOTE_HOST_MAC, INTERFACE, REMOTE_PORT, REMOTE_HOST_SHORT, REMOTE_SSH_PORT,
                            GUCK_PATH, REMOTE_VIRTUALENV)

    # Start Telegram bot
    UPDATER = Updater(TOKEN)
    dp = UPDATER.dispatcher
    dp.add_handler(MessageHandler(Filters.text, chandler))

    # Start Connector
    CONNECTOR = Zenz_connector(DB)
    CONNECTOR.start()

    # Start Nest
    logger.info("(Re)Connecting to NEST ...")
    NESTSS = Nest_sse(NESTTOKEN, NEST_API_URL)
    NESTSS.start()

    # Ctrl+C Handler
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)
    signal.signal(signal.SIGABRT, sighandler)
    signal.signal(signal.SIGALRM, sighandler)

    # Start Telegram
    logger.info("Starting Telegram bot ...")
    UPDATER.start_polling()

    # Loop for threading
    while ZENZ_RUNNING and NESTSS.STATUS != -2:
        time.sleep(1)

    # The end is near ...
    logger.warning("Telegram shutting down ...")
    UPDATER.stop()
    logger.warning("NEST shutting down ...")
    NESTSS.client.close()
    logger.warning("ZENZ ausmaus!!")
