from pymongo import MongoClient
import dotenv
import os
import logging

# Configure logger
logger = logging.getLogger(__name__)

dotenv.load_dotenv(dotenv.find_dotenv())
CONN_STR = os.getenv("MONGO_CONN_STR")

client = MongoClient(CONN_STR)



theseusdb = client.theseusdb
reminder_collection = theseusdb.reminder_collection
timezones_collection = theseusdb.timezones_collection
polls_collection = theseusdb.polls_collection
commands_collection = theseusdb.commands_collection
    
  

    
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
        logger.warning(f"Index creation warning: {e}")
        


# Initialize indexes on import
ensure_indexes()
    
    
    
