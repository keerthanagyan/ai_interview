import os, json, re
import difflib, random
from collections import defaultdict
from pathlib import Path
from typing import Dict, List
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
import difflib
from collections import defaultdict
from openai import OpenAI
import openai
import requests
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)
openai.api_key = OPENAI_API_KEY
if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY not set in .env")

PORT           = int(os.getenv("PORT", "8002"))
REALTIME_MODEL = os.getenv("REALTIME_MODEL", "gpt-4o-realtime-preview")
VOICE          = os.getenv("VOICE", "alloy")        # stable male voice
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "gpt-4o-mini")

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

DATA_DIR = Path("data")

# One base key per topic; we'll load <key>.course.json and <key>.quiz.json
TOPIC_MAP = {
    "Product Designer": "product_designer",
    "PCB Designer": "pcb",
    "Firmware / Software Developer (Embedded)": "firmware_developer",
    "Integration Engineer": "integration_engineer",
    "Domain Expert & V&V Engineer": "domain_expert_vnv",
    "Mechanical Designer": "mechanical_designer",
    "Procurement Specialist": "procurement_specialist",
}


# -------- helpers --------


DATA_DIR = Path("data")
def generate_expected_answer(question: str, topic: str) -> str:
    prompt = f"""
You are an expert interviewer for '{topic}'.
Provide the ideal expected answer for the interview question:

Question: "{question}"

Rules:
- 3 to 5 sentences
- Clear, technical, correct
- Do NOT repeat the question
- Do NOT say “expected answer” or “ideal answer”
- English only
"""

    try:
        resp = client.chat.completions.create(
            model=ANALYSIS_MODEL,
            messages=[
                {"role": "system", "content": "You are an expert technical interviewer."},
                {"role": "user", "content": prompt}
            ]
        )
        return resp.choices[0].message.content.strip()

    except Exception as e:
        print("EXPECTED ANSWER ERROR:", e)
        return "—"


def load_bundle(topic: str) -> dict:
    """Load two JSONs for a topic: <key>.course.json and <key>.quiz.json"""
    key = TOPIC_MAP.get(topic)
    if not key:
        return {"course": {}, "quiz": {}}

    def _read(p: Path):
        if p.exists():
            with p.open("r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    return {
        "course": _read(DATA_DIR / f"{key}.course.json"),
        "quiz":   _read(DATA_DIR / f"{key}.quiz.json"),
    }

def _trim(s: str, lim: int = 220) -> str:
    s = (s or "").strip()
    return s if len(s) <= lim else s[:lim] + "…"

def compact_course_context(topic: str,
                           per_competency: int = 3,
                           max_quiz_sections: int = 8,
                           max_quiz_stems_per_section: int = 6) -> str:
    """
    Build a small grounding blob used to COMPOSE questions.
    - From course: competencies → (subskills + responsibilities + red_flags)
    - From quiz: section names + a few stems; NO verbatim reading allowed
    """
    bundle = load_bundle(topic)
    course = bundle["course"] or {}
    quiz   = bundle["quiz"] or {}

    comps = course.get("competencies") or []

    # Deterministic selection per session (so it’s random but stable for a run)
    rnd = random.Random(42)

    content_snippets = []
    for c in comps:
        subskills = (c.get("subskills") or [])
        resps     = (c.get("responsibilities") or [])
        redflags  = (c.get("red_flags") or [])
        chosen    = subskills if len(subskills) <= per_competency else rnd.sample(subskills, per_competency)
        content_snippets.append({
            "id":  c.get("id",""),
            "name": c.get("name",""),
            "subskills": chosen,
            "responsibilities": resps[:5],
            "red_flags": redflags[:4]
        })

    # Your quiz.json is a dict: { "Section name": [ "Question1", ... ] }
    # Convert to 'clues' only; interviewer will paraphrase, not read.
    quiz_clues = []
    if isinstance(quiz, dict):
        sections = list(quiz.items())
        rnd.shuffle(sections)
        for sec_name, qs in sections[:max_quiz_sections]:
            stems = list(qs)[:max_quiz_stems_per_section]
            quiz_clues.append({
                "section": sec_name,
                "stems": [_trim(s) for s in stems]
            })

    probes = course.get("probe_templates") or [
        {"id":"define","pattern":"Define {subskill} in this product context."},
        {"id":"why","pattern":"Why is {subskill} important for {competency}?"},
        {"id":"steps","pattern":"List key steps; be concise."},
        {"id":"checks","pattern":"What checks verify it was done correctly?"},
        {"id":"instrument","pattern":"Which instrument verifies it and what proves success?"}
    ]

    payload = {
        "topic": topic,
        "coverage": {
            "policy": "breadth_then_depth_without_repetition",
            "per_competency_questions": 2
        },
        "content_snippets": content_snippets,
        "quiz_clues": quiz_clues,
        "probe_templates": probes
    }
    return json.dumps(payload, separators=(",",":"))


