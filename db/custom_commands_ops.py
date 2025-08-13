from .dbmanager import commands_collection
from .dbmanager import logger

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
    result = commands_collection.delete_one({"command_name":command_name})
    if result.deleted_count > 0:
        logger.debug(f"Removed custom command: {command_name}")
    else:
        logger.warning(f"No custom command found with name: {command_name}")
    
def get_all_commands():
    commands = commands_collection.find()
    
    return commands