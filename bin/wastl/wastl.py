#!/home/stephan/.virtualenvs/cvp0/bin/python
import sys
sys.path.append("../../lib")

from flask import Flask, render_template, request, send_from_directory, jsonify, flash, url_for, redirect, Response
from bson.objectid import ObjectId
import os
import models
import zmq
import cv2
import time
import requests
import configparser
import guckmongo
import zenzlib
import threading
import flask_login
from hasher import hash_password, check_password, read_hashfile, write_hashfile
import json
import numpy as np
import urllib.request


socketstate = None
CHATEDIT_INDEX = -1

# try to get config & DB
try:
    dbconfig = configparser.ConfigParser()
    dbconfig.read("../../data/mongo_default/mongo_url.cfg")
    dburl = dbconfig["CONFIG"]["DB_URL"].rstrip()
    dbname = dbconfig["CONFIG"]["DB_NAME"].rstrip()
    DB = guckmongo.ConfigDB(dburl, dbname)
except Exception as e:
    print(str(e) + ": Cannot get WASTL config for DB, exiting ...")
    sys.exit()

# start WastAlarmServer
WAS = zenzlib.WastlAlarmClient()
PHOTOLIST = []
PHOTOLIST_LEN = 0
GUCKSTATUS = False

# init flask
app = Flask(__name__)
app.secret_key = "dfdsmdsv11nmDFSDfds"

# Login Manager
login_manager = flask_login.LoginManager()
login_manager.init_app(app)

# Passwords
hashfile = "../../data/hash.pw"
users = read_hashfile(hashfile)


class Camera(object):
    def __init__(self, camnr):
        cursor = DB.db_getall("cameras")
        cameralist = [cn["url"] for cn in cursor]
        self.surl = cameralist[camnr]
        #self.cap = cv2.VideoCapture(self.surl)
        self.stream = urllib.request.urlopen(self.surl)
        self.bytes = b''

    def get_frame(self):
        while True:
            self.bytes += self.stream.read(1024)
            a = self.bytes.find(b'\xff\xd8')
            b = self.bytes.find(b'\xff\xd9')
            if a != -1 and b != -1:
                jpg = self.bytes[a:b+2]
                self.bytes = self.bytes[b+2:]
                frame = cv2.imdecode(np.fromstring(jpg, dtype=np.uint8), cv2.IMREAD_COLOR)
                ret, jpeg = cv2.imencode('.jpg', frame)
                return ret, jpeg.tobytes()


def gen(camera):
    """Video streaming generator function."""
    while True:
        ret, frame = camera.get_frame()
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


class User(flask_login.UserMixin):
    pass


@login_manager.user_loader
def user_loader(email):
    if email not in users:
        return
    user = User()
    user.id = email
    return user


@login_manager.request_loader
def request_loader(request):
    email = request.form.get('email')
    if email not in users:
        return
    user = User()
    user.id = email

    # DO NOT ever store passwords in plaintext and always compare password
    # hashes using constant-time comparison!
    user.is_authenticated = check_password(users[email]['pw'], request.form["pw"])
    return user


# helper functions

def save_and_prepare_forms(db0, form0, formlist):
    for f in formlist:
        if f == form0:
            f.updatedb(DB)
        f.populateform(DB)


def flash_errors(form):
    for field, errors in form.errors.items():
        for error in errors:
            flash(u"Error in the %s field - %s" % (
                getattr(form, field).label.text,
                error
            ))


@app.route("/wastl.png")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'wastl.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/", methods=['GET', 'POST'])
@app.route("/home", methods=['GET', 'POST'])
def index():
    print(flask_login.current_user.is_authenticated)
    return render_template("index.html", userauth=flask_login.current_user.is_authenticated)


@app.route('/video_feed/<camnr>/')
def video_feed(camnr):
    return Response(gen(Camera(int(camnr)-1)), mimetype='multipart/x-mixed-replace; boundary=frame')


