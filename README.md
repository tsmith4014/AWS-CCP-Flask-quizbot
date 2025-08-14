
## �� Quick Start

### 1. Prerequisites
- Python 3.8+
- Slack workspace with admin permissions
- AWS EC2 instance (Amazon Linux 2 recommended)

### 2. Clone the Repository
```bash
git clone https://github.com/tsmith4014/AWS-CCP-Flask-quizbot.git
cd AWS-CCP-Flask-quizbot
```

### 3. Environment Setup
Create a `.env` file in the project root:

```bash
# Slack Configuration
SLACK_SIGNING_SECRET=your_slack_signing_secret_here
SLACK_BOT_TOKEN=xoxb-your_bot_token_here

# Application Configuration
FLASK_DEBUG=False
SECRET_KEY=your_random_secret_key_here
LOG_LEVEL=INFO
```

### 4. Install Dependencies
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 5. Run the Application
```bash
python3 app.py
```

## 🔧 Slack Configuration

### 1. Create a Slack App
1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Click "Create New App" → "From scratch"
3. Name your app (e.g., "AWS QuizBot")
4. Select your workspace

### 2. Configure Bot Token Scopes
In "OAuth & Permissions":
- **Bot Token Scopes:**
  - `chat:write`
  - `commands`
  - `users:read`

### 3. Install App to Workspace
1. Go to "Install App" in the sidebar
2. Click "Install to Workspace"
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)

### 4. Configure Slash Command
1. Go to "Slash Commands"
2. Click "Create New Command"
3. Configure:
   - **Command:** `/start_quiz`
   - **Request URL:** `https://your-domain.com/start_quiz`
   - **Short Description:** `Start an AWS CCP practice quiz`
   - **Usage Hint:** `[number of questions]`

### 5. Get Signing Secret
1. Go to "Basic Information"
2. Copy the **Signing Secret**

## 🚀 Production Deployment (EC2)

### 1. Launch EC2 Instance
- **AMI:** Amazon Linux 2
- **Instance Type:** t3.micro (free tier) or larger
- **Security Group:** Allow HTTP (80), HTTPS (443), SSH (22)

### 2. Install Dependencies
```bash
sudo yum update -y
sudo yum install python3 python3-pip git nginx -y
sudo yum install gcc python3-devel -y
```

### 3. Deploy Application
```bash
cd /home/ec2-user
git clone https://github.com/tsmith4014/AWS-CCP-Flask-quizbot.git
cd AWS-CCP-Flask-quizbot

# Create virtual environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Create .env file with your secrets
nano .env
# Add your Slack tokens and configuration
```

### 4. Configure Systemd Service - Optional
Create `/etc/systemd/system/flask_app.service`:

```ini
[Unit]
Description=QuizBot - AWS CCP Quiz Slack Application
After=network.target nginx.service

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/AWS-CCP-Flask-quizbot
Environment="PATH=/home/ec2-user/AWS-CCP-Flask-quizbot/venv/bin"
Environment="FLASK_DEBUG=False"
Environment="LOG_LEVEL=INFO"
EnvironmentFile=/home/ec2-user/AWS-CCP-Flask-quizbot/.env
ExecStart=/home/ec2-user/AWS-CCP-Flask-quizbot/venv/bin/gunicorn --config gunicorn_config.py app:app
Restart=always

[Install]
WantedBy=multi-user.target
```

### 5. Configure Nginx - Optional
Create `/etc/nginx/conf.d/app.conf`:

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

### 6. Start Services
```bash
sudo systemctl daemon-reload
sudo systemctl enable flask_app
sudo systemctl start flask_app
sudo systemctl enable nginx
sudo systemctl start nginx
```

## �� How It Works

### 1. Quiz Flow
1. User types `/start_quiz [number]` in Slack
2. Bot sends interactive message with first question
3. User selects answers using checkboxes
4. Bot validates answers and provides feedback
5. Process repeats until quiz completion
6. Final score is displayed

### 2. Security Features
- Slack request signature verification
- Request timestamp validation (5-minute window)
- Environment variable configuration
- No hardcoded secrets

### 3. Data Structure
The `qa_lookup.json` contains 65 AWS CCP practice questions with:
- Question text and multiple choice options
- Correct answer(s)
- Detailed explanations
- Memory hooks for learning

## 🛠️ Development

### Adding New Questions
Edit `qa_lookup.json` following this format:

```json
{
  "practice_exam_a": {
    "Question text here?\na. Option A\nb. Option B\nc. Option C\nd. Option D": {
      "answer": "a. Option A",
      "explanation": "Detailed explanation here..."
    }
  }
}
```

### Testing Locally - Optional, easy to test manually in slack.
1. Set up ngrok for Slack webhook testing:
```bash
ngrok http 5000
```

2. Update Slack app Request URL with ngrok URL
3. Test slash commands in your workspace

## 🔍 Troubleshooting

### Common Issues
1. **"Unauthorized" errors:** Check Slack signing secret and bot token
2. **"Request timestamp too old":** Ensure system clock is synchronized
3. **Gunicorn won't start:** Check file permissions and virtual environment
4. **Nginx 502 errors:** Verify Flask app is running on port 5000

### Logs
```bash
# Flask app logs
sudo journalctl -u flask_app -f

# Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## �� API Endpoints

- `GET /` - Health check
- `POST /start_quiz` - Start new quiz session
- `POST /slack/events` - Handle Slack interactions

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## 📄 License

This project is open source and available under the [MIT License](LICENSE).

## 🆘 Support

For issues and questions:
1. Check the troubleshooting section
2. Review Slack app configuration
3. Verify environment variables
4. Check system logs
