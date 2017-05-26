#!/home/stephan/.virtualenvs/cvp0/bin/python
import sys
import getpass
sys.path.append("../../lib")

from hasher import hash_password, check_password, read_hashfile, write_hashfile

hashfile = "../../data/hash.pw"

pwdict = read_hashfile(hashfile)

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
        oldpw = getpass.getpass(prompt="User already exists, enter old pw to modify/delete: ")
        if not check_password(pwdict[user]["pw"], oldpw):
            print("wrong pw, skipped this one!")
            continue
        ok = input("Do you want to delete or modify? [d/m] ")
        if ok == "d":
            del pwdict[user]
            continue
    newpw = getpass.getpass("Please enter new password: ")
    newpw_check = getpass.getpass("Please confirm new password: ")
    if newpw != newpw_check:
        print("Wrong confirmation, skipped this one!")
        continue
    hashed_new = hash_password(newpw)
    pwdict[user] = {"pw": hash_password(newpw)}
print(pwdict)

write_hashfile(hashfile, pwdict)
