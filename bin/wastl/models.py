from bson.objectid import ObjectId

from flask_wtf import FlaskForm
from wtforms import IntegerField, SelectField, BooleanField, SubmitField, TextField, HiddenField
from wtforms import validators, FileField, FloatField, PasswordField
from wtforms.validators import DataRequired


class ScheduleForm(FlaskForm):
    # All Week fixed
    hlist = []
    for hh in range(24):
        hstr = str(hh)
        if len(hstr) < 2:
            hstr = "0" + hstr
        helem = (hstr, hstr)
        hlist.append(helem)
    mlist = [("00", "00"), ("15", "15"), ("30", "30"), ("45", "45")]
    schedulenr = HiddenField("Schedule Nr", default="0")
    starttime_hh = SelectField('', choices=hlist)
    starttime_mm = SelectField('', choices=mlist)
    endtime_hh = SelectField('', choices=hlist)
    endtime_mm = SelectField('', choices=mlist)
    submit_aw = SubmitField(label="Save")

    def populateform(self):
        self.starttime_hh.data = "19"
        self.starttime_mm.data = "30"
        self.endtime_hh.data = "23"
        self.endtime_mm.data = "30"


class UserLoginForm(FlaskForm):
    email = TextField('Username/Email', [validators.Required(), validators.Length(min=4, max=25)])
    password = PasswordField('Password', [validators.Required(), validators.Length(min=6, max=200)])
    submit_u = SubmitField(label="Log In")
    

class BasicForm(FlaskForm):
    guck_home = TextField("GUCK_HOME")
    doheartbeat = BooleanField("Heartbeat")
    heartbeat_delta = IntegerField("Heartbeat delta (min)", [validators.NumberRange(min=1, max=1440,
                                                                                    message="Delta must be between 1 min and 24h !")])
    heartbeat_dest = SelectField(u'Heartbeat Destination', choices=[('mail', 'E-Mail'), ('telegram', 'Telegram')])
    warn_on_status = BooleanField("Warn on status")
    show_frames = BooleanField("Show Frames")
    dologfps = BooleanField("Log FPS")
    save = SubmitField(label="Save")

    def populateform(self, db):
        self.guck_home.data = db.db_query("basic", "guck_home")
        self.doheartbeat.data = db.db_query("basic", "do_heartbeat")
        self.heartbeat_delta.data = db.db_query("basic", "maxt_heartbeat")
        self.heartbeat_dest.data = db.db_query("basic", "heartbeat_dest")
        self.warn_on_status.data = db.db_query("basic", "warn_on_status")
        self.show_frames.data = db.db_query("basic", "show_frames")
        self.dologfps.data = db.db_query("basic", "do_logfps")

    def updatedb(self, db):
        db.db_update("basic", "guck_home", self.guck_home.data)
        db.db_update("basic", "do_heartbeat", self.doheartbeat.data)
        db.db_update("basic", "maxt_heartbeat", self.heartbeat_delta.data)
        db.db_update("basic", "heartbeat_dest", self.heartbeat_dest.data)
        db.db_update("basic", "warn_on_status", self.warn_on_status.data)
        db.db_update("basic", "show_frames", self.show_frames.data)
        db.db_update("basic", "do_logfps", self.dologfps.data)


