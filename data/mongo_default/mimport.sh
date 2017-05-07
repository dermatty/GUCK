#!/bin/bash
# has to be executed on server where mongodb runs [ubuntuserver2]
mongoimport --db guckconfig2 --collection basic --drop --file basic.json
mongoimport --db guckconfig2 --collection telegram --drop --file telegram.json
mongoimport --db guckconfig2 --collection cameras --drop --file cameras.json
mongoimport --db guckconfig2 --collection mail --drop --file mail.json
mongoimport --db guckconfig2 --collection sms --drop --file sms.json
mongoimport --db guckconfig2 --collection ftp --drop --file ftp.json
mongoimport --db guckconfig2 --collection ai --drop --file ai.json
mongoimport --db guckconfig2 --collection photo --drop --file photo.json
mongoimport --db guckconfig2 --collection remote --drop --file remote.json
