# AWS CCP QuizBot

A simple Slack bot for AWS Cloud Practitioner exam practice, designed to run on EC2.

## Deploy to EC2

### 1. Launch EC2 Instance
- **AMI:** Amazon Linux 2
- **Instance Type:** t3.micro (free tier) or larger
- **Security Group:** Allow HTTP (80), HTTPS (443), SSH (22)

### 2. SSH into Your Instance
```bash
ssh -i your-key.pem ec2-user@your-ec2-public-ip
```

### 3. Install Dependencies
```bash
# Update and install Python + Git
sudo yum update -y
sudo yum install python3 python3-pip git -y

# Install Flask and requests
pip3 install Flask requests
```

### 4. Deploy Application
```bash
# Clone the repo
cd /home/ec2-user
git clone https://github.com/tsmith4014/AWS-CCP-Flask-quizbot.git
cd AWS-CCP-Flask-quizbot

# Set your Slack tokens (replace with your actual tokens)
export SLACK_SIGNING_SECRET=your_slack_signing_secret_here
export SLACK_BOT_TOKEN=xoxb-your_bot_token_here

# Test run the app
python3 app.py
```

### 5. Create Slack App
1. Go to [api.slack.com/apps](https://api.slack.com/apps)
2. Create New App → From scratch
3. Add these Bot Token Scopes:
   - `chat:write`
   - `commands`
4. Install to workspace
5. Copy your **Bot Token** and **Signing Secret**

### 6. Configure Slack Slash Command
1. Go to "Slash Commands" in your Slack app
2. Create command: `/start_quiz`
3. Set Request URL: `http://your-ec2-public-ip:5000/start_quiz`

### 7. Run as System Service (Recommended)
Create `/etc/systemd/system/flask_app.service`:

```ini
[Unit]
Description=QuizBot - AWS CCP Quiz Slack Application

[Service]
User=ec2-user
WorkingDirectory=/home/ec2-user/AWS-CCP-Flask-quizbot
Environment="SLACK_SIGNING_SECRET=your_slack_signing_secret_here"
Environment="SLACK_BOT_TOKEN=xoxb-your_bot_token_here"
ExecStart=/usr/bin/python3 /home/ec2-user/AWS-CCP-Flask-quizbot/app.py
Restart=always

[Install]
WantedBy=multi-user.target
```

Then:
```bash
sudo systemctl daemon-reload
sudo systemctl enable flask_app
sudo systemctl start flask_app

# Check status
sudo systemctl status flask_app
```

### 8. Test Your Bot
Go to your Slack workspace and type `/start_quiz 3`

## Files

- `app.py` - Main Flask application
- `qa_lookup.json` - 65 AWS CCP practice questions
- `requirements.txt` - Python dependencies

## Troubleshooting

### Check App Status
```bash
sudo systemctl status flask_app
sudo journalctl -u flask_app -f
```

### Restart App
```bash
sudo systemctl restart flask_app
```

### Check Port
```bash
netstat -tlnp | grep :5000
```

## Known Issues

- Questions with multiple correct answers may not work properly
- Single-threaded: only one quiz session at a time
- No persistent storage (sessions reset on app restart)

That's it! Your bot should now be running on EC2 and responding to Slack commands. ��
