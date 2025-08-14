# AWS CCP QuizBot - A Slack-based quiz application for AWS Cloud Practitioner exam practice
# This Flask application creates an interactive quiz experience where users can:
# 1. Start a quiz with a specified number of questions using /start_quiz command
# 2. Answer multiple-choice questions through Slack's interactive components
# 3. Get immediate feedback and explanations for each answer
# 4. Track their score throughout the quiz session

import os
import json
import time
import hmac
import hashlib
import random
import logging
import requests
from uuid import uuid4
from flask import Flask, request, jsonify

# Initialize Flask application and configure logging
# Flask is a lightweight web framework for Python that handles HTTP requests
app = Flask(__name__)
# Set logging level to INFO to capture important application events
logging.basicConfig(level=logging.INFO)

# Load Slack credentials from environment variables for security
# These are set in the systemd service file on the EC2 instance
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']  # Used to verify requests come from Slack
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']            # Used to authenticate with Slack API

# In-memory storage for active quiz sessions
# This stores quiz state for each user (questions, current position, score, etc.)
# Note: This data is lost when the application restarts - for production, consider using a database
quiz_sessions = {}

def verify_slack_request(data, timestamp, signature):
    """
    Verify that the incoming request is actually from Slack using cryptographic signature verification.
    
    This is a security measure to prevent unauthorized requests to your bot.
    Slack sends a signature that we can verify using our signing secret.
    
    Args:
        data: The raw request body data
        timestamp: When the request was sent (for replay attack protection)
        signature: The cryptographic signature from Slack
    
    Returns:
        bool: True if signature is valid, False otherwise
    """
    # Create the string that Slack used to generate the signature
    # Format: 'v0:' + timestamp + ':' + request_body
    req = str.encode('v0:' + str(timestamp) + ':') + data
    
    # Generate our own hash using the same method Slack used
    # HMAC-SHA256 with our signing secret as the key
    request_hash = 'v0=' + hmac.new(
        str.encode(SLACK_SIGNING_SECRET),  # Our secret key
        req,                               # The string to hash
        hashlib.sha256                     # Hash algorithm
    ).hexdigest()
    
    # Compare our hash with Slack's signature using constant-time comparison
    # This prevents timing attacks
    return hmac.compare_digest(request_hash, signature)

def load_lookup_table(file_path):
    """
    Load the quiz questions and answers from a JSON file.
    
    The JSON file contains a structured format with questions as keys and
    answer/explanation pairs as values.
    
    Args:
        file_path: Path to the JSON file containing quiz data
    
    Returns:
        dict: Dictionary containing all quiz questions and their answers
    """
    with open(file_path, 'r') as f:
        data = json.load(f)
        # Return the 'practice_exam_a' section which contains the actual questions
        return data['practice_exam_a']

# Load all quiz questions into memory when the application starts
# This makes question lookup fast during quiz sessions
lookup_table = load_lookup_table('./qa_lookup.json')

def generate_unique_id(prefix):
    """
    Generate a unique identifier for Slack block elements.
    
    Slack requires unique IDs for interactive elements like buttons and checkboxes.
    We combine a prefix with a random UUID to ensure uniqueness.
    
    Args:
        prefix: A descriptive prefix for the ID (e.g., "answer_block", "select_answer")
    
    Returns:
        str: A unique identifier like "answer_block_a1b2c3d4"
    """
    return f"{prefix}_{uuid4().hex[:8]}"  # Use first 8 characters of UUID for readability

def create_checkbox_block(options):
    """
    Create a Slack message block containing checkboxes for answer selection and a submit button.
    
    Slack blocks are the building blocks of rich messages. This function creates:
    1. Checkboxes for each answer option
    2. A submit button to confirm the selection
    
    Args:
        options: List of answer options (first element is the question, rest are answers)
    
    Returns:
        dict: A Slack actions block with checkboxes and submit button
    """
    # Generate unique IDs for this block to avoid conflicts
    block_id = generate_unique_id("answer_block")
    action_id = generate_unique_id("select_answer")
    
    return {
        "type": "actions",           # This block contains interactive elements
        "block_id": block_id,        # Unique identifier for this block
        "elements": [
            {
                "type": "checkboxes",                    # Multiple choice selection
                "action_id": action_id,                  # Identifies this element in callbacks
                "options": [
                    {
                        "text": {
                            "type": "plain_text",        # Simple text (no formatting)
                            "text": option,              # The answer text
                            "emoji": True                # Allow emoji rendering
                        },
                        "value": str(i + 1)              # Value sent when selected (1, 2, 3, 4)
                    } for i, option in enumerate(options[1:])  # Skip first element (question text)
                ]
            },
            {
                "type": "button",                        # Submit button
                "text": {
                    "type": "plain_text", 
                    "text": "Submit", 
                    "emoji": True
                },
                "value": "submit",                       # Value sent when clicked
                "action_id": "submit_answer"             # Identifies this button in callbacks
            }
        ]
    }

