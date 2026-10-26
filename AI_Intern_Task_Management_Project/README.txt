# AI Intern Task Management & Review Automation

A beginner-friendly Python + Flask project to manage up to 100 interns, import/export Excel, create individual task links, explain tasks with browser voice, review submitted documents using an AI API, save feedback, and send scheduled email reminders.

## 1. Install Python
Install Python 3.11 or newer from https://www.python.org/downloads/ . During setup on Windows, tick **Add Python to PATH**.

## 2. Open the project folder
Extract `AI_Intern_Task_Management_Project.zip`.
Open the extracted folder in VS Code.

## 3. Install packages
Open Terminal in VS Code (Terminal > New Terminal) and run:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

If PowerShell blocks activation, run this instead:
```powershell
python -m pip install -r requirements.txt
```

## 4. Configure app.py
At the top of `app.py`, change:
- `ADMIN_PASSWORD` to a strong password.
- `AI_API_KEY` to your AI provider API key to enable AI voice answers and AI document reviews.
- `SMTP_EMAIL` to your Gmail address.
- `SMTP_APP_PASSWORD` to a Google App Password (not your normal Gmail password).
- Optionally change `ADMIN_NOTIFICATION_EMAIL`.

The project uses an OpenAI-compatible API. `AI_BASE_URL` and `AI_MODEL` can be adjusted for your provider. Never share your API key or upload a file containing it publicly. If no AI key is set, the basic browser text-to-speech task explanation still works, but AI-generated voice answers and AI document reviews are disabled.

For Gmail SMTP, enable 2-Step Verification in your Google account and create an App Password from Google Account security settings. Availability of App Passwords depends on your account settings.

## 5. Start the project
In the terminal, run:
```powershell
python app.py
```
Open Chrome or Edge and visit:
- Admin login: http://127.0.0.1:5000/login
- Dashboard: http://127.0.0.1:5000/dashboard

Default login (change it before use):
- Username: `admin`
- Password: `ChangeMe123!`

## 6. Add 100 interns from Excel
1. Log in to the dashboard.
2. Click **Excel Template** to download the template.
3. Fill the intern name, email, assigned task and requirements.
4. Set `Review Frequency` to `2 days` or `1 week`.
5. Upload the completed `.xlsx` file using **Import Excel**.
6. The dashboard displays a personal task link for every intern. Send the task email to deliver the link.

Required Excel columns:
- `Intern ID`
- `Intern Name`
- `Email ID`
- `Assigned Task`

Optional columns:
- `Task Requirements`
- `Review Frequency`
- `Next Review Date`
- `Review Meeting Link`

## 7. Intern workflow
1. The intern opens their personal task link.
2. Click **Explain task aloud** to hear the task requirements.
3. Click **Ask a question by voice** to ask a spoken question. Browser microphone permission is needed; voice recognition usually works in Chrome/Edge and on localhost or HTTPS.
4. Submit a PDF, DOCX, TXT or Markdown file.
5. Click **Review document with AI** to get a summary, missing points, errors, improvements and next actions.
6. Submit feedback and update task status.
7. The app sends an email after explanation completion and after AI review (when SMTP is configured).

## 8. Recurring reminders
The scheduler checks for due reviews every 30 minutes while `app.py` is running. When a due reminder is successfully sent, it schedules the next reminder based on that intern's frequency (2 or 7 days). Reminders stop for `Approved` or `Completed` tasks. If your computer is off or the Python app is stopped, reminders will not be sent during that time. For dependable 24/7 reminders, host the app on an always-on server.

## Important security and production notes
- This starter project is intended for local development and a small trusted team.
- The personal task link acts like a password: anyone who has it may see that intern's task page. Do not post links publicly.
- The admin dashboard uses a simple cookie-based login for demonstration. Before real company use, replace it with stronger session management, HTTPS, access controls, backups, and secure secret storage.
- Only upload documents you are permitted to process. AI feedback can make mistakes; a human reviewer should make final approval decisions.
- The browser voice feature reads the task aloud. Spoken Q&A and AI document review require a valid AI API key.
