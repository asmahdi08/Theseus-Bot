from .dbmanager import reminder_collection
from .dbmanager import logger
from .user_ops import get_user_tz
from utils import utils


def remove_rem_doc(jobId):
    result = reminder_collection.delete_one({"job_id": jobId})
    if result.deleted_count > 0:
        logger.debug(f"Removed reminder document for job {jobId}")
    else:
        logger.warning(f"No reminder document found for job {jobId}")

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
  
def create_rem_doc(userId, title, desc, date, time, jobId):
    doc = {
        "userId" : userId,
        "time" : utils.user_input_to_utc_unix(date, time, get_user_tz(userId)),
        "job_id": jobId,
        
        "title" : title,
        "desc" : desc
    }
    
    reminder_collection.insert_one(doc)
    logger.debug(f"Created reminder document for job {jobId}")