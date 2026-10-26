"""
AI Intern Task Management - Dedicated AI Chatbot Application
Run directly with: python chatbot_app.py
"""

import os
import sys
import json
import sqlite3
import re
from datetime import datetime
import requests
from flask import Flask, request, jsonify, render_template_string

# Determine base paths whether running from root or exports folder
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PARENT_DIR = os.path.dirname(SCRIPT_DIR)

# Locate database
DB_PATH = os.path.join(SCRIPT_DIR, "intern_tasks.db")
if not os.path.exists(DB_PATH) and os.path.exists(os.path.join(PARENT_DIR, "intern_tasks.db")):
    DB_PATH = os.path.join(PARENT_DIR, "intern_tasks.db")

# Locate app.py to inherit AI configuration if available
AI_API_KEY = os.environ.get("AI_API_KEY", "")
AI_BASE_URL = os.environ.get("AI_BASE_URL", "https://api.openai.com/v1")
AI_MODEL = os.environ.get("AI_MODEL", "gpt-4o-mini")

app_py_paths = [os.path.join(SCRIPT_DIR, "app.py"), os.path.join(PARENT_DIR, "app.py")]
for apath in app_py_paths:
    if os.path.exists(apath):
        try:
            with open(apath, "r", encoding="utf-8") as f:
                content = f.read()
                m_key = re.search(r'AI_API_KEY\s*=\s*["\']([^"\']*)["\']', content)
                m_url = re.search(r'AI_BASE_URL\s*=\s*["\']([^"\']*)["\']', content)
                m_model = re.search(r'AI_MODEL\s*=\s*["\']([^"\']*)["\']', content)
                if m_key and m_key.group(1):
                    AI_API_KEY = m_key.group(1)
                if m_url and m_url.group(1):
                    AI_BASE_URL = m_url.group(1)
                if m_model and m_model.group(1):
                    AI_MODEL = m_model.group(1)
        except Exception:
            pass
        break

app = Flask(__name__)
app.secret_key = "intern-chatbot-secret-key-2026"

def get_db():
    if not os.path.exists(DB_PATH):
        return None
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def query_db_insights(user_query):
    """
    Check if query is asking for intern task information and answer from SQLite
    """
    q = user_query.lower()
    keywords = ["intern", "task", "status", "pending", "completed", "review", "due", "how many", "list", "who", "summary"]
    if not any(k in q for k in keywords):
        return None

    conn = get_db()
    if not conn:
        return None

    try:
        # Check intern counts and statuses
        total_interns = conn.execute("SELECT count(*) FROM interns").fetchone()[0]
        rows = conn.execute("SELECT * FROM interns ORDER BY id DESC LIMIT 25").fetchall()
        
        if total_interns == 0:
            return "Currently, there are **no interns registered** in the database. You can import interns from Excel or add them via the Admin Dashboard."

        # Specific questions
        if "how many" in q or "count" in q or "total" in q:
            by_status = conn.execute("SELECT status, count(*) as c FROM interns GROUP BY status").fetchall()
            status_text = "\n".join([f"- **{r['status']}**: {r['c']} interns" for r in by_status])
            return f"### 📊 Intern Statistics\n\n**Total Registered Interns:** {total_interns}\n\n**Breakdown by Status:**\n{status_text}"

        if "pending" in q or "in progress" in q:
            pending = conn.execute("SELECT name, task_title, status, next_review_date FROM interns WHERE status IN ('Not Started', 'In Progress', 'Under Review') LIMIT 10").fetchall()
            if not pending:
                return "Great news! There are no pending tasks right now."
            lines = [f"| Intern Name | Task | Status | Next Review |", "|---|---|---|---|"]
            for r in pending:
                lines.append(f"| {r['name']} | {r['task_title']} | `{r['status']}` | {r['next_review_date'] or 'Not set'} |")
            return f"### ⏳ Active / Pending Tasks ({len(pending)}):\n\n" + "\n".join(lines)

        if "list" in q or "summary" in q or "show all" in q or "interns" in q or "tasks" in q:
            lines = [f"| ID | Intern Name | Task Title | Status | Review Frequency |", "|---|---|---|---|---|"]
            for r in rows[:12]:
                lines.append(f"| #{r['id']} | **{r['name']}** | {r['task_title']} | `{r['status']}` | {r['review_frequency']} |")
            res = f"### 📋 Interns & Assigned Tasks (Showing {min(len(rows), 12)} of {total_interns}):\n\n" + "\n".join(lines)
            if total_interns > 12:
                res += f"\n\n*(And {total_interns - 12} more records. Check the Admin Dashboard for the full table)*"
            return res

        # Search for a specific name
        for r in rows:
            if r['name'].lower() in q:
                return f"""### 👤 Intern Profile: **{r['name']}**
- **Email:** {r['email']}
- **Assigned Task:** {r['task_title']}
- **Status:** `{r['status']}`
- **Review Frequency:** {r['review_frequency']}
- **Next Review Date:** {r['next_review_date'] or 'Not scheduled'}
- **Requirements:** {r['requirements'] or 'None specified'}
- **Document Submitted:** {'Yes (' + r['document_filename'] + ')' if r['document_filename'] else 'No document submitted yet'}
"""
    except Exception as e:
        return f"Database query note: {e}"
    finally:
        conn.close()
    return None

