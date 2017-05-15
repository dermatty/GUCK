# Telegram Server

import sys
sys.path.append("../../lib")

# direkter start-up:
#       /home/stephan/.virtualenvs/cvp0/bin/python /media/nfs/PycharmProjects/guck2.0/ts.py
# als alias auf ubuntuserver.iv.at in ~/.bashrc:
#     alias telegramserver='/home/stephan/.virtualenvs/cvp0/bin/python
#     /media/nfs/PycharmProjects/guck2.0/ts.py >/dev/null 2>&1 &'
# als telegramserver.sh auf ubuntuserver.iv.at (/home/stephan/telegramserver.sh)
#

import cv2 
import telepot 
from telepot.loop import MessageLoop
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

SEMAPHORE_NAME = "/tpsemaphore1"

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
guck_home = _guck_home.replace("/nfs/NFS_Projekte/", "/nfs/")
os.environ["GUCK_HOME"] = guck_home
GUCK_HOME = os.environ["GUCK_HOME"]


def telegram_init():
    global BOT
    global TOKEN
    global CHATIDLIST
    global UPDATEID
    try:
        BOT = telepot.Bot(TOKEN)
        logger.info("Connected to Telegram bot!")
        msg = BOT.getUpdates(timeout=5)
        while msg != []:
            UPDATEID = msg[0]["update_id"]
            UPDATEID += 1
            msg = BOT.getUpdates(offset=UPDATEID)
        for i in CHATIDLIST:
            print(i)
            BOT.sendMessage(i, "Telegram server started!")
        MessageLoop(BOT, loophandle).run_as_thread()
        logger.info("Telegram MessageLoop thread started")
    except Exception as e:
        BOT = None
        logger.error("Cannot start telegram error: " + str(e))
        sys.exit()


def loophandle(msg):
    global REMOTE_HOST
    global REMOTE_HOST_MAC
    global INTERFACE
    global REMOTE_PORT
    global REMOTE_HOST_SHORT
    global REMOTE_SSH_PORT
    global GUCK_PATH
    global REMOTE_VIRTUALENV
    global ZENZL
    global running
    content_type, chat_type, chatid = telepot.glance(msg)
    if content_type != "text":
        logger.error("Wrong telegram content type!")
        BOT.sendMessage(chatid, "Starting Guck, hope it works ... ;-)")
        return
    msg0 = msg["text"].lower()
    if msg0[:2] == "g.":
        if msg0[2:] == "stop" or msg0[2:] == "shutdown":
            ZENZL.killguck()
            for c in CHATIDLIST:
                BOT.sendMessage(c, "Killing guck on " + REMOTE_HOST_SHORT)
            if msg0[2:] == "shutdown":
                ZENZL.shutdown()
                for c in CHATIDLIST:
                    BOT.sendMessage(c, "Shutting down " + REMOTE_HOST_SHORT)
        elif msg0[2:] == "ping":
            stat, ping_rep = ZENZL.ping()
            if stat == 0 or stat == 1:
                BOT.sendMessage(chatid, ping_rep)
            else:
                BOT.sendMessage(chatid, "Error in ping to guck host: " + ping_rep)
        elif msg0[2:] == "start" or msg0[2:] == "restart":
            stat, ping_rep = ZENZL.ping()
            if stat == 0:
                ZENZL.lanwake()
                BOT.sendMessage(chatid, ping_rep)
                BOT.sendMessage(chatid, "Guck host down, now booting up via WOL, pls try again in 1 min ...")
                return
            elif stat == 1:
                noservers = ZENZL.get_nr_instances()
                if noservers > 0:
                    ZENZL.killguck()
                    for c in CHATIDLIST:
                        BOT.sendMessage(c, "Killing guck on " + REMOTE_HOST_SHORT)
                try:
                    ZENZL.startguck()
                    logger.info("Starting guck at: " + REMOTE_HOST_SHORT)
                    for c in CHATIDLIST:
                        BOT.sendMessage(c, "Starting Guck, hope it works ... ;-)")
                except Exception as e:
                    for c in CHATIDLIST:
                        BOT.sendMessage(c, "Error in guck start up: " + str(e))
            else:
                BOT.sendMessage(chatid, "Error in ping to guck host:" + ping_rep)
                return
        else:
            res = sendtext_toGuck(msg0[2:], chatid, REMOTE_HOST, REMOTE_PORT)
    elif msg0[:4] == "bot.":
        print(msg0)
        if msg0[4:] == "exit":
            SEMAPHORE.acquire()
            running = False
            BOT.sendMessage(chatid, "Exiting Telegram Server, byebye!")
            SEMAPHORE.release()
        elif msg0[4:] == "status":
            overall_mem = round(psutil.virtual_memory()[0] / float(2 ** 20) / 1024, 2)
            free_mem = round(psutil.virtual_memory()[1] / float(2 ** 20) / 1024, 2)
            used_mem = round(overall_mem - free_mem, 2)
            perc_used = round((used_mem / overall_mem) * 100, 2)
            cpu_perc = psutil.cpu_percent(interval=0.25, percpu=False)
            ret = "\nRAM: " + str(perc_used) + "% ( =" + str(used_mem) + " GB) of overall " + str(overall_mem) + " GB used"
            ret += "\nCPU: " + str(cpu_perc) + "% utilized"
            BOT.sendMessage(chatid, ret)
        else:
            BOT.sendMessage(chatid, "Do not know this bot command!")
    else:
        BOT.sendMessage(chatid, "Don't know what to do with: "+msg0)
    time.sleep(0.05)


def sendtext_toGuck(msg, chatid, host, port):
    global BOT
    # port = "5558"
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socketurl = "tcp://" + host + ":" + port
    socket.connect(socketurl)
    socket.RCVTIMEO = 1000
    a = socket.send_string(msg)
    try:
        rep0, repname, repfr = socket.recv_pyobj()
        socket.close()
        context.term()
        BOT.sendMessage(chatid, rep0)
        if repfr is not None:
            cv2.imwrite("alarmphoto.jpg", repfr)
            msg = "Photo from cam # " + repname
            BOT.sendMessage(chatid, msg)
            BOT.sendPhoto(chatid, open("alarmphoto.jpg", "rb"))
        return True
    except zmq.ZMQError as e:
        msg0 = str(e)
        BOT.sendMessage(chatid, msg0)
        msg0 = "Cannot send text msg, Telegram error!"
        BOT.sendMessage(chatid, msg0)
        socket.close()
        context.term()
        time.sleep(0.1)
        return False


if __name__ == "__main__":
    SEMAPHORE = posix_ipc.Semaphore(SEMAPHORE_NAME, posix_ipc.O_CREAT)
    SEMAPHORE.release()
    ln = "zenz"
    logger = logging.getLogger(ln)
    logger.setLevel(logging.INFO)
    fh = logging.FileHandler(GUCK_HOME + "/log/zenz.log", mode="w")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info("Starting zenz.py ...")
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
    BOT = None
    telegram_init()
    if BOT is None:
        logger.info("Exiting zenz.py, cannot init bot ...")
        sys.exit()
    running = True

    logger.info("Entering service loop ...")

    while running:
        time.sleep(5)

    logger.info("zenz.py terminated!")
