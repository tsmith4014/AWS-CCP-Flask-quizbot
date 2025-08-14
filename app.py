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

# Initialize Flask app and logging
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)

# Slack credentials from environment
SLACK_SIGNING_SECRET = os.environ['SLACK_SIGNING_SECRET']
SLACK_BOT_TOKEN = os.environ['SLACK_BOT_TOKEN']

# Quiz state
quiz_sessions = {}

def verify_slack_request(data, timestamp, signature):
    req = str.encode('v0:' + str(timestamp) + ':') + data
    request_hash = 'v0=' + hmac.new(
        str.encode(SLACK_SIGNING_SECRET),
        req, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(request_hash, signature)

# Load questions from file
def load_lookup_table(file_path):
    with open(file_path, 'r') as f:
        data = json.load(f)
        return data['practice_exam_a']

lookup_table = load_lookup_table('./qa_lookup.json')

def generate_unique_id(prefix):
    return f"{prefix}_{uuid4().hex[:8]}"

def create_checkbox_block(options):
    block_id = generate_unique_id("answer_block")
    action_id = generate_unique_id("select_answer")
    return {
        "type": "actions",
        "block_id": block_id,
        "elements": [
            {
                "type": "checkboxes",
                "action_id": action_id,
                "options": [
                    {
                        "text": {"type": "plain_text", "text": option, "emoji": True},
                        "value": str(i + 1)
                    } for i, option in enumerate(options[1:])
                ]
            },
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Submit", "emoji": True},
                "value": "submit",
                "action_id": "submit_answer"
            }
        ]
    }

def create_question_blocks(question_text, options, response_text=None):
    blocks = []
    if response_text:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": response_text}
        })
    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": question_text}
    })
    blocks.append(create_checkbox_block(options))
    return blocks

@app.route('/start_quiz', methods=['POST'])
def start_quiz():
    if 'X-Slack-Request-Timestamp' not in request.headers or 'X-Slack-Signature' not in request.headers:
        return jsonify({"error": "Unauthorized"}), 403

    timestamp = request.headers['X-Slack-Request-Timestamp']
    signature = request.headers['X-Slack-Signature']
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return jsonify({"error": "Expired"}), 403
    if not verify_slack_request(request.get_data(), timestamp, signature):
        return jsonify({"error": "Invalid signature"}), 403

    try:
        data = request.form
        num_questions = int(data.get('text', 5))
        user_id = data.get('user_id')
        response_url = data.get('response_url')

        questions = list(lookup_table.keys())
        quiz_sessions[user_id] = {
            "questions": random.sample(questions, num_questions),
            "current_question": 0,
            "score": 0,
            "num_questions": num_questions,
            "selected_answers": [],
            "response_url": response_url
        }

        current_question = quiz_sessions[user_id]["questions"][0]
        question_parts = current_question.split('. ', 1)
        options = [part.strip() for part in question_parts[1].split('\n') if part.strip()]
        quiz_sessions[user_id]['options'] = options

        blocks = create_question_blocks(f"Question 1: {options[0]}", options)

        requests.post(response_url, json={
            "response_type": "in_channel",
            "blocks": blocks,
            "text": f"Question 1: {options[0]}"
        })

        return jsonify({"response_type": "in_channel"}), 200
    except Exception as e:
        app.logger.error(f"Error in /start_quiz: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/slack/events', methods=['POST'])
def slack_events():
    if 'X-Slack-Request-Timestamp' not in request.headers or 'X-Slack-Signature' not in request.headers:
        return jsonify({"error": "Unauthorized"}), 403

    timestamp = request.headers['X-Slack-Request-Timestamp']
    signature = request.headers['X-Slack-Signature']
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return jsonify({"error": "Expired"}), 403
    if not verify_slack_request(request.get_data(), timestamp, signature):
        return jsonify({"error": "Invalid signature"}), 403

    try:
        payload = json.loads(request.form["payload"])
        user_id = payload["user"]["id"]
        actions = payload["actions"][0]
        action_id = actions["action_id"]
        response_url = payload["response_url"]

        if user_id not in quiz_sessions:
            return jsonify({"error": "Invalid session"}), 400

        session = quiz_sessions[user_id]
        options = session['options']

        if action_id.startswith("select_answer"):
            session["selected_answers"] = [opt["value"] for opt in actions.get("selected_options", [])]
            return jsonify({"status": "ok"})

        elif action_id == "submit_answer":
            if not session["selected_answers"]:
                return jsonify({"error": "No answers selected"}), 400

            current_q = session["questions"][session["current_question"]]
            correct = lookup_table[current_q]['answer'].split('.')[0].strip().lower()
            explanation = lookup_table[current_q]['explanation']

            number_to_letter = {1: 'a', 2: 'b', 3: 'c', 4: 'd'}
            selected_letters = {number_to_letter[int(i)] for i in session["selected_answers"]}

            if {correct} == selected_letters:
                session["score"] += 1
                response = "That's correct!\n"
            else:
                response = f"That's incorrect. Correct answer: {correct.upper()}\n"

            response += f"Explanation: {explanation}\n"
            session["current_question"] += 1
            session["selected_answers"] = []

            if session["current_question"] < session["num_questions"]:
                next_q = session["questions"][session["current_question"]]
                parts = next_q.split('. ', 1)
                options = [p.strip() for p in parts[1].split('\n') if p.strip()]
                session["options"] = options
                blocks = create_question_blocks(
                    f"Question {session['current_question'] + 1}: {options[0]}",
                    options,
                    response
                )

                requests.post(response_url, json={
                    "replace_original": True,
                    "blocks": blocks,
                    "text": f"Question {session['current_question'] + 1}: {options[0]}"
                })
                return jsonify({"status": "ok"})
            else:
                final = f"{response}Quiz completed! Your score is {session['score']}/{session['num_questions']}."
                del quiz_sessions[user_id]

                requests.post(response_url, json={
                    "replace_original": True,
                    "text": final
                })
                return jsonify({"status": "ok"})

        return jsonify({"status": "unknown action"})
    except Exception as e:
        app.logger.error(f"Error in /slack/events: {str(e)}")
        return jsonify({"error": str(e)}), 500

@app.route('/')
def index():
    return "QuizBot is running!"

if __name__ == '__main__':
    app.run(host='0.0.0.0')