def generate_smart_fallback(user_message, history):
    """
    Intelligent built-in AI response if no OpenAI API key is set
    """
    msg = user_message.lower().strip()
    
    # Check if asking database info
    db_answer = query_db_insights(user_message)
    if db_answer:
        return db_answer

    # Code / Python help
    if "python" in msg or "code" in msg or "flask" in msg or "script" in msg or "error" in msg:
        return f"""### 💡 AI Code & Python Assistant

Here is assistance related to your query:

```python
# Example: Querying Intern Tasks with SQLite in Python
import sqlite3

def get_pending_tasks():
    conn = sqlite3.connect('intern_tasks.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, task_title, status FROM interns WHERE status != 'Completed'")
    return cursor.fetchall()

# Run and inspect
tasks = get_pending_tasks()
print(f"Total active tasks: {len(tasks)}")
for t in tasks:
    print(f"- {t['name']}: {t['task_title']} ({t['status']})")
```

> **Pro-Tip:** If you need live OpenAI/Gemini powered responses, you can configure your API key anytime in the **⚙️ Settings** modal in the top right corner!"""

    if "report" in msg or "document" in msg or "submit" in msg:
        return """### 📄 Task Report & Document Submission Guide

To create a high-quality submission for your intern review:
1. **Title & Executive Summary**: State your task objective clearly.
2. **Methodology / Implementation**:
   - Technologies used (Python, Flask, SQLite, etc.)
   - Architecture / workflow steps
3. **Results & Code Screenshots**: Include evidence of working features.
4. **Challenges & Solutions**: What difficulties did you solve?
5. **Next Steps**: What improvements are planned?

You can upload your file as `.pdf`, `.docx`, `.txt`, or `.md` in your personal task link."""

    if "hello" in msg or "hi" in msg or "vanakkam" in msg or "hey" in msg:
        return """👋 **Vanakkam & Hello!** I am your **AI Intern Task Assistant & Mentor**.

Here is what I can do for you:
1. 📋 **Track Tasks:** Ask me *"Show all interns"*, *"What tasks are pending?"*, or *"Status of Kavan"*.
2. 🎓 **Task Guidance:** Ask questions about your requirements, document format, or review deadlines.
3. 💻 **Coding & Debugging:** Ask for Python, Flask, or database coding help.
4. 🎙️ **Voice Interaction:** Click the microphone icon to speak directly to me!

What would you like to explore today?"""

    return f"""### 🤖 AI Mentor Response

You asked: *"{user_message}"*

As your AI Intern Mentor, here are key recommendations:
- **Clarify Requirements:** Break down complex tasks into smaller daily milestones.
- **Maintain Documentation:** Keep your code commented and prepare clear progress reports.
- **Regular Check-ins:** Be ready for your review meetings by testing your work beforehand.

> ℹ️ **Notice:** Live OpenAI generation is available once an API key is provided. Click the **⚙️ Settings** icon in the header to enter an API key for live GPT-4o completions!"""

