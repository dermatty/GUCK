import os
import subprocess
from paramiko import SSHClient
import paramiko


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

    def killguck(self):
        hostn = self.REMOTE_HOST_SHORT
        etec_cmd1 = self.REMOTE_VIRTUALENV + " " + self.GUCK_PATH + "guck.py"
        etec_killstr2 = self.REMOTE_VIRTUALENV + " -u -c import sys;exec(eval(sys.stdin.readline()))"
        killstr = "ssh " + hostn + " killall -9e " + "'" + etec_cmd1 + "'"
        killstr2 = "ssh " + hostn + " killall -9e " + "'" + etec_killstr2 + "'"
        os.system(killstr)
        os.system(killstr2)

    def shutdown(self):
        hostn = self.REMOTE_HOST_SHORT
        procstr = "/sbin/shutdown +0"
        ssh = subprocess.Popen(["ssh", hostn, procstr], shell=False, stdout=subprocess.PIPE, stderr=subprocess. PIPE)
        return ssh

    def ping(self):
        ssh = subprocess.Popen(["ping", "-c 1", self.REMOTE_HOST], shell=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        sshres = ssh.stdout.readlines()
        try:
            pingstr = sshres[1].decode("utf-8")
            return 0, pingstr
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
        ssh = SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.REMOTE_HOST_SHORT, port=int(self.REMOTE_SSH_PORT))
        stdin, stdout, stderr = ssh.exec_command(etec_cmd00 + " > " + self.GUCK_PATH + "../../log/gucklog.log 2>&1 &")