def topic_instructions(topic: str, context_text: str) -> str:
    return f"""
You are a professional, Indian-English male technical interviewer for the role "{topic}". 
Your job is to conduct a structured, realistic, end-to-end interview based ONLY on the 
competencies and quiz clues provided in the Context JSON.

STRICT RULES
- Speak ONLY in English.
- NEVER switch topics. If the student asks for another topic, reply:
  "We'll continue with the selected topic {topic} as required."
- NEVER praise the student. Avoid words like: great, nice, excellent, wonderful, good job.
- NEVER give answers or hints.
- NEVER repeat your own question.
- NEVER repeat phrases or templates.

OPENING (MANDATORY)
Your first turn MUST say exactly:
"Hello. Let's start the interview on {topic}. Tell me about yourself and how it relates to {topic}."

INTERVIEW STYLE
- Be concise, professional, and neutral.
- 1 question per turn. No explanations.
- Wait for silence (server VAD) before asking the next question.
- Focus ONLY on the competencies, subskills, responsibilities, red flags, and quiz clues in the context.
- DO NOT directly quote or read any text from the context; paraphrase naturally.

QUESTION PROGRESSION (VERY IMPORTANT)
Phase 1 — Basic  
- First 2 questions should be introductory and simple.  
- They should explore basic understanding of the role.

Phase 2 — Intermediate  
- Next ~4 questions should explore practical subskills, reasoning, checks, constraints, block diagrams, instruments, etc.

Phase 3 — Advanced  
- Final questions should be deeper, scenario-based or problem-solving oriented.  
- Use the probe templates (steps, checks, constraints, instruments).

COVERAGE COMPLETENESS
- COVER ALL competencies from the context: approximately 2 questions per competency.
- COVER quiz clue sections where possible.
- DO NOT ask more than 1 question from the same idea unless the student’s previous answer was weak or incomplete.

TOPIC LOCK
- The interview MUST remain on the topic "{topic}".
- If student tries to switch, say:
  "We'll continue with the selected topic {topic}."

AFTER EVERY ANSWER
- Do NOT say “okay”, “good”, “great”, “understood” or similar.
- Transition neutrally: simply ask the next question.

CLOSING
After coverage is complete OR silence for 10 seconds:
- Give a short closing statement with:
  - 2 strengths (high-level only, no technical details)
  - 1 improvement area (general, no answer-leaking)
- Example style (do NOT copy exactly):
  "Thanks. Based on your responses, two strengths I observed are clarity and structured thinking. 
   One improvement area is explaining constraints more precisely."

OUTPUT MIRROR
For every spoken question, ALSO output the SAME text as textual output.

---- Context JSON (for composition only; NEVER read aloud) ----
{context_text}
""".strip()


def _norm(s: str) -> str:
    s = (s or "").lower()
    s = re.sub(r"[^a-z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def _tokset(s: str) -> set:
    return set(_norm(s).split())

def _similarity(a: str, b: str) -> float:
    """Blend Jaccard + fuzzy to match questions to references."""
    A, B = _tokset(a), _tokset(b)
    jacc = len(A & B) / max(1, len(A | B))
    fuzz = difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()
    return 0.6 * jacc + 0.4 * fuzz

def _keywords_from_text(s: str, limit: int = 15) -> list:
    """Cheap keyword extractor (content words, deduped)."""
    toks = [t for t in _norm(s).split() if len(t) >= 4]
    uniq = []
    seen = set()
    for t in toks:
        if t not in seen:
            seen.add(t); uniq.append(t)
        if len(uniq) >= limit:
            break
    return uniq


# -------- routes --------
@app.get("/")
async def index():
    return FileResponse("static/index.html")

@app.post("/session")
async def create_session(payload: dict):
    topic = payload.get("topic")
    if topic not in TOPIC_MAP:
        raise HTTPException(status_code=400, detail="Invalid topic")

    course_context = compact_course_context(topic)

    body = {
    "model": REALTIME_MODEL,
    "voice": VOICE,
    "modalities": ["audio", "text"],
    "turn_detection": {"type": "server_vad", "silence_duration_ms": 800},
    "instructions": (
        topic_instructions(topic, compact_course_context(topic))
    ),
    "input_audio_format": "pcm16",
    "input_audio_transcription": {
        "model": "whisper-1",
        "language": "en"
    }
}


    import requests
    url = "https://api.openai.com/v1/realtime/sessions"
    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        "Content-Type": "application/json",
        "OpenAI-Beta": "realtime=v1",
    }
    r = requests.post(url, headers=headers, json=body, timeout=20)
    if not r.ok:
        raise HTTPException(status_code=500, detail=f"OpenAI error {r.status_code}: {r.text}")
    data = r.json()
    token = (
        (data.get("client_secret") or {}).get("value")
        or data.get("client_secret")
        or data.get("value")
    )
    if not token:
        raise HTTPException(status_code=500, detail="Ephemeral token missing in REST response")
    return {"token": token}