class TelegramForm(FlaskForm):
    # telegram
    dotelegram = BooleanField("Telegram:")
    telegramtoken = TextField("Token ", validators=[DataRequired()])
    # chatfieldlist = FieldList(IntegerField("Chat ID", [validators.NumberRange(min=100000000, max=999999999)]),
    #                          min_entries=1)
    chatidlist = []
    chatid_id = TextField("Chat")
    chatedit_index = HiddenField("Chat_index", default="-1")
    mode = SelectField(u'Mode', choices=[('silent', 'silent'), ('verbose', 'verbose')])
    maxt = IntegerField("Min delta (sec)", [validators.NumberRange(min=1, max=60,
                                                                   message="Delta must be between 1 and 60 sec !")])
    save_t = SubmitField(label="Save")
    chatadd_t = SubmitField(label="Add")
    chatedit_t = SubmitField(label="Update")

    def copyajaxdata(self, db):
        self.chatidlist = [chid for chid in db.db_query("telegram", "chatidlist")]

    def populateform(self, db):
        self.dotelegram.data = db.db_query("telegram", "do_telegram")
        self.chatidlist = [chid for chid in db.db_query("telegram", "chatidlist")]
        self.chatid_id.data = ""
        self.telegramtoken.data = db.db_query("telegram", "token")
        self.mode.data = db.db_query("telegram", "mode")
        self.maxt.data = db.db_query("telegram", "maxt")

    def updatedb(self, db):
        db.db_update("telegram", "do_telegram", self.dotelegram.data)
        # print(self.chatidfield)
        db.db_update("telegram", "chatidlist", self.chatidlist)
        db.db_update("telegram", "token", self.telegramtoken.data)
        db.db_update("telegram", "mode", self.mode.data)
        db.db_update("telegram", "maxt", self.maxt.data)


class FTPForm(FlaskForm):
    doftp = BooleanField("FTP:")
    server_url_f = TextField("Server URL", validators=[DataRequired()])
    user_f = TextField("User", validators=[DataRequired()])
    password_f = TextField("Password")
    ftpdir = TextField("FTP root directory", validators=[DataRequired()])
    set_passive = BooleanField("Passive Mode")
    maxt_f = IntegerField("Min delta (sec)", [validators.NumberRange(min=1, max=60,
                                                                     message="Delta must be between 1 and 60 sec !")], default=5)
    save_f = SubmitField(label="Save", validators=[DataRequired()])

    def populateform(self, db):
        self.doftp.data = db.db_query("ftp", "enable")
        self.server_url_f.data = db.db_query("ftp", "server_url")
        self.user_f.data = db.db_query("ftp", "user")
        self.password_f.data = db.db_query("ftp", "password")
        self.ftpdir.data = db.db_query("ftp", "dir")
        self.set_passive.data = db.db_query("ftp", "set_passive")
        self.maxt_f.data = db.db_query("ftp", "maxt")

    def updatedb(self, db):
        db.db_update("ftp", "enable", self.doftp.data)
        db.db_update("ftp", "server_url", self.server_url_f.data)
        db.db_update("ftp", "user", self.user_f.data)
        db.db_update("ftp", "password", self.password_f.data)
        db.db_update("ftp", "dir", self.ftpdir.data)
        db.db_update("ftp", "set_passive", self.set_passive.data)
        db.db_update("ftp", "maxt", self.maxt_f.data)


class SMSForm(FlaskForm):
    dosms = BooleanField("SMS:")
    user_s = TextField("User", validators=[DataRequired()])
    hashcode = TextField("Hash code", validators=[DataRequired()])
    sender_s = TextField("Sender", validators=[DataRequired()])
    # use Telfield (see above)
    destnumber_s = TextField("Dest. number", validators=[DataRequired()])
    maxt_s = IntegerField("Min delta (sec)", [validators.NumberRange(min=1, max=60,
                                                                     message="Delta must be between 1 and 60 sec !")])
    save_s = SubmitField(label="Save", validators=[DataRequired()])

    def populateform(self, db):
        self.dosms.data = db.db_query("sms", "enable")
        self.user_s.data = db.db_query("sms", "user")
        self.hashcode.data = db.db_query("sms", "hashcode")
        self.sender_s.data = db.db_query("sms", "sender")
        self.destnumber_s.data = db.db_query("sms", "destnumber")
        self.maxt_s.data = db.db_query("sms", "maxt")

    def updatedb(self, db):
        db.db_update("sms", "enable", self.dosms.data)
        db.db_update("sms", "user", self.user_s.data)
        db.db_update("sms", "hashcode", self.hashcode.data)
        db.db_update("sms", "sender", self.sender_s.data)
        db.db_update("sms", "destnumber", self.destnumber_s.data)
        db.db_update("sms", "maxt", self.maxt_s.data)


