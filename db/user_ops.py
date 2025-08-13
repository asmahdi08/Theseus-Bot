from .dbmanager import timezones_collection
from .dbmanager import logger


def create_tz_doc(userId, timezone):
    doc = {
        "userId": userId,
        "timezone": timezone
    }
    if not timezones_collection.find_one({"userId":userId}):
        timezones_collection.insert_one(doc)
        logger.debug(f"Created timezone document for user {userId}")
    else:
        timezones_collection.update_one({"userId":userId},{"$set":{"timezone":timezone}})
        logger.debug(f"Updated timezone document for user {userId}")
        
def get_user_tz(userId) -> str:
    data = timezones_collection.find_one({"userId":userId})
    
    if data:
        return data["timezone"]
    else:
        return "-1"