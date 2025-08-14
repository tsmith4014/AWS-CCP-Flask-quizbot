import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Slack Configuration
    SLACK_SIGNING_SECRET = os.getenv('SLACK_SIGNING_SECRET')
    SLACK_BOT_TOKEN = os.getenv('SLACK_BOT_TOKEN')
    
    # Application Configuration
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())
    
    # Logging Configuration
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Security
    MAX_REQUEST_AGE = 300  # 5 minutes in seconds 