class RemoteForm(FlaskForm):
    guck_path = TextField("Path to GUCK", validators=[DataRequired()])
    remote_virtualenv = TextField("Remote Host VEnv", validators=[DataRequired()])
    remote_host = TextField("Remote Host IP", validators=[DataRequired()])
    remote_host_short = TextField("Remote Host Shortname", validators=[DataRequired()])
    remote_host_mac = TextField("Remote Host MAC", validators=[DataRequired()])
    interface = TextField("Server Network Interface", validators=[DataRequired()])
    remote_port = IntegerField("Remote Port", [validators.NumberRange(min=1, max=65535,
                                                                      message="Port must be between 1 and 65535!")])
    remote_ssh_port = IntegerField("Remote SSH Port", [validators.NumberRange(min=1, max=65535,
                                                                              message="Port must be between 1 and 65535!")])
    save_r = SubmitField(label="Save", validators=[DataRequired()])

    def populateform(self, db):
        self.guck_path.data = db.db_query("remote", "guck_path")
        self.remote_host.data = db.db_query("remote", "remote_host")
        self.remote_virtualenv.data = db.db_query("remote", "remote_virtualenv")
        self.remote_host_short.data = db.db_query("remote", "remote_host_short")
        self.remote_host_mac.data = db.db_query("remote", "remote_host_mac")
        self.interface.data = db.db_query("remote", "interface")
        self.remote_port.data = int(db.db_query("remote", "remote_port"))
        self.remote_ssh_port.data = int(db.db_query("remote", "remote_ssh_port"))

    def updatedb(self, db):
        db.db_update("remote", "guck_path", self.guck_path.data)
        db.db_update("remote", "remote_host", self.remote_host.data)
        db.db_update("remote", "remote_virtualenv", self.remote_virtualenv.data)
        db.db_update("remote", "remote_host_short", self.remote_host_short.data)
        db.db_update("remote", "remote_host_mac", self.remote_host_mac.data)
        db.db_update("remote", "interface", self.interface.data)
        db.db_update("remote", "remote_port", str(self.remote_port.data))
        db.db_update("remote", "remote_ssh_port", str(self.remote_ssh_port.data))


class MailForm(FlaskForm):
    domail = BooleanField("E-mail:")
    mail_from = TextField("Send from", validators=[DataRequired()])
    mail_to = TextField("Send to", validators=[DataRequired()])
    user_m = TextField("User", validators=[DataRequired()])
    password_m = TextField("Password")   # Passwd. empty is ok!
    server_m = TextField("SMTP server", validators=[DataRequired()])
    port_m = IntegerField("Port", [validators.NumberRange(min=1, max=65535, message="Port must be between 1 and 65535!")])
    maxt_m = IntegerField("Min delta (sec)", [validators.NumberRange(min=1, max=60,
                                                                     message="Delta must be between 1 and 60 sec !")])
    only_text = BooleanField("Text only")
    save_m = SubmitField(label="Save", validators=[DataRequired()])

    def populateform(self, db):
        self.domail.data = db.db_query("mail", "enable")
        self.mail_from.data = db.db_query("mail", "from")
        self.mail_to.data = db.db_query("mail", "to")
        self.user_m.data = db.db_query("mail", "user")
        self.password_m.data = db.db_query("mail", "password")
        self.server_m.data = db.db_query("mail", "server")
        self.port_m.data = db.db_query("mail", "smtport")
        self.maxt_m.data = db.db_query("mail", "maxt")
        self.only_text.data = db.db_query("mail", "only_text")

    def updatedb(self, db):
        db.db_update("mail", "enable", self.domail.data)
        db.db_update("mail", "from", self.mail_from.data)
        db.db_update("mail", "to", self.mail_to.data)
        db.db_update("mail", "user", self.user_m.data)
        db.db_update("mail", "password", self.password_m.data)
        db.db_update("mail", "server", self.server_m.data)
        db.db_update("mail", "smtport", self.port_m.data)
        db.db_update("mail", "maxt", self.maxt_m.data)
        db.db_update("mail", "only_text", self.only_text.data)


