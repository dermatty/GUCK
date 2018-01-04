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

#!!! guck_home = _guck_home.replace("/nfs/NFS_Projekte/", "/nfs/")
guck_home = _guck_home

#guck_home = _guck_home
#print(guck_home)
os.environ["GUCK_HOME"] = guck_home
GUCK_HOME = os.environ["GUCK_HOME"]


def sighandler(signum, frame):
    global UPDATER
    global NESTSS
    logger.warning("Telegram shutting down ...")
    UPDATER.stop()
    logger.warning("NEST shutting down ...")
    NESTSS.client.close()
    sys.exit()


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


class Nest_sse(Thread):
    def __init__(self, token, api_endpoint):
        Thread.__init__(self)
        self.daemon = True
        self.TOKEN = token
        self.API_ENDPOINT = api_endpoint
        self.STATUS = 1
        self.client = None

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
                print("event: ", event_type)
                if event_type == 'open':  # not always received here
                    print("The event stream has been opened")
                elif event_type == 'put':
                    print(event.data)
                    print("-" * 80)
                    eventdata = json.loads(event.data)
                    self.smokeco = eventdata["data"]["devices"]["smoke_co_alarms"]
                    print(self.smokeco)
                    # for sc in self.smokeco:
                    #    print(sc)
                    print("-" * 80)
                    self.away = eventdata["data"]["structures"]
                    print("AWAY:" + str(self.away))
                    print("-" * 80)
                elif event_type == 'keep-alive':
                    print("No data updates. Receiving an HTTP header to keep the connection open.")
                elif event_type == 'auth_revoked':
                    print("The API authorization has been revoked.")
                    print("revoked token: ", event.data)
                    raise Exception("AUTH ERROR")
                elif event_type == 'error':
                    print("Error occurred, such as connection closed.")
                    print("error message: ", event.data)
                    raise Exception(str(event.data))
                else:
                    print("Unknown event, no handler for it.")
            except Exception as e:
                print(str(e))
                if str(e) == "AUTH_ERROR":
                    self.STATUS = -2
                    logger.error(str(e))
                else:
                    self.STATUS = -1
                    logger.warning(str(e))


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
    ''''UPDATER = Updater(TOKEN)
    dp = UPDATER.dispatcher
    dp.add_handler(MessageHandler(Filters.text, chandler))

    # Start Nest
    logger.info("(Re)Connecting to NEST ...")
    NESTSS = Nest_sse(NESTTOKEN, NEST_API_URL)
    NESTSS.start()

    # Ctrl+C Handler
    signal.signal(signal.SIGINT, sighandler)
    signal.signal(signal.SIGTERM, sighandler)
    signal.signal(signal.SIGABRT, sighandler)

    # Start Telegram
    logger.info("Starting Telegram bot ...")
    UPDATER.start_polling()

    # Loop for threading
    while True:
        if NESTSS.STATUS == -1:
            logger.info("(Re)Connecting to NEST ...")
            sys.exit()
            # NESTSS.start()
        time.sleep(1)'''

    eventdata = {
        "path": "/",
        "data": {
            "devices": {
                        "smoke_co_alarms": {
                                "OLK-rC0gUkeZ9nH3no2m-iMePXBie9RS": {
                                        "locale": "de-DE",
                                        "structure_id": "f1iJ7Qyvwlr6dvj2MMhHl9VVSqYQ11gMpl1bfDYOESORRo7IkewcYw",
                                        "software_version": "3.1.3rc2",
                                        "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMZzpoeK5Bx1w",
                                        "device_id": "OLK-rC0gUkeZ9nH3no2m-iMePXBie9RS",
                                        "where_name": "Living Room",
                                        "name": "Living Room",
                                        "name_long": "Living Room Nest Protect",
                                        "is_online": True,
                                        "last_connection": "2018-01-04T15:26:06.053Z",
                                        "battery_health": "ok",
                                        "co_alarm_state": "ok",
                                        "smoke_alarm_state": "ok",
                                        "ui_color_state": "green",
                                        "is_manual_test_active": False
                                },
                                "OLK-rC0gUkf5bPX_UWv5ZiMePXBie9RS": {
                                        "locale": "de-DE",
                                        "structure_id": "f1iJ7Qyvwlr6dvj2MMhHl9VVSqYQ11gMpl1bfDYOESORRo7IkewcYw",
                                        "software_version": "3.1.3rc2",
                                        "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNsCOyEoZWFVQ",
                                        "device_id": "OLK-rC0gUkf5bPX_UWv5ZiMePXBie9RS",
                                        "where_name": "Kitchen",
                                        "name": "Kitchen",
                                        "name_long": "Kitchen Nest Protect",
                                        "is_online": True,
                                        "last_connection": "2018-01-04T13:41:51.842Z",
                                        "battery_health": "ok",
                                        "co_alarm_state": "ok",
                                        "smoke_alarm_state": "ok",
                                        "ui_color_state": "green",
                                        "is_manual_test_active": False,
                                        "last_manual_test_time": "2017-11-18T15:25:15.000Z"
                                },
                                "OLK-rC0gUkeHck1ZRKWMTiMePXBie9RS": {
                                        "locale": "de-DE",
                                        "structure_id": "f1iJ7Qyvwlr6dvj2MMhHl9VVSqYQ11gMpl1bfDYOESORRo7IkewcYw",
                                        "software_version": "3.1.3rc2",
                                        "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMLwv6tlzXDSA",
                                        "device_id": "OLK-rC0gUkeHck1ZRKWMTiMePXBie9RS",
                                        "where_name": "Upstairs",
                                        "name": "Upstairs",
                                        "name_long": "Upstairs Nest Protect",
                                        "is_online": False,
                                        "last_connection": "2018-01-04T16:12:35.386Z",
                                        "battery_health": "ok",
                                        "co_alarm_state": "ok",
                                        "smoke_alarm_state": "ok",
                                        "ui_color_state": "green",
                                        "is_manual_test_active": False
                                }
                        }
                }, "structures": {
                        "f1iJ7Qyvwlr6dvj2MMhHl9VVSqYQ11gMpl1bfDYOESORRo7IkewcYw": {
                                "smoke_co_alarms": [
                                        "OLK-rC0gUkeHck1ZRKWMTiMePXBie9RS",
                                        "OLK-rC0gUkeZ9nH3no2m-iMePXBie9RS",
                                        "OLK-rC0gUkf5bPX_UWv5ZiMePXBie9RS"
                                ],
                                "name": "Irenevalley",
                                "country_code": "AT",
                                "time_zone": "Europe/Vienna",
                                "away": "home",
                                "structure_id": "f1iJ7Qyvwlr6dvj2MMhHl9VVSqYQ11gMpl1bfDYOESORRo7IkewcYw",
                                "co_alarm_state": "ok",
                                "smoke_alarm_state": "ok",
                                "wheres": {
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNO5B7v05qhmtg": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNO5B7v05qhmtg",
                                                "name": "Backyard"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNOU_8peC6fWA": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNOU_8peC6fWA",
                                                "name": "Basement"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPMpn3YgTC99g": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPMpn3YgTC99g",
                                                "name": "Bedroom"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPORFC5S_Y9Bw": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPORFC5S_Y9Bw",
                                                "name": "Den"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNzXJpniTwnTw": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNzXJpniTwnTw",
                                                "name": "Dining Room"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNuPj2Hryy7pQ": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNuPj2Hryy7pQ",
                                                "name": "Downstairs"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNO34JrAO8pyWQ": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNO34JrAO8pyWQ",
                                                "name": "Driveway"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNcWYIXurQ5PQ": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNcWYIXurQ5PQ",
                                                "name": "Entryway"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPhTEG5J2d0Ww": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPhTEG5J2d0Ww",
                                                "name": "Family Room"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPHs3RyGDvR0w": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPHs3RyGDvR0w",
                                                "name": "Front Yard"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPlZyat9nNWqA": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPlZyat9nNWqA",
                                                "name": "Guest House"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNOAh5kWonxC_A": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNOAh5kWonxC_A",
                                                "name": "Guest Room"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNN4Gx8Pytzc-A": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNN4Gx8Pytzc-A",
                                                "name": "Hallway"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMRhAFGf17N0Q": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMRhAFGf17N0Q",
                                                "name": "Kids Room"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNsCOyEoZWFVQ": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNsCOyEoZWFVQ",
                                                "name": "Kitchen"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMZzpoeK5Bx1w": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMZzpoeK5Bx1w",
                                                "name": "Living Room"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPTP47grpjSwA": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNPTP47grpjSwA",
                                                "name": "Master Bedroom"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNwgKSVu80w2w": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNNwgKSVu80w2w",
                                                "name": "Office"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMIjenwOROfKQ": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMIjenwOROfKQ",
                                                "name": "Outside"
                                        },
                                        "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMLwv6tlzXDSA": {
                                                "where_id": "-z_S_Jc8xjMzSAcosdUyxFKY9jMJvCsOAn7EILNVJNMLwv6tlzXDSA",
                                                "name": "Upstairs"
                                        }
                                }
                        }
                }, "metadata": {
                "access_token": "c.SMjBF19NuZ0Bm7ySJFf0nqyoMohWO2aXOL6u2Kjjx7REcylX3kiLRiYQrQlsP06cNvNf4QEJMiIcGZYkjcd8xlDXsajpwxWKUDgyFvniTefFPXcK8kKFA2ztde1BBGACcoa1dhhHIPcfAane",
                "client_version": 3,
                "user_id": "z.1.1.GptpHRlEQjK5qsF+jtF0jlk78dGteJtkXdOjSdv8Eyo="
                }
        }
    }


structures = eventdata["data"]["structures"]
for key, s in structures.items():
    print("Name:  " + s["name"])
    print("away:  " + s["away"])
    print("co2_alarm:  " + s["co_alarm_state"])
    for location in s["smoke_co_alarms"]:
        print("*" * 80)
        s0 = eventdata["data"]["devices"]["smoke_co_alarms"][location]
        print("Name: " + s0["name"])
        print("CO2 Alarm: " + s0["co_alarm_state"])
        print("Smoke Alarm: " + s0["smoke_alarm_state"])
        print("Energy: " + s0["battery_health"])
        
    # print(key, s)
    # for key1, s1 in s.items():
    #    print(key1, s1)