# hier noch fullscreen!
@app.route("/livecam/", defaults={"camnrstr": 0, "toggle": 0, "ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/", defaults={"toggle": 0, "ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/<toggle>/", defaults={"ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/<toggle>/<ptz>", methods=['GET', 'POST'])
@flask_login.login_required
def livecam(camnrstr=0, toggle=0, ptz=0):
    if request.method == "GET":
        ptz0 = int(ptz)
        camnr = int(camnrstr)
        cursor = DB.db_getall("cameras")
        cameralist = [(cn["_id"], cn["name"], cn["photo_url"], cn["url"]) for cn in cursor]
        if ptz0 != 0 and len(cameralist)-1 >= camnr:
            cursor = DB.db_getall("cameras")
            ptzlist = [(cn["_id"], cn["ptz_up"], cn["ptz_down"], cn["ptz_left"], cn["ptz_right"]) for cn in cursor]
            _, ptz_up, ptz_down, ptz_left, ptz_right = ptzlist[camnr]
            ptzcommand = ""
            if ptz0 == 1:
                ptzcommand = ptz_up
            elif ptz0 == 2:
                ptzcommand = ptz_down
            elif ptz0 == 3:
                ptzcommand = ptz_left
            elif ptz0 == 4:
                ptzcommand = ptz_right
            if ptzcommand != "":
                try:
                    requests.get(ptzcommand)
                except:
                    pass
        return render_template("livecam.html", cameralist=cameralist, camnr=camnr+1, toggle=int(toggle), ptz=0)
    elif request.method == "POST":
        pass


@flask_login.login_required
@app.route("/zenz", methods=['GET', 'POST'])
def zenz():
    return render_template("zenz.html")


@app.route("/userlogin", methods=['GET', 'POST'])
def userlogin():
    if request.method == "GET":
        userloginform = models.UserLoginForm(request.form)
        return render_template("login.html", userloginform=userloginform, userauth=flask_login.current_user.is_authenticated)
    else:
        users = read_hashfile(hashfile)
        userloginform = models.UserLoginForm(request.form)
        email = userloginform.email.data
        pw = userloginform.password.data
        # print(">>>>" + email + " " + pw)
        try:
            pw_hash = users[email]["pw"]
        except:
            return redirect(url_for("index"))
        if check_password(pw_hash, pw):
            user = User()
            user.id = email
            flask_login.login_user(user)
            return render_template("index.html")
        return redirect(url_for('index'))


@login_manager.unauthorized_handler
def unauthorized_handler():
    return redirect(url_for('index'))


@app.route("/userlogout", methods=['GET', 'POST'])
@flask_login.login_required
def userlogout():
    flask_login.logout_user()
    return render_template("index.html", userauth=flask_login.current_user.is_authenticated)


@app.route("/detections", methods=['GET', 'POST'])
@flask_login.login_required
def detections():
    global PHOTOLIST
    global PHOTOLIST_LEN
    detlist = []
    for i, ple in enumerate(reversed(PHOTOLIST)):
        if i > 5:
            break
        # save new .jpg
        frame, tm = ple
        photoname = "detphoto" + tm + ".jpg"
        detlist.append((photoname, tm))
        fn = "./static/" + photoname
        cv2.imwrite(fn, frame)
    PHOTOLIST_LEN = 0
    return render_template("detections.html", detlist=detlist)


@app.route("/guck/<menu1>/", defaults={"param1": "0"}, methods=['GET', 'POST'])
@app.route("/guck/<menu1>/<param1>", methods=['GET', 'POST'])
@flask_login.login_required
def guck(menu1, param1):
    global socket
    global socketstate
    global DB
    global PHOTOLIST

    if menu1 == "photo" or menu1 == "system" or menu1 == "help" or menu1 == "status" or menu1 == "start":
        GUCK_PATH = DB.db_query("remote", "guck_path")
        REMOTE_HOST = DB.db_query("remote", "remote_host")
        REMOTE_HOST_SHORT = DB.db_query("remote", "remote_host_short")
        REMOTE_PORT = DB.db_query("remote", "remote_port")
        REMOTE_SSH_PORT = DB.db_query("remote", "remote_ssh_port")
        REMOTE_HOST_MAC = DB.db_query("remote", "remote_host_mac")
        INTERFACE = DB.db_query("remote", "interface")
        REMOTE_VIRTUALENV = DB.db_query("remote", "remote_virtualenv")
        ZENZL = zenzlib.ZenzLib(REMOTE_HOST, REMOTE_HOST_MAC, INTERFACE, REMOTE_PORT, REMOTE_HOST_SHORT, REMOTE_SSH_PORT,
                                GUCK_PATH, REMOTE_VIRTUALENV)

    if menu1 == "photo":
        camlist = []
        pn = []
        # delete all files in directory
        filelist = [f for f in os.listdir("./static/") if f.endswith(".jpg")]
        for f in filelist:
            os.remove("./static/" + f)
        # just one photo or all?
        cursor = DB.db_getall("cameras")
        nr_cameras = len([(cn["_id"], cn["name"], cn["enable"]) for cn in cursor])
        print("# cameras:", nr_cameras)
        if int(param1) < nr_cameras:
            lowerbound = upperbound = int(param1)
        else:
            lowerbound = 0
            upperbound = nr_cameras - 1
        # loop over all cameras and save photos as .jpg
        j = 1
        REMOTE_HOST = DB.db_query("remote", "remote_host")
        REMOTE_PORT = DB.db_query("remote", "remote_port")
        camsok = True
        for photoindex in range(lowerbound, upperbound + 1):
            sstr = "photo " + str(photoindex)
            ok, res0 = ZENZL.request_to_guck(sstr, REMOTE_HOST, REMOTE_PORT)
            if ok:
                rep0, repname, repfr = res0
                # save new .jpg
                tm = time.strftime("%a%d%b%Y%H:%M:%S")
                photoname = "jpgphoto" + str(j) + tm + ".jpg"
                pn.append(photoname)
                fn = "./static/" + photoname
                cv2.imwrite(fn, repfr)
                j += 1
            else:
                pn.append(False)
                camsok = False
        i = 0
        cursor = DB.db.cameras.find()
        for cam in cursor:
            camlist.append((str(i), cam["name"], camsok))
            i += 1
        camlist.append((str(i), "ALL CAMERAS", camsok))
        return render_template("photo.html", camlist=camlist, pn=pn, param1=param1, menu1=menu1)
    elif menu1 == "start":
        rep0 = []
        stat, rep = ZENZL.ping()
        if stat == 0:
            ZENZL.lanwake()
            rep0.append(rep)
            rep0.append("Guck host down, now booting up via WOL, pls try again in 1 min ...")
        elif stat == 1:
            noservers = ZENZL.get_nr_instances()
            if noservers > 0:
                ZENZL.killguck()
                rep0.append(rep)
                rep0.append("Killing guck on " + REMOTE_HOST_SHORT)
            try:
                ZENZL.startguck()
                rep0.append("Starting guck at " + REMOTE_HOST_SHORT)
            except Exception as e:
                rep0.append(str(e))
                # rep0 += "\nError in guck start up, possibly no ssh access to guck host ... ?"
        else:
            rep0.append("Error in ping to guck host: " + rep)
        return render_template("start.html", rep0=rep0)
    elif menu1 == "system":
        # ping
        rep0 = []
        if param1 == "1":
            stat, rep = ZENZL.ping()
            if stat == -1:
                rep0.append("Error in ping to guck host: " + str(rep))
            else:
                rep0.append(rep)
        # (re)start
        elif param1 == "2":
            stat, rep = ZENZL.ping()
            if stat == 0:
                ZENZL.lanwake()
                rep0.append(rep)
                rep0.append("Guck host down, now booting up via WOL, pls try again in 1 min ...")
            elif stat == 1:
                noservers = ZENZL.get_nr_instances()
                if noservers > 0:
                    ZENZL.killguck()
                    rep0.append(rep)
                    rep0.append("Killing guck on " + REMOTE_HOST_SHORT)
                try:
                    ZENZL.startguck()
                    rep0.append("Starting guck at: " + REMOTE_HOST_SHORT)
                except Exception as e:
                    rep0.append(str(e))
                    # rep0 += "\nError in guck start up, possibly no ssh access to guck host ... ?"
            else:
                rep0.append("Error in ping to guck host: " + rep)
        # stop/shutdown
        elif param1 == "3" or param1 == "10":
            ZENZL.killguck()
            if param1 == "3":
                rep0.append("Killing guck on " + REMOTE_HOST_SHORT)
            if param1 == "10":
                ZENZL.shutdown()
                rep0.append("Killing guck, shutting down " + REMOTE_HOST_SHORT)
        elif param1 in ["4", "5", "6", "7", "8", "9"]:
            if param1 == "4":
                sstr = "pause"
            elif param1 == "5":
                sstr = "resume"
            elif param1 == "6":
                sstr = "quit"
            elif param1 == "7":
                sstr = "record start"
            elif param1 == "8":
                sstr = "record stop"
            elif param1 == "9":
                sstr = "clear"
            stat, res0 = ZENZL.request_to_guck(sstr, REMOTE_HOST, REMOTE_PORT)
            if stat:
                rep, repname, repfr = res0
                rep0.append(rep)
            else:
                rep0.append(res0)
        elif param1 == "0":
            rep0 = []
            param1 = "1"
        return render_template("system.html", rep0=rep0, param1=param1, menu1=menu1)
    elif menu1 == "help":
        # check connection to iotserver
        sstr = "help"
        stat, res0 = ZENZL.request_to_guck(sstr, REMOTE_HOST, REMOTE_PORT)
        if stat:
            rep0, repname, repfr = res0
        else:
            rep0 = res0
        replist = rep0.split("\n")
        return render_template("help.html", replist=replist, menu1=menu1)
    elif menu1 == "status":
        sstr = "status"
        stat, res0 = ZENZL.request_to_guck(sstr, REMOTE_HOST, REMOTE_PORT)
        if stat:
            rep0, repname, repfr = res0
        else:
            rep0 = res0
        replist = rep0.split("\n")
        return render_template("status.html", replist=replist, menu1=menu1)
    elif menu1 == "config":
        camlist = []
        tabchoice = "basic"
        if request.method == "GET":
            basicform = models.BasicForm(request.form)
            telegramform = models.TelegramForm(request.form)
            mailform = models.MailForm(request.form)
            ftpform = models.FTPForm(request.form)
            smsform = models.SMSForm(request.form)
            aiform = models.AIForm(request.form)
            photoform = models.PhotoForm(request.form)
            camerasform = models.CamerasForm(request.form)
            remoteform = models.RemoteForm(request.form)
            formlist = [telegramform, basicform, mailform, ftpform, smsform, aiform, photoform, camerasform, remoteform]
            for f in formlist:
                f.populateform(DB)
            return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                   ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                   camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
        if request.method == 'POST':
            basicform = models.BasicForm(request.form)
            telegramform = models.TelegramForm(request.form)
            mailform = models.MailForm(request.form)
            ftpform = models.FTPForm(request.form)
            smsform = models.SMSForm(request.form)
            aiform = models.AIForm(request.form)
            photoform = models.PhotoForm(request.form)
            remoteform = models.RemoteForm(request.form)
            camerasform = models.CamerasForm(request.form)
            formlist = [telegramform, basicform, mailform, ftpform, smsform, aiform, photoform, camerasform, remoteform]
            # basic
            if (basicform.save.data):
                if basicform.validate_on_submit() or not basicform.doheartbeat.data:
                    print("basic validated!")
                    save_and_prepare_forms(DB, basicform, formlist)
                else:
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "basic"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # cameras
            elif (camerasform.camedit_t.data):
                if camerasform.validate_on_submit():
                    # print("validate")
                    camerasform.copyajaxdata(DB)
                    save_and_prepare_forms(DB, camerasform, formlist)
                else:
                    flash_errors(camerasform)
                    # print(">>>", camerasform.act_camera_id.data)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "cameras"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            elif camerasform.camadd_t.data:
                if camerasform.validate_on_submit():
                    id0 = DB.db_open_one("cameras", {"name": "dummy0", "enable": True})
                    camerasform.updatedb(DB, idparam=id0)
                    camerasform.copyajaxdata(DB)
                    save_and_prepare_forms(DB, camerasform, formlist)
                else:
                    print("Not validated!")
                    flash_errors(camerasform)
                    camerasform.copyajaxdata(DB)
                tabchoice = "cameras"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            elif camerasform.camcancel_t.data:
                camerasform.act_camera_id.data = "-1"
                save_and_prepare_forms(DB, None, formlist)
                tabchoice = "cameras"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")

            # telegram
            elif (telegramform.save_t.data):
                if telegramform.validate_on_submit() or not telegramform.dotelegram.data:
                    telegramform.copyajaxdata(DB)
                    save_and_prepare_forms(DB, telegramform, formlist)
                else:
                    flash_errors(telegramform)
                    telegramform.copyajaxdata(DB)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "telegram"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            elif telegramform.chatadd_t.data or telegramform.chatedit_t.data:
                cdata = telegramform.chatid_id.data
                chat_index = int(telegramform.chatedit_index.data)
                if cdata and telegramform.chatadd_t.data:
                    chatidlist = DB.db_query("telegram", "chatidlist")
                    chatidlist.append(telegramform.chatid_id.data)
                    DB.db_update("telegram", "chatidlist", chatidlist)
                elif cdata and telegramform.chatedit_t.data and chat_index > -1:
                    chatidlist = DB.db_query("telegram", "chatidlist")
                    chatidlist[chat_index] = telegramform.chatid_id.data
                    DB.db_update("telegram", "chatidlist", chatidlist)
                    telegramform.chatedit_index.data = "-1"
                tabchoice = "telegram"
                telegramform.copyajaxdata(DB)
                save_and_prepare_forms(DB, None, formlist)
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # mail
            elif (mailform.save_m.data):
                if mailform.validate_on_submit() or not mailform.domail.data:
                    save_and_prepare_forms(DB, mailform, formlist)
                else:
                    flash_errors(mailform)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "mail"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # ftp
            elif (ftpform.save_f.data):
                if ftpform.validate_on_submit() or not ftpform.doftp.data:
                    save_and_prepare_forms(DB, ftpform, formlist)
                else:
                    flash_errors(ftpform)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "ftp"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # sms
            elif (smsform.save_s.data):
                if smsform.validate_on_submit() or not smsform.dosms.data:
                    save_and_prepare_forms(DB, smsform, formlist)
                else:
                    flash_errors(smsform)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "sms"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # photo
            elif (photoform.save_p.data):
                if photoform.validate_on_submit():
                    save_and_prepare_forms(DB, photoform, formlist)
                else:
                    flash_errors(photoform)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "photo"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # remote
            elif (remoteform.save_r.data):
                if remoteform.validate_on_submit():
                    save_and_prepare_forms(DB, remoteform, formlist)
                else:
                    flash_errors(remoteform)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "remote"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
            # ai
            elif (aiform.save_a.data):
                if aiform.validate_on_submit():
                    save_and_prepare_forms(DB, aiform, formlist)
                else:
                    flash_errors(aiform)
                    save_and_prepare_forms(DB, None, formlist)
                tabchoice = "ai"
                return render_template('config.html', basicform=basicform, telegramform=telegramform, mailform=mailform,
                                       ftpform=ftpform, smsform=smsform, aiform=aiform, photoform=photoform,
                                       camerasform=camerasform, tabchoice=tabchoice, remoteform=remoteform, chatedit="empty")
    else:
        replist = []
        return render_template("index.html")


@app.route("/_ajaxconfig", methods=["GET", "POST"])
def _ajaxconfig():
    global DB
    global PHOTOLIST_LEN
    global GUCKSTATUS
    cmd = request.args.get("cmd")
    index = request.args.get("index", 0, type=int)
    if cmd == "delete":
        chatidlist = DB.db_query("telegram", "chatidlist")
        if index >= 0 and index <= len(chatidlist)-1:
            del chatidlist[index]
            DB.db_update("telegram", "chatidlist", chatidlist)
            telegramform = models.TelegramForm(request.form)
            telegramform.copyajaxdata(DB)
            telegramform.populateform(DB)
            result0 = render_template("config_chatid.html", telegramform=telegramform)
    elif cmd == "edit":
        chatidlist = DB.db_query("telegram", "chatidlist")
        telegramform = models.TelegramForm(request.form)
        telegramform.copyajaxdata(DB)
        telegramform.populateform(DB)
        telegramform.chatid_id.data = chatidlist[index]
        telegramform.chatedit_index.data = index
        result0 = render_template("config_chatedit.html", telegramform=telegramform, chatedit=str(index+1))
    elif cmd == "camedit":
        camerasform = models.CamerasForm(request.form)
        camerasform.copyajaxdata(DB)
        camerasform.act_camera_id.data, _, _ = camerasform.cameralist[index]
        camerasform.populateform(DB)
        result0 = render_template("config_camedit.html", camerasform=camerasform, camedit_action="edit",
                                  cid=camerasform.act_camera_id.data)
    elif cmd == "camdelete":
        camerasform = models.CamerasForm(request.form)
        camerasform.copyajaxdata(DB)
        camerasform.act_camera_id.data, _, _ = camerasform.cameralist[index]
        id0 = ObjectId(camerasform.act_camera_id.data)
        DB.db_delete_one("cameras", "_id", id0)
        camerasform.act_camera_id.data = "-1"
        camerasform.copyajaxdata(DB)
        result0 = render_template("config_cameraid.html", camerasform=camerasform)
    elif cmd == "camcheck":
        check = request.args.get("check", 0, type=str)
        checkbol = True if check == "true" else False
        camerasform = models.CamerasForm(request.form)
        camerasform.copyajaxdata(DB)
        camerasform.act_camera_id.data, _, _ = camerasform.cameralist[index]
        id0 = ObjectId(camerasform.act_camera_id.data)
        DB.db_update2("cameras", "_id", id0, "enable", checkbol)
        camerasform.act_camera_id.data = "-1"
        camerasform.copyajaxdata(DB)
        result0 = render_template("config_cameraid.html", camerasform=camerasform)
    elif cmd == "camadd":
        # insert code here
        camerasform = models.CamerasForm(request.form)
        camerasform.populate_with_defaults(DB)
        result0 = render_template("config_camedit.html", camerasform=camerasform, camedit_action="add")
    elif cmd == "guckphoto":
        stat, data = WAS.get_from_guck()
        if stat:
            PHOTOLIST_LEN += 1
            frame, tm = data
            PHOTOLIST.append(data)
            if len(PHOTOLIST) > 50:
                del PHOTOLIST[0]
                PHOTOLIST_LEN -= 1
        if stat is False and data is not False:
            GUCKSTATUS = False
        else:
            GUCKSTATUS = True
        result0 = render_template("guckphoto.html", nralarms=PHOTOLIST_LEN)
    else:
        result0 = ""
    return jsonify(result=result0, status=GUCKSTATUS)


@app.route("/configmsg", methods=["GET", "POST"])
@flask_login.login_required
def configmsg():
    f = request.args.get("a")
    print(f)
    return jsonify(feedback=f)


@app.route("/hue/<menu1>")
@flask_login.login_required
def hue(menu1):
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