class AIForm(FlaskForm):
    ai_mode = SelectField('AI Mode', choices=[("CNN", 'CNN'), ("CV", 'CV2')])
    cnn_path = TextField("CNN path #1", validators=[DataRequired()])
    cnn_path2 = TextField("CNN path #2", validators=[DataRequired()])
    cnn_path3 = TextField("CNN path #3", validators=[DataRequired()])
    haar_path = TextField("HAAR path #1", validators=[DataRequired()])
    haar_path2 = TextField("HAAR path #2", validators=[DataRequired()])
    ai_sens = IntegerField("Sensitivity (1 - 10)", [validators.NumberRange(min=1, max=10,
                                                                           message="Sensitivity must be between 1 and 10")])
    save_a = SubmitField(label="Save", validators=[DataRequired()])

    def populateform(self, db):
        self.ai_mode.data = db.db_query("ai", "ai_mode")
        self.cnn_path.data = db.db_query("ai", "cnn_path")
        self.cnn_path2.data = db.db_query("ai", "cnn_path2")
        self.cnn_path3.data = db.db_query("ai", "cnn_path3")
        self.haar_path.data = db.db_query("ai", "haar_path")
        self.haar_path2.data = db.db_query("ai", "haar_path2")
        self.ai_sens.data = db.db_query("ai", "ai_sens")

    def updatedb(self, db):
        db.db_update("ai", "ai_mode", self.ai_mode.data)
        db.db_update("ai", "cnn_path", self.cnn_path.data)
        db.db_update("ai", "cnn_path2", self.cnn_path2.data)
        db.db_update("ai", "cnn_path3", self.cnn_path3.data)
        db.db_update("ai", "haar_path", self.haar_path.data)
        db.db_update("ai", "haar_path2", self.haar_path2.data)
        db.db_update("ai", "ai_sens", self.ai_sens.data)


class PhotoForm(FlaskForm):
    dophoto = BooleanField("Photo:")
    doaiphoto = BooleanField("AI photo:")
    # use FileField
    aphotodir = TextField("Photo Directory", validators=[DataRequired()])
    aphotodir_file = FileField("Photo Directory")
    aiphotodir = TextField("AI photo directory [1]", validators=[DataRequired()])
    aiphotodir_neg = TextField("AI photo directory [0]", validators=[DataRequired()])
    maxt_p = IntegerField("Min delta (sec)", [validators.NumberRange(min=1, max=60,
                                                                     message="Delta must be between 1 and 60 sec !")])
    cutoff_p = BooleanField("CutOff")
    cutoff_len = IntegerField("CutOff Len", [validators.NumberRange(min=250, max=5000,
                                                                    message="CutOff Len must be between 250 and 5000!")])
    save_p = SubmitField(label="Save")

    def populateform(self, db):
        self.dophoto.data = db.db_query("photo", "enable")
        self.doaiphoto.data = db.db_query("photo", "enable_aiphoto")
        self.aphotodir.data = db.db_query("photo", "aphoto_dir")
        self.aiphotodir.data = db.db_query("photo", "aiphoto_dir")
        self.aiphotodir_neg.data = db.db_query("photo", "aiphoto_dir_neg")
        self.maxt_p.data = db.db_query("photo", "maxt")
        self.cutoff_p.data = db.db_query("photo", "cutoff")
        self.cutoff_len.data = db.db_query("photo", "cutoff_len")

    def updatedb(self, db):
        db.db_update("photo", "enable", self.dophoto.data)
        db.db_update("photo", "enable_aiphoto", self.doaiphoto.data)
        db.db_update("photo", "aphoto_dir", self.aphotodir.data)
        db.db_update("photo", "aiphoto_dir", self.aiphotodir.data)
        db.db_update("photo", "aiphoto_dir_neg", self.aiphotodir_neg.data)
        db.db_update("photo", "maxt", self.maxt_p.data)
        db.db_update("photo", "cutoff", self.cutoff_p.data)
        db.db_update("photo", "cutoff_len", self.cutoff_len.data)


