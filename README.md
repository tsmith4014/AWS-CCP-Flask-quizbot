# AWS CCP QuizBot

A simple Slack bot for AWS Cloud Practitioner exam practice, designed to run on EC2.

## How It Works - Simple Summary

### **The Magic of Slack Integration**

This bot works through a clever back-and-forth conversation with Slack:

1. **User starts quiz**: Types `/start_quiz 5` in Slack
2. **Slack calls your server**: Slack sends a POST request to your EC2 instance
3. **Your server responds**: Sends the first question back to Slack using a special URL Slack provided
4. **User answers**: Clicks checkboxes and Submit button in Slack
5. **Slack calls your server again**: Sends the user's answers to your server
6. **Your server responds**: Sends feedback and the next question back to Slack
7. **Repeat until done**: Shows final score when quiz is complete

### **The Key Insight: Response URLs**

- **Slack → Your Server**: Slack sends requests to your Flask routes (`/start_quiz`, `/slack/events`)
- **Your Server → Slack**: Your server responds using the `response_url` that Slack provides in each request
- **No Bot Token Needed**: The bot never actively sends messages - it only responds to what users do

### **Why This is Cool**

- **No webhooks needed** - Slack calls you when it needs to
- **Simple architecture** - Just two Flask routes handle everything
- **Real-time interaction** - Users get immediate feedback
- **No database required** - Quiz sessions stored in memory

---

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
3. **Set Request URL: `http://your-ec2-public-ip:5000/start_quiz`**
4. **Set Short Description: "Start an AWS CCP practice quiz"**
5. **Set Usage Hint: "[number of questions]"**

### 7. Configure Interactive Components (CRITICAL!)

1. Go to "Interactive Components" in your Slack app
2. **Set Request URL: `http://your-ec2-public-ip:5000/slack/events`**
3. **This is required for buttons and checkboxes to work!**

### 8. Run as System Service (Recommended)

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

### 9. Test Your Bot

Go to your Slack workspace and type `/start_quiz 3`

---

## How the Code Works

### **Two Main Endpoints**

1. **`/start_quiz`** - Handles the slash command, creates quiz session, sends first question
2. **`/slack/events`** - Handles button clicks and checkbox selections, processes answers

### **Quiz Flow**

1. **Start**: User types `/start_quiz 5` → Bot creates session with 5 random questions
2. **Question**: Bot sends question with checkboxes and Submit button
3. **Answer**: User selects answers and clicks Submit
4. **Feedback**: Bot shows if answer was correct/incorrect with explanation
5. **Next**: Bot shows next question or final score
6. **Cleanup**: Bot removes completed session from memory

### **Security Features**

- **Request Verification**: Uses Slack's signing secret to verify requests are authentic
- **Timestamp Validation**: Prevents replay attacks (requests older than 5 minutes rejected)
- **Session Management**: Each user gets their own isolated quiz session

---

## Files

- `app.py` - Main Flask application with detailed comments explaining every step
- `qa_lookup.json` - 65 AWS CCP practice questions with answers and explanations
- `requirements.txt` - Python dependencies
- `flask_app.service` - Systemd service file for running as background service

---

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

### Common Issues

- **Buttons not working**: Check Interactive Components URL in Slack app settings
- **Slash command not working**: Check Slash Commands URL in Slack app settings
- **App won't start**: Check environment variables in service file

---

## Known Limitations

- **Single-threaded**: Only one quiz session at a time per user
- **No persistence**: Quiz sessions reset when app restarts
- **Memory storage**: All sessions stored in application memory
- **No user management**: Anyone can start a quiz

---

## What Happens When You Use It

1. **Type `/start_quiz 3`** in Slack
2. **Bot responds** with first question and answer options
3. **Click checkboxes** to select your answer(s)
4. **Click Submit** to see if you're right
5. **Get explanation** and move to next question
6. **See final score** when all questions are answered

That's it! Your bot is now running on EC2 and responding to Slack commands.
