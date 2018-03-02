import os
import subprocess
from paramiko import SSHClient
import paramiko
import zmq
import time
import dill
import json
import requests


class Connector:
    def send_to_connector(self, msgtype, typ, obj0, host="localhost", port="7014"):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socketurl = "tcp://" + host + ":" + port
        socket.connect(socketurl)
        socket.RCVTIMEO = 300
        socket.send_pyobj((msgtype, typ, dill.dumps(obj0)))
        try:
            oknok = socket.recv_string()
            socket.close()
            context.term()
            return True, oknok
        except zmq.ZMQError as e:
            socket.close()
            context.term()
            time.sleep(0.1)
            return False


# waits for alarmphotos sent from guck
class WastlAlarmClient:

    def get_from_guck(self, url="etec.iv.at", port="7001"):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect("tcp://" + url + ":" + port)
        socket.RCVTIMEO = 300
        socket.send_string("REQ")
        try:
            ret, r, p = socket.recv_pyobj()
            socket.close()
            context.term()
            if ret:
                return True, dill.loads(r), p
            else:
                return False, False, p
        except zmq.ZMQError as e:
            socket.close()
            context.term()
            time.sleep(0.1)
            return False, "WASTL connection error: " + str(e), False


class ZenzLib:
    def __init__(self, remote_host, remote_host_mac, interface, remote_port, remote_host_short, remote_ssh_port,
                 guck_path, remote_virtualenv):
        self.REMOTE_HOST = remote_host
        self.REMOTE_HOST_MAC = remote_host_mac
        self.INTERFACE = interface
        self.REMOTE_PORT = remote_port
        self.REMOTE_HOST_SHORT = remote_host_short
        self.REMOTE_SSH_PORT = remote_ssh_port
        self.GUCK_PATH = guck_path
        self.REMOTE_VIRTUALENV = remote_virtualenv

    def request_to_guck(self, txt, url="etec.iv.at", port="5558"):
        context = zmq.Context()
        socket = context.socket(zmq.REQ)
        socket.setsockopt(zmq.LINGER, 0)
        socket.connect("tcp://" + url + ":" + port)
        socket.RCVTIMEO = 1000
        socket.send_string(txt)
        try:
            res0 = socket.recv_pyobj()
            socket.close()
            context.term()
            return True, res0
        except zmq.ZMQError as e:
            socket.close()
            context.term()
            time.sleep(0.1)
            return False, "GUCK connection error: " + str(e)

    def get_sens_temp(self, hostn="raspisens", filen="/home/pi/sens.txt"):
        procstr = "cat " + filen
        ssh = subprocess.Popen(["ssh", hostn, procstr], shell=False, stdout=subprocess.PIPE, stderr=subprocess. PIPE)
        sshres = ssh.stdout.readlines()
        n = 0
        temp = 0
        hum = 0
        for s in sshres:
            s0 = s.decode("utf-8").split(" ")
            temp += float(s0[2])
            hum += float(s0[3])
            n += 1
        if n > 0:
            temp = temp / n
            hum = hum / n
        return temp, hum

    def get_external_ip(self, hostlist=[("WAN2TMO_DHCP", "ubuntuserver"), ("WAN_DHCP", "ubuntuvm2")]):
        procstr = 'curl https://api.ipdata.co/"$(dig +short myip.opendns.com @resolver1.opendns.com)"'
        iplist = []
        for gateway, hostn in hostlist:
            try:
                ssh = subprocess.Popen(["ssh", hostn, procstr], shell=False, stdout=subprocess.PIPE, stderr=subprocess. PIPE)
                sshres = ssh.stdout.readlines()
                s0 = ""
                for ss in sshres:
                    s0 += ss.decode("utf-8")
                d = json.loads(s0)
                iplist.append((gateway, hostn, d["ip"], d["organisation"], "status", "N/A", "N/A", "N/A", "N/A"))
            except Exception as e:
                iplist.append((gateway, hostn, "N/A", "N/A", "N/A", "N/A", "N/A", "N/A", "N/A"))
        try:
            r = requests.get("https://pfsense.iv.at/status_gateways_json.php?key=pfsense", verify=False)
            rjson = r.json()
        except Exception as e:
            rjson = {}
        if rjson:
            for i, (gateway, hostn, ip, org, _, _, _, _, _) in enumerate(iplist):
                for key, item in rjson.items():
                    if item["name"] == gateway:
                        iplist[i] = (gateway, hostn, ip, org, item["status"], item["monitorip"], item["sourceip"], item["delay"], item["loss"])
        return iplist

    def killguck(self):
        hostn = self.REMOTE_HOST_SHORT
        etec_cmd1 = self.REMOTE_VIRTUALENV + " " + self.GUCK_PATH + "guck.py"
        etec_killstr2 = self.REMOTE_VIRTUALENV + " -u -c import sys;exec(eval(sys.stdin.readline()))"
        killstr = "ssh " + hostn + " killall -9e " + "'" + etec_cmd1 + "'"
        killstr2 = "ssh " + hostn + " killall -9e " + "'" + etec_killstr2 + "'"
        try:
            os.system(killstr)
            os.system(killstr2)
        except:
            pass

    def shutdown(self):
        hostn = self.REMOTE_HOST_SHORT
        # procstr = "/sbin/shutdown -h now"
        ssh = subprocess.Popen(["ssh", hostn, "sudo /bin/systemctl", "poweroff"], shell=False, stdout=subprocess.PIPE, stderr=subprocess. PIPE)
        return ssh

    def reboot(self):
        hostn = self.REMOTE_HOST_SHORT
        ssh = subprocess.Popen(["ssh", hostn, "sudo /bin/systemctl", "reboot"], shell=False, stdout=subprocess.PIPE, stderr=subprocess. PIPE)
        return ssh

    def ping(self):
        # return:  status, pingstr
        #     status:    1 ... host alive,
        #                0 ... down,
        #                -1 ... error in ping
        #     pingstr:   "etec.iv.at alive", "etec.iv.at down"
        ssh = subprocess.Popen(["ping", "-c 1", "-w 1", self.REMOTE_HOST], shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        sshres = ssh.stdout.readlines()
        try:
            pingstr1 = sshres[1].decode("utf-8")
            pingstr2 = sshres[2].decode("utf-8")
            if pingstr2[0:3] == "---":
                pingstr = self.REMOTE_HOST + " down!"
                stat = 0
            elif pingstr1[0:8] == "64 bytes":
                pingstr = self.REMOTE_HOST + " alive: " + pingstr1
                stat = 1
            else:
                stat = 0
                pingstr = self.REMOTE_HOST + " down!"
            return stat, pingstr
        except Exception as e:
            return -1, str(e)

    def lanwake(self):
        ssh = subprocess.Popen(["/usr/sbin/etherwake", "-i", self.INTERFACE, self.REMOTE_HOST_MAC], shell=False,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return ssh

    def get_nr_instances(self):
        etec_cmd1 = self.REMOTE_VIRTUALENV
        etec_cmd2 = self.GUCK_PATH + "guck.py"
        hoststr = etec_cmd1 + " " + etec_cmd2
        procstr = "ps aux | grep '" + hoststr + "' | wc -l"
        ssh = subprocess.Popen(["ssh", self.REMOTE_HOST_SHORT, procstr], shell=False, stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
        sshres = ssh.stdout.readlines()
        try:
            noservers = int(sshres[0].decode("utf-8"))-2
        except:
            noservers = 0
        return noservers

    def startguck(self):
        etec_cmd00 = "nohup " + self.GUCK_PATH + "../../scripts/startguck.sh"
        print(etec_cmd00)
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.REMOTE_HOST_SHORT, port=int(self.REMOTE_SSH_PORT))
        stdin, stdout, stderr = ssh.exec_command(etec_cmd00 + " > " + self.GUCK_PATH + "../../log/gucklog.log 2>&1 &")
        print(stderr)