class CamerasForm(FlaskForm):
    enabled = BooleanField("Enabled")
    cameralist = []
    act_camera_id = HiddenField("Camera_id", default="-1")
    name_c = TextField("Name", validators=[DataRequired()])
    videofile = TextField("Videofile name", validators=[DataRequired()])
    recordfile = TextField("Recordfile name", validators=[DataRequired()])
    url_c = TextField("Stream URL", validators=[DataRequired()])
    host_ip = TextField("Host IP", validators=[DataRequired()])
    host_venv = TextField(" Host venv", validators=[DataRequired()])
    min_area_rect = IntegerField("Min. area rect.", [validators.NumberRange(min=1, max=12000,
                                                                            message="Area must be between 1 and 12000!")])
    haar_scale = FloatField("HAAR scale", [validators.NumberRange(min=1.01, max=1.5,
                                                                  message="Scale must be between 1.01 and 1.5!")])
    hog_scale = FloatField("HOG scale", [validators.NumberRange(min=1.01, max=1.5,
                                                                message="Scale must be between 1.01 and 1.5!")])
    hog_thresh = FloatField("HOG threshold", [validators.NumberRange(min=0.01, max=0.5,
                                                                     message="Threshold must be between 0.01 and 0.5!")])
    mog2_sens = IntegerField("MOG2 sens.", [validators.NumberRange(min=1, max=10,
                                                                   message="Sensitivity must be between 1 and 10!")])
    scanrate = IntegerField("Scan rate", [validators.NumberRange(min=5, max=50,
                                                                 message="Scan rate must be between 5 and 50")])
    ptz_mode = SelectField('PTZ mode', coerce=int, choices=[(1, 'START'), (2, 'STARTSTOP')])
    ptz_right = TextField("PTZ right URL")
    ptz_left = TextField("PTZ left URL")
    ptz_up = TextField("PTZ up URL")
    ptz_down = TextField("PTZ down URL")
    photo_url = TextField("LiveCam Photo URL")
    reboot = TextField("Reboot URL")
    camadd_t = SubmitField(label="Add")
    camedit_t = SubmitField(label="Update")
    camcancel_t = SubmitField(label="Cancel")

    def copyajaxdata(self, db):
        cursor = db.db_getall("cameras")
        self.cameralist = [(cn["_id"], cn["name"], cn["enable"]) for cn in cursor]

    def populate_with_defaults(self, db):
        self.name_c.data = "Camera-xy"
        self.enabled.data = True
        self.videofile.data = "video1.h264"
        self.recordfile.data = "videorecord.avi"
        self.url_c.data = "http://USER:PASSWORD@ipcamera:80/video.cgi"
        self.host_ip.data = "localhost"
        self.host_venv.data = "/home/USER/.virtualenvs/VIRTENV/bin/python"
        self.min_area_rect.data = 1200
        self.haar_scale.data = 1.05
        self.hog_scale.data = 1.05
        self.hog_thresh.data = 0.1
        self.mog2_sens.data = 5
        self.scanrate.data = 10
        self.ptz_mode.data = 1
        self.ptz_right.data = "http://USER:PASSWORD@ipcamera/cgi-bin/ptz.cgi?action=start&channel=0&code=Right"
        self.ptz_left.data = "http://USER:PASSWORD@ipcamera/cgi-bin/ptz.cgi?action=start&channel=0&code=Left"
        self.ptz_up.data = "http://USER:PASSWORD@ipcamera/cgi-bin/ptz.cgi?action=start&channel=0&code=Up"
        self.ptz_down.data = "http://USER:PASSWORD@ipcamera/cgi-bin/ptz.cgi?action=start&channel=0&code=Down"
        self.reboot.data = "http://USER:PASSWORD@ipcamera/cgi-bin/action=reboot"
        self.photo_url.data = "http://USER:PASSWORD@ipcamera/tmpfs/auto.jpg"

    def populateform(self, db):
        self.copyajaxdata(db)
        if len(str(self.act_camera_id.data)) > 2:
            id0 = ObjectId(self.act_camera_id.data)
            cam0 = db.db_find_one("cameras", "_id", id0)
            self.name_c.data = cam0["name"]
            self.enabled.data = cam0["enable"]
            self.videofile.data = cam0["videofile"]
            self.recordfile.data = cam0["recordfile"]
            self.url_c.data = cam0["url"]
            self.host_ip.data = cam0["host_ip"]
            self.host_venv.data = cam0["host_venv"]
            self.min_area_rect.data = cam0["min_area_rect"]
            self.haar_scale.data = cam0["haarscale"]
            self.hog_scale.data = cam0["hog_scale"]
            self.hog_thresh.data = cam0["hog_thresh"]
            self.mog2_sens.data = cam0["mog2_sensitivity"]
            self.scanrate.data = cam0["scanrate"]
            self.ptz_mode.data = 1 if cam0["ptz_mode"] == "START" else 2
            self.ptz_right.data = cam0["ptz_right"]
            self.ptz_left.data = cam0["ptz_left"]
            self.ptz_up.data = cam0["ptz_up"]
            self.ptz_down.data = cam0["ptz_down"]
            self.reboot.data = cam0["reboot"]
            self.photo_url.data = cam0["photo_url"]

    def updatedb(self, db, idparam="--"):
        if idparam == "--":
            id0 = ObjectId(self.act_camera_id.data)
        else:
            id0 = idparam
            self.act_camera_id.data = id0
        db.db_update2("cameras", "_id", id0, "name", self.name_c.data)
        db.db_update2("cameras", "_id", id0, "enable", self.enabled.data)
        db.db_update2("cameras", "_id", id0, "videofile", self.videofile.data)
        db.db_update2("cameras", "_id", id0, "recordfile", self.recordfile.data)
        db.db_update2("cameras", "_id", id0, "url", self.url_c.data)
        db.db_update2("cameras", "_id", id0, "host_ip", self.host_ip.data)
        db.db_update2("cameras", "_id", id0, "host_venv", self.host_venv.data)
        db.db_update2("cameras", "_id", id0, "min_area_rect", self.min_area_rect.data)
        db.db_update2("cameras", "_id", id0, "haarscale", self.haar_scale.data)
        db.db_update2("cameras", "_id", id0, "hog_scale", self.hog_scale.data)
        db.db_update2("cameras", "_id", id0, "hog_thresh", self.hog_thresh.data)
        db.db_update2("cameras", "_id", id0, "mog2_sensitivity", self.mog2_sens.data)
        db.db_update2("cameras", "_id", id0, "scanrate", self.scanrate.data)
        db.db_update2("cameras", "_id", id0, "ptz_mode", "START" if self.ptz_mode.data == 1 else "STARTSTOP")
        db.db_update2("cameras", "_id", id0, "ptz_right", self.ptz_right.data)
        db.db_update2("cameras", "_id", id0, "ptz_left", self.ptz_left.data)
        db.db_update2("cameras", "_id", id0, "ptz_up", self.ptz_up.data)
        db.db_update2("cameras", "_id", id0, "ptz_down", self.ptz_down.data)
        db.db_update2("cameras", "_id", id0, "reboot", self.reboot.data)
        db.db_update2("cameras", "_id", id0, "photo_url", self.photo_url.data)
