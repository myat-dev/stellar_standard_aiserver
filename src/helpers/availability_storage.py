import time
from src.helpers.logger import logger
from src.helpers.conf_loader import LINE_WAIT_TIME

availability_responses = {}  
availability_timestamps = {} 

def mark_message_sent(user_id):
    """Call this when sending CheckAvailabilityMessage."""
    availability_timestamps[user_id] = time.time()

def set_response(user_id, response_type):
    """Set response only if it's within 20 seconds of the message being sent."""
    now = time.time()
    message_time = availability_timestamps.get(user_id)

    if message_time is None:
        logger.info(f"[set_response] No availability message timestamp for {user_id}. Ignored.")
        return

    if now - message_time > LINE_WAIT_TIME:
        logger.info(f"[set_response] Response from {user_id} expired. Ignored.")
        return

    current = availability_responses.get(user_id)
    if current != response_type:
        availability_responses[user_id] = response_type
        logger.info(f"[set_response] Stored response from {user_id}: {response_type}")
    else:
        logger.info(f"[set_response] Duplicate response from {user_id} ignored.")

def pop_response(user_id):
    availability_timestamps.pop(user_id, None)
    return availability_responses.pop(user_id, None)

def clear_all_responses():
    availability_responses.clear()
    availability_timestamps.clear()

def rank_responses(reply_messages: list):
    rank_order = ["今すぐ対応する", "2分以内に対応する", "対応出来ない"]
    best_rank = len(rank_order)
    best_text = None

    for text in reply_messages:
        if text in rank_order:
            rank = rank_order.index(text)
            if rank < best_rank:
                best_rank = rank
                best_text = text

    return best_text if best_text is not None else None
