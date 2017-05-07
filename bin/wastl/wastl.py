#!/home/stephan/.virtualenvs/cvp0/bin/python
import sys
sys.path.append("../../lib")

from flask import Flask, render_template, request, send_from_directory, jsonify, flash
from bson.objectid import ObjectId
import os
import models
import zmq
import cv2
import time
import requests
import configparser
import guckmongo


def request_to_guck(txt):
    port = "5558"
    context = zmq.Context()
    socket = context.socket(zmq.REQ)
    socket.setsockopt(zmq.LINGER, 0)
    socket.connect("tcp://localhost:%s" % port)
    socket.RCVTIMEO = 1000
    socket.send_string(txt)
    try:
        res0 = socket.recv_pyobj()
        socket.close()
        context.term()
        return res0
    except zmq.ZMQError as e:
        socket.close()
        context.term()
        time.sleep(0.1)
        return None


# init flask
app = Flask(__name__)
app.secret_key = "dfdsmdsv11nmDFSDfds"
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


@app.route("/favicon.png")
def favicon():
    return send_from_directory(os.path.join(app.root_path, 'static'), 'favicon.ico', mimetype='image/vnd.microsoft.icon')


@app.route("/")
@app.route("/home")
def index():
    return render_template("index.html")


# hier noch fullscreen!
@app.route("/livecam/", defaults={"camnrstr": 0, "interval": 5, "toggle": 0, "ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/", defaults={"interval": 5, "toggle": 0, "ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/<interval>/", defaults={"toggle": 0, "ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/<interval>/<toggle>/", defaults={"ptz": 0}, methods=['GET', 'POST'])
@app.route("/livecam/<camnrstr>/<interval>/<toggle>/<ptz>", methods=['GET', 'POST'])
def livecam(camnrstr=0, interval=5, toggle=0, ptz=0):
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
        if len(cameralist)-1 >= camnr:
            _, _, camurl, videourl = cameralist[camnr]
        else:
            camurl = "-"
        return render_template("livecam.html", cameralist=cameralist, camurl=camurl, videourl=videourl, camnr=camnr+1,
                               speed=int(interval), toggle=int(toggle), ptz=0)
    elif request.method == "POST":
        pass


@app.route("/zenz", methods=['GET', 'POST'])
def zenz():
    return render_template("zenz.html")


@app.route("/guck/<menu1>/", defaults={"param1": "0"}, methods=['GET', 'POST'])
@app.route("/guck/<menu1>/<param1>", methods=['GET', 'POST'])
def guck(menu1, param1):
    global socket
    global socketstate
    global DB

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
        camsok = True
        for photoindex in range(lowerbound, upperbound + 1):
            sstr = "photo " + str(photoindex)
            res0 = request_to_guck(sstr)
            if res0 is not None:
                rep0, repname, repfr = res0
                # save new .jpg
                tm = time.strftime("%a%d%b%Y%H:%M:%S")
                photoname = "jpgphoto" + str(j) + tm + ".jpg"
                pn.append(photoname)
                fn = "./static/" + photoname
                cv2.imwrite(fn, repfr)
                j += 1
            else:
                camsok = False
        i = 0
        cursor = DB.db.cameras.find()
        if not camsok:
            camlist.append(("", "Guck host down"))
        else:
            for cam in cursor:
                if camsok:
                    camlist.append((str(i), cam["name"]))
                else:
                    camlist.append((str(i), "Not available!"))
                i += 1
            camlist.append((str(i), "ALL CAMERAS"))
        return render_template("photo.html", camlist=camlist, pn=pn, param1=param1, menu1=menu1)
    elif menu1 == "system":
        # check connection to iotserver
        rep0 = "selection " + param1 + " not implemented yet!"
        if param1 == "1":
            sstr = "ping"
            res0 = request_to_guck(sstr)
            if res0 is not None:
                rep0, repname, repfr = res0
        elif param1 == "0":
            rep0 = ""
            param1 = "1"
        return render_template("system.html", rep0=rep0, param1=param1, menu1=menu1)
    elif menu1 == "help":
        # check connection to iotserver
        sstr = "help"
        res0 = request_to_guck(sstr)
        if res0 is not None:
            rep0, repname, repfr = res0
        else:
            rep0 = "GUCK CONNECTION ERROR"
        replist = rep0.split("\n")
        return render_template("help.html", replist=replist, menu1=menu1)
    elif menu1 == "status":
        sstr = "status"
        res0 = request_to_guck(sstr)
        if res0 is not None:
            rep0, repname, repfr = res0
        else:
            rep0 = "GUCK CONNECTION ERROR"
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
    else:
        result0 = ""
    return jsonify(result=result0)


@app.route("/configmsg", methods=["GET", "POST"])
def configmsg():
    f = request.args.get("a")
    print(f)
    return jsonify(feedback=f)


@app.route("/hue/<menu1>")
def hue(menu1):
    return render_template("index.html")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
