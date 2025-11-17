AI Interview System – Realtime Mock Interview + Analysis

A fully interactive AI-powered Interview System built using:

FastAPI backend

OpenAI Realtime API (gpt-4o-realtime-preview)

WebRTC voice streaming

Whisper speech-to-text

Dynamic question generation using JSON-based course data

Automated scoring & expected answer generation

Beautiful 4-step interview pipeline UI

This project simulates a real interview for multiple job roles such as:

Product Designer

PCB Designer

Embedded Developer

Integration Engineer

Domain Expert (V&V)

Mechanical Designer

Procurement Specialist

The interviewer asks questions, listens to student answers, scores them, and produces a final analysis report with strengths, improvements, scores, and expected answers.

⭐ Features
🎤 Realtime AI Interview

Live AI interviewer using OpenAI Realtime

Server-VAD silence detection

Voice + text output

Difficulty progression (basic → intermediate → advanced)

Strict topic-lock (never switches topics)

🧠 Analysis Engine

Keyword scoring & similarity scoring

Automatic expected answer generation (GPT)

Per-competency scores

Overall score

Strengths, improvements, next steps

🎥 Topic Intro Videos

Non-skippable intro video before interview

Custom video per topic

🧩 Structured Pipeline UI

Step 1 — Select Topic
Step 2 — Watch Intro Video
Step 3 — AI Interview
Step 4 — Detailed Analysis

📁 Project Structure
project/
│
├── server.py                # FastAPI backend + analysis logic
├── requirements.txt         # Python dependencies
├── .env.example             # Environment template
├── data/                    # Course + quiz files per topic
│     └── product_designer.course.json
│     └── product_designer.quiz.json
│     ...
│
└── static/
      ├── index.html         # UI (pipeline)
      ├── app.js             # WebRTC logic + analysis UI
      ├── styles.css         # UI styling
      └── videos/            # Intro videos for each topic

⚙️ Installation
1️⃣ Clone the repository
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>

2️⃣ Create virtual environment
python3 -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Create .env file

Copy .env.example → .env

cp .env.example .env


Update with your real API key:

OPENAI_API_KEY=sk-xxxxxxxxxxxx
REALTIME_MODEL=gpt-4o-realtime-preview
ANALYSIS_MODEL=gpt-4o-mini
VOICE=alloy
PORT=8000

5️⃣ Run the server (local development)
uvicorn server:app --host 0.0.0.0 --port 8000 --reload


Open in browser:

http://localhost:8000

🧠 How the System Works
✔ Data Loading

Each topic has:

<topic>.course.json

<topic>.quiz.json

The interviewer uses these files to generate questions.

✔ Realtime Session

UI requests a session token → connects WebRTC → AI speaks → Whisper transcribes.

✔ Interview Flow

AI asks 1 question → waits for silence → next question.
Difficulty increases automatically.

✔ Analysis

For each Q/A pair:

Match to correct competency or quiz bucket

Score using fuzzy matching

Expected answer generated using GPT

Return final JSON to frontend

✔ UI Rendering

app.js renders:

Table of questions

Student answers

Expected answers

Score per question

Competency progress bars

Strengths / improvements

🚀 Deployment
Using Render.com

Push code to GitHub

Create new Web Service on Render

Choose your repo

Set:

Environment: Python
Build Command

pip install -r requirements.txt


Start Command

uvicorn server:app --host 0.0.0.0 --port $PORT


Add environment variables:

OPENAI_API_KEY=...
REALTIME_MODEL=gpt-4o-realtime-preview
ANALYSIS_MODEL=gpt-4o-mini
VOICE=alloy


Deploy

Render will give you a public URL.

🔐 Security Notes

NEVER push .env to GitHub

Keep API key secret

Always use SSL (Render provides automatically)

🤝 Contributing

Pull requests and improvements are welcome.

📄 License

This project can include MIT license or your company’s internal license.

❤️ Author

Built by Keerthana G
For AI-powered interview solutions.
