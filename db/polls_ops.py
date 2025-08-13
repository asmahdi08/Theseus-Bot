from .dbmanager import polls_collection
from .dbmanager import logger
from bson.objectid import ObjectId

def rem_poll_doc(poll_id):
    try:
        # Try to find by ObjectId first
        try:
            result = polls_collection.delete_one({"_id": ObjectId(poll_id)})
            if result.deleted_count > 0:
                logger.debug(f"Deleted poll by ObjectId {poll_id}")
                return True
        except:
            # If ObjectId fails, try by message ID
            result = polls_collection.delete_one({"poll_msg_id": poll_id})
            if result.deleted_count > 0:
                logger.debug(f"Deleted poll by message ID {poll_id}")
                return True
        
        logger.warning(f"No poll found with ID {poll_id}")
        return False
    except Exception as e:
        logger.error(f"Error deleting poll {poll_id}: {e}")
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
