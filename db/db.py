from pymongo import MongoClient
import dotenv
from urllib.parse import quote_plus
import pprint
from bson.objectid import ObjectId
import os
import time
from datetime import datetime
from utils import utils

dotenv.load_dotenv(dotenv.find_dotenv())
MONGO_PASS = os.getenv("MONGO_PASS")
MONGO_USR = os.getenv("MONGO_USR")

CONN_STR = f"mongodb+srv://{quote_plus(MONGO_USR)}:{quote_plus(MONGO_PASS)}@botcluster.6z4atou.mongodb.net/?retryWrites=true&w=majority&appName=botcluster"

client = MongoClient(CONN_STR)



theseusdb = client.theseusdb
reminder_collection = theseusdb.reminder_collection
timezones_collection = theseusdb.timezones_collection
polls_collection = theseusdb.polls_collection

def create_rem_doc(userId, title, desc, date, time, jobId):
    doc = {
        "userId" : userId,
        "time" : utils.user_input_to_utc_unix(date, time, get_user_tz(userId)),
        "job_id": jobId,
        
        "title" : title,
        "desc" : desc
    }
    
    reminder_collection.insert_one(doc)
    print("successfully inserted reminder doc")
    
def remove_rem_doc(jobId):
    reminder_collection.delete_one({"job_id": jobId})
    print("removed doc")

def list_user_reminders(userId):
    return list(reminder_collection.find({"userId": userId}))

def get_reminder_by_job_id(jobId):
    return reminder_collection.find_one({"job_id": jobId})
    
def create_tz_doc(userId, timezone):
    doc = {
        "userId": userId,
        "timezone": timezone
    }
    if not timezones_collection.find_one({"userId":userId}):
        timezones_collection.insert_one(doc)
        print("successfully inserted timezone doc")
    else:
        timezones_collection.update_one({"userId":userId},{"$set":{"timezone":timezone}})
        print("successfully updated timezone doc")
        
def get_user_tz(userId) -> str:
    data = timezones_collection.find_one({"userId":userId})
    
    if data:
        return data["timezone"]
    else:
        return "-1"
    
def ensure_indexes():
    try:
        # Unique job_id to prevent duplicate records
        reminder_collection.create_index([
            ("job_id", 1)
        ], name="job_id_unique", unique=True)

        # Helpful lookups
        reminder_collection.create_index([
            ("userId", 1)
        ], name="userId_idx")
        reminder_collection.create_index([
            ("time", 1)
        ], name="time_idx")

        # Ensure single timezone per user
        timezones_collection.create_index([
            ("userId", 1)
        ], name="userId_tz_unique", unique=True)
        
        # Poll indexes
        polls_collection.create_index([
            ("message_id", 1)
        ], name="message_id_unique", unique=True)
        polls_collection.create_index([
            ("creator_id", 1)
        ], name="creator_id_idx")
    except Exception as e:
        print(f"Index creation warning: {e}")

# Initialize indexes on import
ensure_indexes()
    
    
    
