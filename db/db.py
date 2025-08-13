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
commands_collection = theseusdb.commands_collection

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

def get_missed_reminders():
    """Get all reminders that should have already been sent"""
    import time
    current_timestamp = int(time.time())
    
    # Find reminders where time < current time (past due)
    missed = list(reminder_collection.find({
        "time": {"$lt": current_timestamp}
    }))
    
    return missed

def get_active_job_ids():
    """Get list of all job IDs that currently exist in scheduler"""
    # You'll call this from bot.py since scheduler is there
    pass
    
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
    except Exception as e:
        print(f"Index creation warning: {e}")
        
def rem_poll_doc(poll_id):
    try:
        # Try to find by ObjectId first
        try:
            result = polls_collection.delete_one({"_id": ObjectId(poll_id)})
            if result.deleted_count > 0:
                print(f"Successfully deleted poll by ObjectId {poll_id}")
                return True
        except:
            # If ObjectId fails, try by message ID
            result = polls_collection.delete_one({"poll_msg_id": poll_id})
            if result.deleted_count > 0:
                print(f"Successfully deleted poll by message ID {poll_id}")
                return True
        
        print(f"No poll found with ID {poll_id}")
        return False
    except Exception as e:
        print(f"Error deleting poll {poll_id}: {e}")
        return False

def get_poll_by_id(poll_id):
    """Get poll by either ObjectId or message ID"""
    try:
        # Try ObjectId first
        poll = polls_collection.find_one({"_id": ObjectId(poll_id)})
        if poll:
            return poll
    except:
        pass
    
    # Try message ID
    poll = polls_collection.find_one({"poll_msg_id": poll_id})
    return poll
    
def get_all_polls():
    polls = polls_collection.find()
    
    return polls

def add_command_doc(command_name, message):
    
    doc = {
        "command_name" : command_name,
        "message" : message
    }
    
    commands_collection.insert_one(doc)
    
def get_existing_command_names():
    docs = commands_collection.find()
    
    names = []
    
    for doc in docs:
        name = doc["command_name"]
        names.append(name)
        
    return names

def get_reply(command_name):
    doc = commands_collection.find_one({"command_name":command_name})
    
    msg = doc["message"]
    
    return msg

def rem_custom_command(command_name):
    commands_collection.delete_one({"command_name":command_name})
    print("removed command: ",command_name)
    
def get_all_commands():
    commands = commands_collection.find()
    
    return commands


# Initialize indexes on import
ensure_indexes()
    
    
    
