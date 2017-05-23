import uuid
import hashlib
import json


def hash_password(password):
    # uuid is used to generate a random number
    salt = uuid.uuid4().hex
    return hashlib.sha256(salt.encode() + password.encode()).hexdigest() + ':' + salt


def check_password(hashed_password, user_password):
    password, salt = hashed_password.split(':')
    return password == hashlib.sha256(salt.encode() + user_password.encode()).hexdigest()


def write_hashfile(fn, pwdict):
    f = open(fn, "w")
    f.write(json.dumps(pwdict))
    f.close()


def read_hashfile(fn):
    pwdict = {}
    f = open(fn, "r")
    try:
        pwdict0 = json.loads(f.read())
        for key in pwdict0:
            pwdict[key] = pwdict0[key]
    except Exception as e:
        print(e)
    f.close()
    return pwdict