def create_question_blocks(question_text, options, response_text=None):
    """
    Create a complete set of Slack message blocks for displaying a quiz question.
    
    This function builds the entire message structure including:
    1. Previous answer feedback (if provided)
    2. The current question text
    3. Interactive answer options
    
    Args:
        question_text: The question to display
        options: List of options (question + answers)
        response_text: Optional feedback from previous answer
    
    Returns:
        list: List of Slack message blocks forming the complete question
    """
    blocks = []
    
    # Add feedback from previous answer if provided
    if response_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": response_text}
        })
    
    # Add the main question text
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": question_text}
    })
    
    # Add the interactive answer options
    blocks.append(create_checkbox_block(options))
    
    return blocks

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    """
    Handle the /start_quiz slash command from Slack.
    
    This endpoint is called when a user types /start_quiz in Slack.
    It validates the request, creates a new quiz session, and sends the first question.
    
    The flow is:
    1. Verify the request is from Slack
    2. Parse the number of questions requested
    3. Create a new quiz session for the user
    4. Select random questions from the question bank
    5. Send the first question to the Slack channel
    """
    # Security check: Ensure required Slack headers are present
    if 'X-Slack-Request-Timestamp' not in request.headers or 'X-Slack-Signature' not in request.headers:
        return jsonify({"error": "Unauthorized"}), 403

    # Extract and validate the request timestamp
    timestamp = request.headers['X-Slack-Request-Timestamp']
    signature = request.headers['X-Slack-Signature']
    
    # Prevent replay attacks by checking if request is too old (5 minutes)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return jsonify({"error": "Expired"}), 403
    
    # Verify the request signature to ensure it's from Slack
    if not verify_slack_request(request.get_data(), timestamp, signature):
        return jsonify({"error": "Invalid signature"}), 403

    try:
        # Extract data from the Slack slash command
        data = request.form
        num_questions = int(data.get('text', 5))  # Default to 5 questions if none specified
        user_id = data.get('user_id')             # Unique Slack user identifier
        response_url = data.get('response_url')   # URL to send responses back to Slack

        # Get all available questions and randomly select the requested number
        questions = list(lookup_table.keys())
        
        # Create a new quiz session for this user
        quiz_sessions[user_id] = {
            "questions": random.sample(questions, num_questions),  # Random selection without duplicates
            "current_question": 0,                                # Start with first question
            "score": 0,                                           # Initialize score counter
            "num_questions": num_questions,                       # Total questions in this quiz
            "selected_answers": [],                               # User's selected answers for current question
            "response_url": response_url                          # Where to send responses
        }

        # Get the first question and parse its components
        current_question = quiz_sessions[user_id]["questions"][0]
        # Split on first period to separate question number from content
        question_parts = current_question.split('. ', 1)
        # Split the content by newlines to separate question from answer options
        options = [part.strip() for part in question_parts[1].split('\n') if part.strip()]
        quiz_sessions[user_id]['options'] = options

        # Create the Slack message blocks for the first question
        blocks = create_question_blocks(f"Question 1: {options[0]}", options)

        # Send the first question to Slack using the response URL
        # This makes the question visible in the channel
        requests.post(response_url, json={
            "response_type": "in_channel",  # Make response visible to everyone
            "blocks": blocks,               # Rich message with interactive elements
            "text": f"Question 1: {options[0]}"  # Fallback text for accessibility
        })

        # Return success response to Slack
        return jsonify({"response_type": "in_channel"}), 200
        
    except Exception as e:
        # Log any errors for debugging
        app.logger.error(f"Error in /start_quiz: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/slack/events', methods=['POST'])
def slack_events():
    """
    Handle interactive events from Slack (button clicks, checkbox selections).
    
    This endpoint processes user interactions with the quiz interface:
    1. When users select answer checkboxes
    2. When users click the submit button
    
    The flow for answering questions:
    1. User selects answers using checkboxes
    2. User clicks submit
    3. System checks answers against correct answers
    4. System provides feedback and moves to next question
    5. If no more questions, shows final score
    """
    # Security check: Ensure required Slack headers are present
    if 'X-Slack-Request-Timestamp' not in request.headers or 'X-Slack-Signature' not in request.headers:
        return jsonify({"error": "Unauthorized"}), 403

    # Extract and validate the request timestamp
    timestamp = request.headers['X-Slack-Request-Timestamp']
    signature = request.headers['X-Slack-Signature']
    
    # Prevent replay attacks by checking if request is too old (5 minutes)
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return jsonify({"error": "Expired"}), 403
    
    # Verify the request signature to ensure it's from Slack
    if not verify_slack_request(request.get_data(), timestamp, signature):
        return jsonify({"error": "Invalid signature"}), 403

    try:
        # Parse the interactive payload from Slack
        payload = json.loads(request.form["payload"])
        user_id = payload["user"]["id"]                    # Which user interacted
        actions = payload["actions"][0]                     # What action they performed
        action_id = actions["action_id"]                    # Type of action (select_answer, submit_answer)
        response_url = payload["response_url"]              # Where to send response

        # Verify this user has an active quiz session
        if user_id not in quiz_sessions:
            return jsonify({"error": "Invalid session"}), 400

        # Get the user's current quiz session
        session = quiz_sessions[user_id]
        options = session['options']

        # Handle checkbox selection (user choosing answers)
        if action_id.startswith("select_answer"):
            # Extract the selected answer values (1, 2, 3, 4)
            session["selected_answers"] = [opt["value"] for opt in actions.get("selected_options", [])]
            return jsonify({"status": "ok"})

        # Handle submit button click (user confirming their answer)
        elif action_id == "submit_answer":
            # Ensure user selected at least one answer
            if not session["selected_answers"]:
                return jsonify({"error": "No answers selected"}), 400

            # Get the current question and check the answer
            current_q = session["questions"][session["current_question"]]
            correct = lookup_table[current_q]['answer'].split('.')[0].strip().lower()  # Extract correct answer letter
            explanation = lookup_table[current_q]['explanation']                       # Get explanation text

            # Convert selected numbers (1,2,3,4) to letters (a,b,c,d)
            number_to_letter = {1: 'a', 2: 'b', 3: 'c', 4: 'd'}
            selected_letters = {number_to_letter[int(i)] for i in session["selected_answers"]}

            # Check if the answer is correct
            if {correct} == selected_letters:
                session["score"] += 1  # Increment score for correct answer
                response = "That's correct!\n"
            else:
                response = f"That's incorrect. Correct answer: {correct.upper()}\n"

            # Add explanation to the response
            response += f"Explanation: {explanation}\n"
            
            # Move to next question and reset selected answers
            session["current_question"] += 1
            session["selected_answers"] = []

            # Check if there are more questions
            if session["current_question"] < session["num_questions"]:
                # Get the next question
                next_q = session["questions"][session["current_question"]]
                parts = next_q.split('. ', 1)
                options = [p.strip() for p in parts[1].split('\n') if p.strip()]
                session["options"] = options
                
                # Create blocks for the next question
                blocks = create_question_blocks(
                    f"Question {session['current_question'] + 1}: {options[0]}",
                    options,
                    response  # Include feedback from previous answer
                )

                # Update the message with the next question
                requests.post(response_url, json={
                    "replace_original": True,  # Replace the current message instead of sending new one
                    "blocks": blocks,
                    "text": f"Question {session['current_question'] + 1}: {options[0]}"
                })
                return jsonify({"status": "ok"})
            else:
                # Quiz is complete - show final score
                final = f"{response}Quiz completed! Your score is {session['score']}/{session['num_questions']}."
                
                # Clean up the completed quiz session
                del quiz_sessions[user_id]

                # Update the message with final results
                requests.post(response_url, json={
                    "replace_original": True,
                    "text": final
                })
                return jsonify({"status": "ok"})

        # Handle unknown action types
        return jsonify({"status": "unknown action"})
        
    except Exception as e:
        # Log any errors for debugging
        app.logger.error(f"Error in /slack/events: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    """
    Simple health check endpoint.
    
    This route just confirms the application is running.
    Useful for monitoring and testing.
    """
    return "QuizBot is running!"

# Main application entry point
if __name__ == '__main__':
    # Start the Flask development server
    # host='0.0.0.0' makes it accessible from external connections (not just localhost)
    # This is necessary when running on EC2 or other cloud servers
    app.run(host='0.0.0.0')
