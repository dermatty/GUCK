#!/bin/bash
source "/home/stephan/.virtualenvs/cvp0/bin/activate"
cd /media/nfs_neu/GIT/GUCK/bin/wastl/
gunicorn --bind 0.0.0.0 wsgi:app>/media/nfs_neu/GIT/GUCK/log/guni_wastl.log 2>&1 &

