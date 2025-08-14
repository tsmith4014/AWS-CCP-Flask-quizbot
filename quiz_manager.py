import json
import random
import logging
import os
from typing import Dict, List, Optional
import filelock

logger = logging.getLogger(__name__)

class QuizManager:
    def __init__(self, lookup_file_path: str):
        """
        Initialize the QuizManager with a lookup file containing questions and answers.
        
        Args:
            lookup_file_path (str): Path to the JSON file containing quiz data
        """
        self.lookup_table = self._load_lookup_table(lookup_file_path)
        self.sessions_file = 'quiz_sessions.json'
        self.lock_file = 'quiz_sessions.lock'
        self._ensure_sessions_file()

    def _ensure_sessions_file(self):
        """Ensure the sessions file exists and is valid JSON."""
        if not os.path.exists(self.sessions_file):
            with open(self.sessions_file, 'w') as f:
                json.dump({}, f)

    def _load_sessions(self) -> Dict:
        """Load quiz sessions from file with locking."""
        with filelock.FileLock(self.lock_file):
            with open(self.sessions_file, 'r') as f:
                return json.load(f)

    def _save_sessions(self, sessions: Dict):
        """Save quiz sessions to file with locking."""
        with filelock.FileLock(self.lock_file):
            with open(self.sessions_file, 'w') as f:
                json.dump(sessions, f)

    def _load_lookup_table(self, file_path: str) -> dict:
        """
        Load the quiz data from a JSON file.
        
        Args:
            file_path (str): Path to the JSON file
            
        Returns:
            dict: The loaded quiz data
        """
        try:
            with open(file_path, 'r') as file:
                data = json.load(file)
                return data['practice_exam_a']
        except Exception as e:
            logger.error(f"Error loading lookup table: {str(e)}")
            raise

    def start_quiz(self, user_id: str, num_questions: int = 5) -> dict:
        """
        Start a new quiz session for a user.
        
        Args:
            user_id (str): The Slack user ID
            num_questions (int): Number of questions in the quiz
            
        Returns:
            dict: The first question and options
        """
        questions = list(self.lookup_table.keys())
        selected_questions = random.sample(questions, num_questions)
        
        # Load existing sessions
        sessions = self._load_sessions()
        
        # Store the quiz session
        sessions[user_id] = {
            "questions": selected_questions,
            "current_question": 0,
            "score": 0,
            "num_questions": num_questions,
            "selected_answers": []
        }
        
        # Save updated sessions
        self._save_sessions(sessions)
        
        return self._get_current_question(user_id)

    def _get_current_question(self, user_id: str) -> dict:
        """
        Get the current question for a user's quiz session.
        
        Args:
            user_id (str): The Slack user ID
            
        Returns:
            dict: The current question and options
        """
        sessions = self._load_sessions()
        if user_id not in sessions:
            raise KeyError(f"No active quiz session for user {user_id}")
            
        session = sessions[user_id]
        current_question = session["questions"][session["current_question"]]
        question_parts = current_question.split('. ', 1)
        options = [part.strip() for part in question_parts[1].split('\n') if part.strip()]
        
        return {
            "question_text": options[0],
            "options": options[1:],
            "question_number": session["current_question"] + 1
        }

    def submit_answer(self, user_id: str, selected_answers: List[str]) -> dict:
        """
        Submit an answer for the current question and move to the next question.
        
        Args:
            user_id (str): The Slack user ID
            selected_answers (List[str]): List of selected answer indices
            
        Returns:
            dict: The result of the answer submission and next question if available
        """
        sessions = self._load_sessions()
        if user_id not in sessions:
            raise KeyError(f"No active quiz session for user {user_id}")
            
        session = sessions[user_id]
        current_question = session["questions"][session["current_question"]]
        correct_answer = self.lookup_table[current_question]['answer']
        explanation = self.lookup_table[current_question]['explanation']
        
        # Map selected numbers to letters
        number_to_letter = {1: 'a', 2: 'b', 3: 'c', 4: 'd', 5: 'e'}
        user_selected_letters = {number_to_letter[int(i)] for i in selected_answers}
        
        # Parse correct answers - they can be multiple letters separated by commas
        correct_letters = {letter.strip().lower() for letter in correct_answer.split(',')}
        
        # Check if all correct answers are selected and no incorrect ones
        is_correct = user_selected_letters == correct_letters
        if is_correct:
            session["score"] += 1
        
        # Move to next question
        session["current_question"] += 1
        session["selected_answers"] = []
        
        # Update sessions
        sessions[user_id] = session
        self._save_sessions(sessions)
        
        result = {
            "is_correct": is_correct,
            "correct_answers": [letter.upper() for letter in sorted(correct_letters)],
            "explanation": explanation,
            "score": session["score"],
            "total_questions": session["num_questions"]
        }
        
        # Get next question if available
        if session["current_question"] < session["num_questions"]:
            result["next_question"] = self._get_current_question(user_id)
        else:
            # Remove the completed quiz session
            sessions = self._load_sessions()
            del sessions[user_id]
            self._save_sessions(sessions)
        
        return result 
