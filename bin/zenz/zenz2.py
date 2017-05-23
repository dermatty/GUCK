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
# guck_home = _guck_home
os.environ["GUCK_HOME"] = guck_home
GUCK_HOME = os.environ["GUCK_HOME"]


def send_to_guck(bot, update):
    update.message.reply_text("Don't know what to do with:" + update.message.text)


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
            sys.exit()
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
    else:
        update.message.reply_text("Don't know what to do with: " + msg0)


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


if __name__ == '__main__':
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

    # Create the EventHandler and pass it your bot's token.
    updater = Updater(TOKEN)

    # Get the dispatcher to register handlers
    dp = updater.dispatcher

    # on different commands - answer in Telegram
    # dp.add_handler(CommandHandler("g.ping", g_ping))
    # on noncommand i.e message - echo the message on Telegram
    dp.add_handler(MessageHandler(Filters.text, chandler))

    # log all errors
    # dp.add_error_handler(error)

    updater.start_polling()

    updater.idle()