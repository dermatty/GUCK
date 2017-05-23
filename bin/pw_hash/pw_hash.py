#!/home/stephan/.virtualenvs/cvp0/bin/python
import sys
sys.path.append("../../lib")

from hasher import hash_password, check_password
import json

hashfile = "../../data/hash.pw"

pwdict = {}
f = open(hashfile, "r")
try:
    pwdict0 = json.loads(f.read())
    for key in pwdict0:
        pwdict[key] = pwdict0[key]
except Exception as e:
    print(e)
f.close()

while True:
    print("The hashfile contains passwords for the following users:")
    print("--------------------------------------------------------")
    for key in pwdict:
        print("  " + key)
    print("--------------------------------------------------------")
    ok = ""
    while ok.lower() not in ["y", "n"]:
        ok = input("Add new user/modify existing one? [Y/N] ")
    if ok == "n":
        break
    user = input("\nEnter user to add or to modify: ")
    if user in pwdict:
        oldpw = input("User already exists, enter old pw to modify: ")
        if not check_password(pwdict[user]["pw"], oldpw):
            print("wrong pw, skipped this one!")
            continue
        ok = "Do you want to delete or modify? [d/m] "
        if ok == "d":
            del pwdict[user]
            continue
    newpw = input("Please enter new password: ")
    newpw_check = input("Please confirm new password: ")
    if newpw != newpw_check:
        print("Wrong confirmation, skipped this one!")
        continue
    hashed_new = hash_password(newpw)
    pwdict[user] = {"pw": hash_password(newpw)}
print(pwdict)

f = open(hashfile, "w")
f.write(json.dumps(pwdict))
f.close()