@app.post("/analyze")
async def analyze(request: Dict):

    # request already IS the JSON dict
    data = request

    topic = (data.get("topic") or "").strip()
    Q = data.get("interviewerTurns") or []
    A = data.get("candidateTurns") or []

    bundle = load_bundle(topic)
    course = bundle.get("course") or {}
    quiz = bundle.get("quiz") or {}

    references = []

    # ---------- COURSE COMPETENCIES ----------
    for c in (course.get("competencies") or []):
        cid = c.get("id", "")
        cname = c.get("name", "")
        blob = "; ".join(
            (c.get("responsibilities") or []) +
            (c.get("subskills") or []) +
            (c.get("red_flags") or [])
        )
        references.append({
            "kind": "competency",
            "competency_id": cid,
            "name": cname,
            "text": blob,
            "keywords": _keywords_from_text(blob, 50),
            "stems": []
        })

    # ---------- QUIZ SECTIONS ----------
    if isinstance(quiz, dict):
        for sec_name, stems in quiz.items():
            if not isinstance(stems, list):
                continue

            clean_name = re.sub(
                r"\.xlsx?$", "",
                str(sec_name),
                flags=re.IGNORECASE
            ).strip()

            short_stems = [
                _trim(s, 220) for s in stems if isinstance(s, str)
            ][:24]

            joined = " ".join(short_stems[:12])

            references.append({
                "kind": "quiz",
                "competency_id": "",
                "name": clean_name,
                "text": joined,
                "keywords": _keywords_from_text(joined, 50),
                "stems": short_stems
            })

    if not references:
        return {
            "overall_score": 0.0,
            "items": [],
            "progress": [],
            "strengths": [],
            "improvements": [],
            "next_steps": [],
            "analysis": "No references found."
        }

    # ---------- PICK REFERENCE ----------
    def _pick_ref(question: str) -> dict:
        best = None
        best_score = -1
        for r in references:
            text_sim = _similarity(question, r["text"])
            stem_sim = 0
            for s in r["stems"][:6]:
                stem_sim = max(stem_sim, _similarity(question, s))
            score = max(text_sim, stem_sim)
            if score > best_score:
                best_score = score
                best = r
        return best

    # ---------- SCORE ----------
    def _score(answer: str, ref: dict):
        if not answer:
            return 0.0, [], [], None

        ans_norm = _norm(answer)
        tokens = _tokset(answer)
        ref_keys = ref.get("keywords", [])[:40]

        hits = [k for k in ref_keys if k in tokens]
        misses = [k for k in ref_keys if k not in tokens]

        text_fuzz = difflib.SequenceMatcher(
            None, ans_norm, _norm(ref["text"])
        ).ratio()

        stem_fuzz = 0
        best_stem = ""
        for s in ref["stems"][:6]:
            r = difflib.SequenceMatcher(None, ans_norm, _norm(s)).ratio()
            if r > stem_fuzz:
                stem_fuzz = r
                best_stem = s

        coverage = len(hits) / max(1, len(ref_keys))
        fuzz = max(text_fuzz, stem_fuzz)

        raw = 10 * (0.55 * coverage + 0.45 * fuzz)
        if hits and raw < 3:
            raw += 1.5

        score = round(min(10, raw), 1)
        

        return score, hits, misses, None

    # ---------- BUILD RESULT ----------
    items = []
    comp_map = defaultdict(lambda: {"sum": 0, "n": 0, "name": ""})

    for q, a in zip(Q, A):
        ref = _pick_ref(q)
        score, hits, misses,  _ignored = _score(a, ref)

        comp_key = ref["competency_id"] or f"quiz::{ref['name']}"
        comp_map[comp_key]["sum"] += score
        comp_map[comp_key]["n"] += 1
        comp_map[comp_key]["name"] = ref["name"]

        items.append({
            "question": q,
            "answer": a,
            "expected": generate_expected_answer(q, topic),
            "hits": hits,
            "misses": misses,
            "item_score": score,
            "matched_to": {"kind": ref["kind"], "name": ref["name"]},
        })

    progress = []
    all_scores = []
    for key, info in comp_map.items():
        if info["n"] > 0:
            avg = round(info["sum"] / info["n"], 1)
            progress.append({
                "name": info["name"],
                "score": avg,
                "questions": info["n"]
            })
            all_scores.append(avg)

    overall = round(sum(all_scores) / max(1, len(all_scores)), 1)

    strengths = [p["name"] for p in progress if p["score"] >= 7.5]
    improvements = [p["name"] for p in progress if p["score"] <= 4]
    next_steps = [p["name"] for p in progress if 4 < p["score"] < 7.5]

    return {
        "overall_score": overall,
        "items": items,
        "progress": progress,
        "strengths": strengths,
        "improvements": improvements,
        "next_steps": next_steps,
        "analysis": "Analysis completed."
    }


