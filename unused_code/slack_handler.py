import hmac
import hashlib
import time
import json
import logging
from config import Config

logger = logging.getLogger(__name__)

def verify_slack_request(data, timestamp, signature):
    """
    Verifies the Slack request signature to ensure the request is authentic.
    
    Args:
        data (bytes): The raw request data
        timestamp (str): The request timestamp
        signature (str): The Slack signature to verify
        
    Returns:
        bool: True if the signature is valid, False otherwise
    """
    req = str.encode('v0:' + str(timestamp) + ':') + data
    request_hash = 'v0=' + hmac.new(
        str.encode(Config.SLACK_SIGNING_SECRET),
        req, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(request_hash, signature)

def validate_slack_request(request):
    """
    Validates a Slack request by checking headers and signature.
    
    Args:
        request: The Flask request object
        
    Returns:
        tuple: (bool, dict) - (is_valid, error_response)
    """
    # Check required headers
    if 'X-Slack-Request-Timestamp' not in request.headers or 'X-Slack-Signature' not in request.headers:
        logger.error("Missing required Slack headers")
        return False, {"error": "Unauthorized"}, 403

    # Validate request timestamp
    timestamp = request.headers['X-Slack-Request-Timestamp']
    signature = request.headers['X-Slack-Signature']
    
    if abs(time.time() - int(timestamp)) > Config.MAX_REQUEST_AGE:
        logger.error("Request timestamp too old")
        return False, {"error": "Unauthorized"}, 403

    # Verify Slack request signature
    if not verify_slack_request(request.get_data(), timestamp, signature):
        logger.error("Slack request verification failed")
        return False, {"error": "Unauthorized"}, 403

    return True, None, None

def create_question_blocks(question_data):
    """
    Creates Slack message blocks for a quiz question.
    
    Args:
        question_data (dict): Dictionary containing question text, options, and question number
        
    Returns:
        list: List of Slack message blocks
    """
    return [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"Question {question_data['question_number']}: {question_data['question_text']}"
            }
        },
        {
            "type": "actions",
            "block_id": "answer_block",
            "elements": [
                {
                    "type": "checkboxes",
                    "action_id": "select_answer",
                    "options": [{"text": {"type": "plain_text", "text": opt}, "value": str(i+1)} 
                              for i, opt in enumerate(question_data['options'])]
                },
                {
                    "type": "button",
                    "text": {
                        "type": "plain_text",
                        "text": "Submit"
                    },
                    "value": "submit",
                    "action_id": "submit_answer"
                }
            ]
        }
    ] 
