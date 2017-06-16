from qhue import Bridge
import requests
import json
from datetime import datetime
import random

class Hue:
    def __init__(self, ip="192.168.1.247", username="qxhVgcSwVwIymX7OhX4KQYqt9v8QP8whdr2ecX4Y"):
        self.fullurl = "http://" + ip + "/api/" + username + "/"
        self.apiurl = "/api/" + username + "/"
        self.ip = ip
        self.username = username
        self.b = Bridge(ip, username)

    # ## LIGHTS ######################################################
    def get_lights(self):
        ret = [l for l in self.b.lights()]
        return ret

    def set_all_lights(self, onoff):
        ll = [l for l in self.b.lights()]
        for ll0 in ll:
            self.b.lights[int(ll0)].state(on=onoff)

    def get_lights_status(self, l):
        return [(self.b.lights[int(s)]()["state"]["on"], self.b.lights[int(s)]()["state"]["reachable"]) for s in l]

    def set_light_on(self, nr):
        self.b.lights[int(nr)].state(on=True)

    def set_light_off(self, nr):
        self.b.lights[int(nr)].state(on=False)

    def set_lights_on(self, l):
        for l0 in l:
            self.b.lights[int(l0)].state(on=True)

    def set_lights_off(self, l):
        for l0 in l:
            self.b.lights[int(l0)].state(on=False)

    # ## GROUPS ######################################################
    def get_all_groups(self):
        return [g for g in self.b.groups()]

    def get_groups_status(self, g):
        return [self.b.groups[int(gg)]()["action"]["on"] for gg in g]

    def set_group_on(self, nr):
        self.b.groups[int(nr)].action(on=True)

    def set_group_off(self, nr):
        self.b.groups[int(nr)].action(on=False)

    def delete_groups(self, g):
        for g0 in g:
            self.b("groups", int(g0), http_method="delete")

    def delete_all_groups(self):
        g = self.get_all_groups()
        self.delete_groups(g)

    def set_new_group(self, l):
        body_g = {
                "name": "Living room",
                "type": "Room",
                "class": "Living room",
                "lights": l
                 }
        url = self.fullurl + "groups"
        r = requests.post(url, json.dumps(body_g), timeout=5)
        return r.json()

    def set_groups_on(self, l):
        for l0 in l:
            self.b.groups[int(l0)].action(on=True)

    def set_groups_off(self, l):
        for l0 in l:
            self.b.groups[int(l0)].action(on=False)

    # ## SCHEDULES ######################################################
    def get_all_schedules(self):
        return [s for s in self.b.schedules()]

    def delete_schedules(self, s):
        for s0 in s:
            self.b("schedules", int(s0), http_method="delete")

    def delete_all_schedules(self):
        s = self.get_all_schedules()
        self.delete_schedules(s)

    def convert_mins_to_str(self, mins):
        hh = int(mins / 60)
        mm = int(mins - hh * 60)
        hhstr = "0" + str(hh) if len(str(hh)) < 2 else str(hh)
        mmstr = "0" + str(mm) if len(str(mm)) < 2 else str(mm)
        ssstr = "00"
        return hhstr, mmstr, ssstr

    def set_schedule_request(self, g, lt, on):
        actionstr = self.apiurl + "groups/" + str(g) + "/action"
        print(actionstr)
        body = {
            "name": "sched" + lt + str(on),
            "description": "schedule" + lt + str(on),
            "command": {
                "address": actionstr,
                "body": {
                    "on": on
                },
                "method": "PUT"
            },
            "localtime": lt,
            "status": "enabled",
        }
        url = self.fullurl + "schedules"
        r = requests.post(url, json.dumps(body), timeout=5)
        return r.json()

    def set_schedule(self, timercmd, g, mins, on, ww="0b01111111"):
        # timercmd: "timer", "allweek", "weekdays"
        hhstr, mmstr, ssstr = self.convert_mins_to_str(mins)
        if timercmd == "allweek":
            w = str(int("0b01111111", 2))
            lt = "W" + w + "/T" + hhstr + ":" + mmstr + ":" + ssstr
        elif timercmd == "timer":
            lt = "PT" + hhstr + ":" + mmstr + ":" + ssstr
        elif timercmd == "weekdays":
            w = str(int("0b01111100", 2))
            lt = "W" + w + "/T" + hhstr + ":" + mmstr + ":" + ssstr
        elif timercmd == "oneoff":
            lt = "W" + ww + "/T" + hhstr + ":" + mmstr + ":" + ssstr
        r = self.set_schedule_request(g, lt, on)
        return r

    def sethue_timestr(self, nr):
        # weekday: 1 = Monday, 2 = Tuesday, ...
        w = "0b00000000"
        if nr + 2 > len(w):
            nr = 1
        try:
            w_new = w[:nr+1] + "1" + w[nr+3:]
        except:
            w_new = w[:nr+1] + "1"
        w0 = str(int(w_new, 2))
        return w0

    def set_weekly_random_schedules(self, g, start_mins, duration_mins, start_random_t, duration_random_t):
        # generates 7 schedules for every of day of the week
        for i in range(1):
            weekday = i + 1
            w0 = self.sethue_timestr(weekday)
            # start
            start0 = start_mins + random.randint(-start_random_t, start_random_t)
            if start0 > 24*60:
                start0 -= 24*60
                weekday += 1
                w0 = self.sethue_timestr(weekday)
            self.set_schedule("oneoff", g, start0, True, ww=w0)
            # end
            dur = duration_mins + random.randint(-duration_random_t, duration_random_t)
            if dur < 0:
                dur = 5
            end0 = start0 + dur
            if end0 > 24*60:
                end0 -= 24*60
                weekday += 1
                w0 = self.sethue_timestr(weekday)
            self.set_schedule("oneoff", g, end0, False, ww=w0)

    def set_schedule_allweek(self, g, mins, on):
        return self.set_schedule("allweek", g, mins, on)

    def set_schedule_timer(self, g, mins, on):
        return self.set_schedule("timer", g, mins, on)


if __name__ == "__main__":
    # HUE test main
    #    - delete all groups and schedules
    #    - set up new group with all lights
    #    - turn group (=all lights) off
    #    - set allweek schedule: turn on in 2 mins, turn off in 4 mins

    hue = Hue()

    # set up everything new
    hue.delete_all_groups()
    hue.delete_all_schedules()
    l = hue.get_lights()
    print("Set new group:", hue.set_new_group(l))
    gl = hue.get_all_groups()
    hue.set_groups_on(gl)

    # set new schedules: turn all groups on in 2 mins and off in 4 mins
    for g in gl:
        #now = datetime.now()
        #starttime = now.hour * 60 + now.minute + 2
        #enddtime = now.hour * 60 + now.minute + 4
        # for every weekday random sched.: 19.30h +/- 45 min for 5 hours +/- 45 min
        hue.set_weekly_random_schedules(g, int(19.5 * 60), 5*60, 45, 45)
    for s in hue.get_all_schedules():
        print(hue.b.schedules[int(s)]())
    hue.delete_all_schedules()