CHATBOT_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Intern Task Assistant & Chatbot</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-primary: #0a0f1d;
      --bg-surface: #111827;
      --bg-card: #1f293d;
      --bg-card-hover: #26334d;
      --text-main: #f3f4f6;
      --text-muted: #94a3b8;
      --accent: #6366f1;
      --accent-hover: #4f46e5;
      --accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #d946ef 100%);
      --cyan-gradient: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
      --border-color: rgba(255, 255, 255, 0.08);
      --border-focus: rgba(99, 102, 241, 0.5);
      --user-bubble: #1e3a8a;
      --bot-bubble: #172033;
      --shadow-glow: 0 0 30px rgba(99, 102, 241, 0.15);
    }

    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, sans-serif;
      background: var(--bg-primary);
      color: var(--text-main);
      height: 100vh;
      display: flex;
      overflow: hidden;
    }

    /* Layout */
    .app-container {
      display: flex;
      width: 100vw;
      height: 100vh;
      background: radial-gradient(circle at 10% 20%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
                  radial-gradient(circle at 90% 80%, rgba(217, 70, 239, 0.06) 0%, transparent 40%);
    }

    /* Sidebar */
    .sidebar {
      width: 300px;
      background: rgba(17, 24, 39, 0.85);
      backdrop-filter: blur(16px);
      border-right: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      padding: 20px 16px;
      transition: all 0.3s ease;
      z-index: 10;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
      padding: 0 8px;
    }

    .brand-icon {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: var(--accent-gradient);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 20px;
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3);
    }

    .brand-title {
      font-size: 17px;
      font-weight: 700;
      letter-spacing: -0.3px;
      background: linear-gradient(to right, #fff, #cbd5e1);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .brand-badge {
      font-size: 10px;
      padding: 2px 6px;
      border-radius: 4px;
      background: rgba(99, 102, 241, 0.2);
      color: #a5b4fc;
      margin-left: auto;
    }

    .new-chat-btn {
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 10px;
      width: 100%;
      padding: 12px 16px;
      background: var(--accent-gradient);
      color: white;
      border: none;
      border-radius: 10px;
      font-size: 14px;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s ease;
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.25);
    }
    .new-chat-btn:hover {
      transform: translateY(-1px);
      box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4);
    }

    .sidebar-section-title {
      font-size: 11px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.8px;
      color: var(--text-muted);
      margin: 20px 8px 10px;
    }

    .prompt-chip {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border-color);
      color: #cbd5e1;
      padding: 10px 12px;
      border-radius: 8px;
      margin-bottom: 8px;
      font-size: 13px;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 8px;
      transition: all 0.2s;
    }
    .prompt-chip:hover {
      background: rgba(99, 102, 241, 0.15);
      border-color: rgba(99, 102, 241, 0.4);
      color: #fff;
      transform: translateX(3px);
    }

    .sidebar-footer {
      margin-top: auto;
      padding-top: 16px;
      border-top: 1px solid var(--border-color);
      display: flex;
      flex-direction: column;
      gap: 8px;
    }

    .link-btn {
      color: #94a3b8;
      text-decoration: none;
      font-size: 13px;
      display: flex;
      align-items: center;
      gap: 8px;
      padding: 8px;
      border-radius: 6px;
      transition: all 0.2s;
    }
    .link-btn:hover {
      background: rgba(255, 255, 255, 0.05);
      color: #fff;
    }

    /* Main Chat Area */
    .chat-main {
      flex: 1;
      display: flex;
      flex-direction: column;
      height: 100vh;
      position: relative;
    }

    /* Header */
    .chat-header {
      height: 68px;
      border-bottom: 1px solid var(--border-color);
      background: rgba(17, 24, 39, 0.7);
      backdrop-filter: blur(12px);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
    }

    .header-left {
      display: flex;
      align-items: center;
      gap: 12px;
    }

    .status-indicator {
      display: flex;
      align-items: center;
      gap: 8px;
      font-size: 13px;
      color: #94a3b8;
    }

    .status-dot {
      width: 8px;
      height: 8px;
      background: #10b981;
      border-radius: 50%;
      box-shadow: 0 0 8px #10b981;
    }

    .header-actions {
      display: flex;
      align-items: center;
      gap: 10px;
    }

    .icon-btn {
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: #cbd5e1;
      width: 36px;
      height: 36px;
      border-radius: 8px;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s;
    }
    .icon-btn:hover {
      background: rgba(99, 102, 241, 0.2);
      border-color: var(--accent);
      color: #fff;
    }

    /* Messages container */
    .messages-container {
      flex: 1;
      overflow-y: auto;
      padding: 24px;
      display: flex;
      flex-direction: column;
      gap: 20px;
      scroll-behavior: smooth;
    }

    .welcome-card {
      max-width: 680px;
      margin: 40px auto 20px;
      text-align: center;
      padding: 36px;
      background: rgba(31, 41, 61, 0.4);
      border: 1px solid var(--border-color);
      border-radius: 20px;
      backdrop-filter: blur(8px);
      box-shadow: var(--shadow-glow);
    }

    .welcome-avatar {
      width: 64px;
      height: 64px;
      margin: 0 auto 16px;
      border-radius: 18px;
      background: var(--accent-gradient);
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 32px;
    }

    .welcome-card h2 {
      font-size: 24px;
      font-weight: 700;
      margin-bottom: 8px;
    }

    .welcome-card p {
      color: var(--text-muted);
      font-size: 14px;
      line-height: 1.6;
      margin-bottom: 24px;
    }

    .quick-grid {
      display: grid;
      grid-template-columns: repeat(2, 1fr);
      gap: 12px;
      text-align: left;
    }

    .quick-card {
      background: rgba(255, 255, 255, 0.03);
      border: 1px solid var(--border-color);
      padding: 14px;
      border-radius: 12px;
      cursor: pointer;
      transition: all 0.2s;
    }
    .quick-card:hover {
      background: rgba(99, 102, 241, 0.15);
      border-color: rgba(99, 102, 241, 0.4);
      transform: translateY(-2px);
    }
    .quick-card strong {
      display: block;
      font-size: 13px;
      margin-bottom: 4px;
      color: #fff;
    }
    .quick-card span {
      font-size: 12px;
      color: var(--text-muted);
    }

    /* Message bubbles */
    .message-row {
      display: flex;
      gap: 14px;
      max-width: 850px;
      width: 100%;
      margin: 0 auto;
      animation: fadeIn 0.3s ease;
    }

    .message-row.user {
      flex-direction: row-reverse;
    }

    .avatar {
      width: 38px;
      height: 38px;
      border-radius: 10px;
      display: flex;
      align-items: center;
      justify-content: center;
      font-size: 18px;
      flex-shrink: 0;
    }

    .avatar.bot {
      background: var(--accent-gradient);
      box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
    }

    .avatar.user {
      background: var(--cyan-gradient);
      box-shadow: 0 4px 12px rgba(6, 182, 212, 0.3);
    }

    .bubble-wrap {
      max-width: 80%;
      display: flex;
      flex-direction: column;
    }

    .bubble {
      padding: 14px 18px;
      border-radius: 16px;
      font-size: 14.5px;
      line-height: 1.6;
      word-wrap: break-word;
    }

    .message-row.bot .bubble {
      background: var(--bot-bubble);
      border: 1px solid var(--border-color);
      border-top-left-radius: 4px;
      color: #e2e8f0;
    }

    .message-row.user .bubble {
      background: var(--user-bubble);
      color: #fff;
      border-top-right-radius: 4px;
    }

    .bubble-actions {
      display: flex;
      align-items: center;
      gap: 8px;
      margin-top: 6px;
      font-size: 11px;
      color: var(--text-muted);
    }

    .action-icon {
      background: transparent;
      border: none;
      color: #94a3b8;
      cursor: pointer;
      display: flex;
      align-items: center;
      gap: 4px;
      font-size: 12px;
      padding: 2px 6px;
      border-radius: 4px;
      transition: all 0.2s;
    }
    .action-icon:hover {
      background: rgba(255, 255, 255, 0.1);
      color: #fff;
    }

    /* Markdown inside messages */
    .bubble h1, .bubble h2, .bubble h3 { margin: 12px 0 6px; color: #fff; font-size: 16px; }
    .bubble ul, .bubble ol { margin: 8px 0 8px 20px; }
    .bubble li { margin-bottom: 4px; }
    .bubble p { margin-bottom: 8px; }
    .bubble p:last-child { margin-bottom: 0; }
    .bubble code {
      font-family: 'JetBrains Mono', monospace;
      background: rgba(0, 0, 0, 0.3);
      padding: 2px 6px;
      border-radius: 4px;
      font-size: 13px;
      color: #38bdf8;
    }
    .bubble pre {
      background: #090d16;
      border: 1px solid rgba(255, 255, 255, 0.1);
      border-radius: 8px;
      padding: 12px;
      overflow-x: auto;
      margin: 10px 0;
      position: relative;
    }
    .bubble pre code {
      background: transparent;
      padding: 0;
      color: #a5f3fc;
      font-size: 13px;
    }
    .bubble table {
      width: 100%;
      border-collapse: collapse;
      margin: 10px 0;
      font-size: 13px;
    }
    .bubble th, .bubble td {
      border: 1px solid rgba(255, 255, 255, 0.12);
      padding: 8px 10px;
      text-align: left;
    }
    .bubble th {
      background: rgba(255, 255, 255, 0.05);
      color: #f1f5f9;
    }

    /* Typing indicator */
    .typing-indicator {
      display: flex;
      align-items: center;
      gap: 5px;
      padding: 8px 12px;
    }
    .typing-dot {
      width: 7px;
      height: 7px;
      background: #818cf8;
      border-radius: 50%;
      animation: bounce 1.4s infinite ease-in-out both;
    }
    .typing-dot:nth-child(1) { animation-delay: -0.32s; }
    .typing-dot:nth-child(2) { animation-delay: -0.16s; }

    @keyframes bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
    @keyframes fadeIn {
      from { opacity: 0; transform: translateY(8px); }
      to { opacity: 1; transform: translateY(0); }
    }

    /* Input Box Area */
    .input-wrapper {
      padding: 16px 24px 24px;
      background: rgba(17, 24, 39, 0.85);
      border-top: 1px solid var(--border-color);
      backdrop-filter: blur(12px);
    }

    .input-bar {
      max-width: 850px;
      margin: 0 auto;
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      border-radius: 16px;
      padding: 8px 12px;
      display: flex;
      align-items: center;
      gap: 10px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.25);
      transition: all 0.2s ease;
    }

    .input-bar:focus-within {
      border-color: var(--accent);
      box-shadow: 0 0 20px rgba(99, 102, 241, 0.25);
    }

    .chat-textarea {
      flex: 1;
      background: transparent;
      border: none;
      outline: none;
      color: #fff;
      font-family: inherit;
      font-size: 14.5px;
      resize: none;
      max-height: 120px;
      min-height: 24px;
      line-height: 1.5;
    }
    .chat-textarea::placeholder {
      color: #64748b;
    }

    .send-btn {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: var(--accent-gradient);
      border: none;
      color: #fff;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s;
      flex-shrink: 0;
    }
    .send-btn:hover {
      transform: scale(1.05);
      box-shadow: 0 4px 15px rgba(99, 102, 241, 0.4);
    }
    .send-btn:disabled {
      opacity: 0.5;
      cursor: not-allowed;
      transform: none;
    }

    .mic-btn {
      width: 40px;
      height: 40px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.05);
      border: 1px solid var(--border-color);
      color: #cbd5e1;
      display: flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      transition: all 0.2s;
      flex-shrink: 0;
    }
    .mic-btn.listening {
      background: #ef4444;
      color: white;
      animation: pulse 1.5s infinite;
    }
    @keyframes pulse {
      0% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0.7); }
      70% { box-shadow: 0 0 0 10px rgba(239, 68, 68, 0); }
      100% { box-shadow: 0 0 0 0 rgba(239, 68, 68, 0); }
    }

    .input-hint {
      max-width: 850px;
      margin: 8px auto 0;
      font-size: 12px;
      color: #64748b;
      display: flex;
      justify-content: space-between;
    }

    /* Modal */
    .modal {
      position: fixed;
      top: 0; left: 0; width: 100%; height: 100%;
      background: rgba(0, 0, 0, 0.7);
      backdrop-filter: blur(8px);
      display: none;
      align-items: center;
      justify-content: center;
      z-index: 100;
    }
    .modal-content {
      background: var(--bg-surface);
      border: 1px solid var(--border-color);
      width: 90%;
      max-width: 480px;
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 20px 40px rgba(0,0,0,0.5);
    }
    .modal-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 18px;
    }
    .modal-header h3 { font-size: 18px; }
    .close-btn { background: none; border: none; color: #94a3b8; font-size: 20px; cursor: pointer; }
    .form-group { margin-bottom: 16px; }
    .form-group label { display: block; font-size: 13px; color: #cbd5e1; margin-bottom: 6px; font-weight: 500; }
    .form-group input, .form-group select {
      width: 100%;
      background: rgba(255, 255, 255, 0.04);
      border: 1px solid var(--border-color);
      padding: 10px 14px;
      border-radius: 8px;
      color: #fff;
      font-size: 14px;
    }
    .save-modal-btn {
      width: 100%;
      padding: 12px;
      border-radius: 8px;
      background: var(--accent-gradient);
      color: white;
      border: none;
      font-weight: 600;
      cursor: pointer;
    }

    @media (max-width: 768px) {
      .sidebar { display: none; }
      .quick-grid { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
  <div class="app-container">
    <!-- Sidebar -->
    <aside class="sidebar">
      <div class="brand">
        <div class="brand-icon">🤖</div>
        <div>
          <div class="brand-title">Task AI Chatbot</div>
          <div style="font-size: 11px; color: #94a3b8">Intern Assistant & Mentor</div>
        </div>
        <span class="brand-badge">PRO</span>
      </div>

      <button class="new-chat-btn" onclick="startNewChat()">
        <span>+</span> New Conversation
      </button>

      <div class="sidebar-section-title">Quick Actions</div>
      <div class="prompt-chip" onclick="sendQuickPrompt('List all registered interns and their tasks')">
        <span>📊</span> List All Interns & Tasks
      </div>
      <div class="prompt-chip" onclick="sendQuickPrompt('What tasks are currently pending or in progress?')">
        <span>⏳</span> Show Pending Tasks
      </div>
      <div class="prompt-chip" onclick="sendQuickPrompt('How can I write an effective project report?')">
        <span>📝</span> Project Report Guide
      </div>
      <div class="prompt-chip" onclick="sendQuickPrompt('Write a Python script to check task deadlines')">
        <span>🐍</span> Python Task Helper
      </div>
      <div class="prompt-chip" onclick="sendQuickPrompt('Give me tips for my task review meeting')">
        <span>🎯</span> Review Meeting Tips
      </div>

      <div class="sidebar-footer">
        <a href="http://127.0.0.1:5000/dashboard" target="_blank" class="link-btn">
          <span>📋</span> Open Admin Dashboard
        </a>
        <a href="javascript:void(0)" onclick="openSettings()" class="link-btn">
          <span>⚙️</span> AI & API Settings
        </a>
      </div>
    </aside>

    <!-- Main Chat -->
    <main class="chat-main">
      <header class="chat-header">
        <div class="header-left">
          <div class="status-indicator">
            <span class="status-dot"></span>
            <span id="modelStatus">AI Mentor Ready ({{ model_name }})</span>
          </div>
        </div>
        <div class="header-actions">
          <button class="icon-btn" title="Text-to-speech audio toggle" id="ttsToggle" onclick="toggleAudioSpeech()">
            <span id="audioIcon">🔊</span>
          </button>
          <button class="icon-btn" title="Export Chat" onclick="exportChat()">
            📥
          </button>
          <button class="icon-btn" title="Settings" onclick="openSettings()">
            ⚙️
          </button>
        </div>
      </header>

      <!-- Message History -->
      <div class="messages-container" id="messagesContainer">
        <div class="welcome-card" id="welcomeCard">
          <div class="welcome-avatar">🎓</div>
          <h2>Hello, Welcome to Intern Task AI!</h2>
          <p>I am your smart assistant designed to help interns and administrators manage tasks, write reports, debug code, and check real-time project progress.</p>
          
          <div class="quick-grid">
            <div class="quick-card" onclick="sendQuickPrompt('Show summary of all intern tasks')">
              <strong>📊 Intern Database Summary</strong>
              <span>Check registered interns, pending tasks & deadlines</span>
            </div>
            <div class="quick-card" onclick="sendQuickPrompt('How do I submit my document for review?')">
              <strong>📑 Submission Guidance</strong>
              <span>Accepted file formats and review checklist</span>
            </div>
            <div class="quick-card" onclick="sendQuickPrompt('Write Python code to connect to SQLite database')">
              <strong>💻 Python & Code Assistant</strong>
              <span>Get code snippets, explanations and debugging tips</span>
            </div>
            <div class="quick-card" onclick="sendQuickPrompt('Help me prepare for my mentor review meeting')">
              <strong>🎙️ Review Preparation</strong>
              <span>Common questions, presentation advice and feedback</span>
            </div>
          </div>
        </div>
      </div>

      <!-- Input Section -->
      <div class="input-wrapper">
        <div class="input-bar">
          <button class="mic-btn" id="micBtn" onclick="toggleSpeechRecognition()" title="Voice input (Speech to Text)">
            🎤
          </button>
          <textarea 
            id="userInput" 
            class="chat-textarea" 
            placeholder="Ask about tasks, Python code, requirements or say 'Show interns'..." 
            rows="1"
            onkeydown="handleKeyDown(event)"
            oninput="autoResize(this)"
          ></textarea>
          <button class="send-btn" id="sendBtn" onclick="sendMessage()" title="Send Message">
            ➔
          </button>
        </div>
        <div class="input-hint">
          <span>Press <strong>Enter</strong> to send, <strong>Shift + Enter</strong> for new line</span>
          <span id="speechStatus">Microphone ready</span>
        </div>
      </div>
    </main>
  </div>

  <!-- Settings Modal -->
  <div class="modal" id="settingsModal">
    <div class="modal-content">
      <div class="modal-header">
        <h3>⚙️ Chatbot Settings</h3>
        <button class="close-btn" onclick="closeSettings()">&times;</button>
      </div>
      <div class="form-group">
        <label>OpenAI-Compatible API Key</label>
        <input type="password" id="cfgApiKey" placeholder="sk-..." value="{{ api_key }}">
        <small style="color:#94a3b8;font-size:11px;display:block;margin-top:4px">
          Supports OpenAI, Groq, OpenRouter, or DeepSeek API key.
        </small>
      </div>
      <div class="form-group">
        <label>API Base URL</label>
        <input type="text" id="cfgBaseUrl" value="{{ base_url }}">
      </div>
      <div class="form-group">
        <label>Model Name</label>
        <input type="text" id="cfgModel" value="{{ model_name }}">
      </div>
      <button class="save-modal-btn" onclick="saveSettings()">Save & Update Settings</button>
    </div>
  </div>

  <script>
    let chatHistory = [];
    let audioSpeechEnabled = true;
    let isListening = false;
    let recognition = null;

    function autoResize(el) {
      el.style.height = 'auto';
      el.style.height = Math.min(el.scrollHeight, 120) + 'px';
    }

    function handleKeyDown(e) {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
      }
    }

    function sendQuickPrompt(text) {
      document.getElementById('userInput').value = text;
      sendMessage();
    }

    function startNewChat() {
      chatHistory = [];
      const container = document.getElementById('messagesContainer');
      container.innerHTML = `
        <div class="welcome-card" id="welcomeCard">
          <div class="welcome-avatar">🎓</div>
          <h2>New Conversation Started</h2>
          <p>Ask anything about intern tasks, coding in Python/Flask, or report submissions.</p>
        </div>
      `;
    }

    function toggleAudioSpeech() {
      audioSpeechEnabled = !audioSpeechEnabled;
      document.getElementById('audioIcon').textContent = audioSpeechEnabled ? '🔊' : '🔇';
      document.getElementById('ttsToggle').title = audioSpeechEnabled ? 'Voice output enabled' : 'Voice output muted';
    }

    function speakText(text) {
      if (!audioSpeechEnabled || !('speechSynthesis' in window)) return;
      window.speechSynthesis.cancel();
      // Remove markdown chars
      const clean = text.replace(/[*#`_\[\]]/g, '');
      const utter = new SpeechSynthesisUtterance(clean.substring(0, 300));
      utter.rate = 1.0;
      window.speechSynthesis.speak(utter);
    }

    function toggleSpeechRecognition() {
      const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
      if (!SR) {
        alert('Speech recognition is not supported in this browser. Please use Chrome or Edge.');
        return;
      }

      if (isListening) {
        if (recognition) recognition.stop();
        return;
      }

      recognition = new SR();
      recognition.lang = 'en-US';
      recognition.interimResults = false;

      recognition.onstart = () => {
        isListening = true;
        document.getElementById('micBtn').classList.add('listening');
        document.getElementById('speechStatus').textContent = 'Listening... Speak now';
      };

      recognition.onresult = (e) => {
        const transcript = e.results[0][0].transcript;
        document.getElementById('userInput').value = transcript;
        document.getElementById('speechStatus').textContent = 'Heard: ' + transcript;
        sendMessage();
      };

      recognition.onerror = (e) => {
        document.getElementById('speechStatus').textContent = 'Speech error: ' + e.error;
      };

      recognition.onend = () => {
        isListening = false;
        document.getElementById('micBtn').classList.remove('listening');
        document.getElementById('speechStatus').textContent = 'Microphone ready';
      };

      recognition.start();
    }

    // Markdown Parser
    function parseMarkdown(text) {
      if (!text) return '';
      let html = text
        .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
        // Code blocks with syntax copy button
        .replace(/```([a-z]*)\n([\s\S]*?)```/g, (match, lang, code) => {
          return `<pre><div style="display:flex;justify-content:space-between;color:#94a3b8;font-size:11px;margin-bottom:6px"><span>${lang || 'code'}</span><button class="action-icon" onclick="copySnippet(this)">Copy</button></div><code>${code.trim()}</code></pre>`;
        })
        // Inline code
        .replace(/`([^`]+)`/g, '<code>$1</code>')
        // Headers
        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
        // Bold & Italic
        .replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>')
        .replace(/\*([^*]+)\*/g, '<em>$1</em>')
        // Blockquotes
        .replace(/^\> (.*$)/gim, '<blockquote style="border-left:3px solid #6366f1;padding-left:10px;color:#cbd5e1;margin:8px 0">$1</blockquote>')
        // Lists
        .replace(/^\- (.*$)/gim, '<li>$1</li>')
        // Tables
        .replace(/\|(.+)\|/g, (match) => {
          const cells = match.split('|').filter(c => c.trim().length > 0);
          if (cells.every(c => c.trim().match(/^:?-+:?$/))) return '';
          return '<tr>' + cells.map(c => `<td>${c.trim()}</td>`).join('') + '</tr>';
        });

      // Wrap list items
      html = html.replace(/(<li>.*<\/li>)/gms, '<ul>$1</ul>');
      // Wrap table rows
      html = html.replace(/(<tr>.*<\/tr>)/gms, '<table>$1</table>');
      // Paragraphs
      html = html.replace(/\n\n/g, '<br><br>');
      return html;
    }

    function copySnippet(btn) {
      const code = btn.parentElement.nextElementSibling.textContent;
      navigator.clipboard.writeText(code);
      btn.textContent = 'Copied!';
      setTimeout(() => btn.textContent = 'Copy', 2000);
    }

    function appendMessage(role, text) {
      const container = document.getElementById('messagesContainer');
      const welcome = document.getElementById('welcomeCard');
      if (welcome) welcome.style.display = 'none';

      const row = document.createElement('div');
      row.className = `message-row ${role}`;

      const avatar = document.createElement('div');
      avatar.className = `avatar ${role}`;
      avatar.textContent = role === 'user' ? '👤' : '🤖';

      const wrap = document.createElement('div');
      wrap.className = 'bubble-wrap';

      const bubble = document.createElement('div');
      bubble.className = 'bubble';
      bubble.innerHTML = role === 'user' ? text.replace(/</g, "&lt;") : parseMarkdown(text);

      wrap.appendChild(bubble);

      if (role === 'bot') {
        const actions = document.createElement('div');
        actions.className = 'bubble-actions';
        actions.innerHTML = `
          <button class="action-icon" onclick="speakText(this.closest('.bubble-wrap').querySelector('.bubble').innerText)">🔊 Read</button>
          <button class="action-icon" onclick="navigator.clipboard.writeText(this.closest('.bubble-wrap').querySelector('.bubble').innerText)">📋 Copy</button>
        `;
        wrap.appendChild(actions);
      }

      row.appendChild(avatar);
      row.appendChild(wrap);
      container.appendChild(row);
      container.scrollTop = container.scrollHeight;
    }

    function showTypingIndicator() {
      const container = document.getElementById('messagesContainer');
      const row = document.createElement('div');
      row.id = 'typingRow';
      row.className = 'message-row bot';
      row.innerHTML = `
        <div class="avatar bot">🤖</div>
        <div class="bubble-wrap">
          <div class="bubble">
            <div class="typing-indicator">
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
              <div class="typing-dot"></div>
            </div>
          </div>
        </div>
      `;
      container.appendChild(row);
      container.scrollTop = container.scrollHeight;
    }

    function removeTypingIndicator() {
      const ind = document.getElementById('typingRow');
      if (ind) ind.remove();
    }

    async function sendMessage() {
      const input = document.getElementById('userInput');
      const text = input.value.trim();
      if (!text) return;

      appendMessage('user', text);
      input.value = '';
      input.style.height = 'auto';

      chatHistory.push({ role: 'user', content: text });
      showTypingIndicator();

      try {
        const res = await fetch('/api/chat', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ message: text, history: chatHistory })
        });
        const data = await res.json();
        removeTypingIndicator();

        if (data.reply) {
          appendMessage('bot', data.reply);
          chatHistory.push({ role: 'assistant', content: data.reply });
          speakText(data.reply);
        } else {
          appendMessage('bot', '⚠️ Error: ' + (data.error || 'Unable to get response'));
        }
      } catch (err) {
        removeTypingIndicator();
        appendMessage('bot', '⚠️ Connection error: ' + err.message);
      }
    }

    function exportChat() {
      if (chatHistory.length === 0) {
        alert('No conversation to export yet.');
        return;
      }
      let content = "=== AI INTERN CHAT TRANSCRIPT ===\n";
      content += "Exported on: " + new Date().toLocaleString() + "\n\n";
      chatHistory.forEach(msg => {
        content += (msg.role === 'user' ? 'USER: ' : 'AI: ') + msg.content + "\n\n";
      });
      const blob = new Blob([content], { type: 'text/plain' });
      const a = document.createElement('a');
      a.href = URL.createObjectURL(blob);
      a.download = `intern_chat_${Date.now()}.txt`;
      a.click();
    }

    // Settings Modal
    function openSettings() {
      document.getElementById('settingsModal').style.display = 'flex';
    }
    function closeSettings() {
      document.getElementById('settingsModal').style.display = 'none';
    }
    async function saveSettings() {
      const apiKey = document.getElementById('cfgApiKey').value.trim();
      const baseUrl = document.getElementById('cfgBaseUrl').value.trim();
      const model = document.getElementById('cfgModel').value.trim();

      const res = await fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ api_key: apiKey, base_url: baseUrl, model: model })
      });
      const data = await res.json();
      if (data.ok) {
        document.getElementById('modelStatus').textContent = `AI Mentor Ready (${model})`;
        closeSettings();
        alert('Settings saved successfully!');
      }
    }
  </script>
</body>
</html>
"""

@app.route("/")
def index():
    return render_template_string(
        CHATBOT_HTML,
        api_key=AI_API_KEY,
        base_url=AI_BASE_URL,
        model_name=AI_MODEL
    )

@app.route("/api/chat", methods=["POST"])
def chat_endpoint():
    data = request.json or {}
    user_msg = data.get("message", "").strip()
    history = data.get("history", [])

    if not user_msg:
        return jsonify({"error": "Empty message"}), 400

    # 1. First check if message is a database / task query
    db_insights = query_db_insights(user_msg)
    if db_insights:
        return jsonify({"reply": db_insights})

    # 2. If API Key is present, try OpenAI-compatible endpoint
    if AI_API_KEY:
        try:
            # Build context from database if available
            db_context = ""
            conn = get_db()
            if conn:
                try:
                    interns = conn.execute("SELECT id, name, task_title, status FROM interns LIMIT 15").fetchall()
                    if interns:
                        intern_summary = ", ".join([f"{r['name']} ({r['task_title']} - {r['status']})" for r in interns])
                        db_context = f"\nCurrent Active Interns Context: {intern_summary}"
                except Exception:
                    pass
                finally:
                    conn.close()

            system_prompt = (
                "You are an empathetic, highly knowledgeable AI Intern Mentor and Task Assistant. "
                "You help interns understand their task assignments, write professional reports, "
                "debug code (Python, Flask, SQLite, Frontend), and prepare for mentor reviews. "
                "Keep answers practical, structured with bullet points or code blocks where appropriate."
                + db_context
            )

            messages = [{"role": "system", "content": system_prompt}]
            # Include recent chat history
            for h in history[-8:]:
                if h.get("role") in ("user", "assistant"):
                    messages.append({"role": h["role"], "content": h["content"]})

            if not any(m["role"] == "user" and m["content"] == user_msg for m in messages[-2:]):
                messages.append({"role": "user", "content": user_msg})

            resp = requests.post(
                AI_BASE_URL.rstrip("/") + "/chat/completions",
                headers={
                    "Authorization": f"Bearer {AI_API_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": AI_MODEL,
                    "temperature": 0.5,
                    "messages": messages
                },
                timeout=45
            )
            resp.raise_for_status()
            reply = resp.json()["choices"][0]["message"]["content"].strip()
            return jsonify({"reply": reply})
        except Exception as e:
            # If external AI fails or times out, gracefully use smart fallback
            fallback = generate_smart_fallback(user_msg, history)
            return jsonify({"reply": fallback})

    # 3. If no API key configured, use built-in smart assistant
    reply = generate_smart_fallback(user_msg, history)
    return jsonify({"reply": reply})

@app.route("/api/settings", methods=["POST"])
def update_settings():
    global AI_API_KEY, AI_BASE_URL, AI_MODEL
    data = request.json or {}
    AI_API_KEY = data.get("api_key", AI_API_KEY).strip()
    AI_BASE_URL = data.get("base_url", AI_BASE_URL).strip()
    AI_MODEL = data.get("model", AI_MODEL).strip()
    return jsonify({"ok": True})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"\n" + "="*60)
    print(f"🚀 AI Intern Chatbot Web App is running!")
    print(f"👉 Open in browser: http://127.0.0.1:{port}")
    print(f"👉 Direct access: http://localhost:{port}")
    print("="*60 + "\n")
    app.run(host="0.0.0.0", port=port, debug=False)
