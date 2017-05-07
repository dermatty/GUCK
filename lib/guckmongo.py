from pymongo import MongoClient
# from bson.objectid import ObjectId

# --- simple update & query ---
# db.db_update("basic", "do_heartbeat", self.doheartbeat.data)
# self.dotelegram.data = db.db_query("telegram", "do_telegram")

# --- cursor ---
# cursor = db.db_getall("cameras")
# self.cameralist = [(cn["_id"], cn["name"], cn["enable"]) for cn in cursor]

# --- complex query ---
# id0 = ObjectId(self.act_camera_id.data)
# cam0 = db.db_find_one("cameras", "_id", id0)
# self.name_c.data = cam0["name"]

# --- complex update
# id0 = ObjectId(self.act_camera_id.data)
# db.db_update2("cameras", "_id", id0, "name", self.name_c.data)


class ConfigDB:
    def __init__(self, mongopath, mongoname):
        self.client = MongoClient(mongopath)
        self.db = self.client[mongoname]
        self.db_basic = self.db.basic.find()[0]

    def db_getall(self, doc0):
        return self.db[doc0].find()

    def db_delete_one(self, doc0, name, value):
        try:
            result = self.db[doc0].delete_many({name: value})
            return result
        except Exception as e:
            print("DB delete error:", e)
            return -1

    def db_open_one(self, doc0, template):
        result = self.db[doc0].insert_one(template)
        return result.inserted_id

    def db_find_one(self, doc0, name, value):
        return self.db[doc0].find_one({name: value})

    def db_query(self, doc0, name, index=0):
        try:
            return self.db[doc0].find()[index][name]
        except Exception as e:
            print("DB Query error: ", e)
            return -1

    def db_update2(self, doc0, selector_name, selector_value, name, value):
        try:
            result = self.db[doc0].update_one({selector_name: selector_value}, {"$set":  {name: value}})
            return result
        except Exception as e:
            print("DB update error:", e)
            return -1

    def db_update(self, doc0, name, value, index=0):
        try:
            id0 = self.db_query(doc0, "_id")
            result = self.db[doc0].update_one({"_id": id0}, {"$set":  {name: value}})
            return result
        except Exception as e:
            print("DB update error:", e)
            return -1
