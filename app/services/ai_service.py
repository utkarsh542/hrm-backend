"""AI Service — Google Gemini powered HR intelligence (FREE tier).

Uses gemini-2.0-flash via the google-genai SDK.
Falls back to rule-based logic when no API key is set.
"""
import os
import json
import random
import hashlib
from app.utils.timezone import get_ist_date
from datetime import date
from typing import List, Dict, Optional
import urllib.request
import urllib.error
from app.logger import logger

from app.config import settings

# ── OpenRouter Free LLM setup ─────────────────────────────────────────
_AI_ENABLED = False
_OPENROUTER_KEY = settings.OPENROUTER_API_KEY or os.environ.get("OPENROUTER_API_KEY", "")
_MODEL = settings.OPENROUTER_MODEL or os.environ.get("OPENROUTER_MODEL", "meta-llama/llama-3-8b-instruct:free")

# Persistent Cache Configuration
_CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "ai_cache.json")

def _load_cache() -> dict:
    try:
        if os.path.exists(_CACHE_FILE):
            with open(_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception as e:
        logger.error(f"[AI] Error loading persistent cache: {e}")
    return {}

def _save_cache(cache: dict):
    try:
        with open(_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"[AI] Error saving persistent cache: {e}")

_AI_CACHE = _load_cache()

if _OPENROUTER_KEY:
    _AI_ENABLED = True
    logger.info(f"[AI] OpenRouter Free LLM enabled (model: {_MODEL})")
else:
    logger.warning("[AI] No OPENROUTER_API_KEY — running in rule-based fallback mode")


def _call_openrouter(prompt: str, system: str, max_tokens: int = 1024, json_mode: bool = False) -> str:
    """Send request to OpenRouter API."""
    if not _AI_ENABLED or not _OPENROUTER_KEY:
        logger.info("[AI] OpenRouter not enabled or key missing. Returning empty string.")
        return ""
    
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {_OPENROUTER_KEY}",
        "HTTP-Referer": "http://localhost:3000",
        "X-Title": "TechCorp HRMS",
        "Content-Type": "application/json"
    }
    
    data = {
        "model": _MODEL,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.3 if json_mode else 0.4,
        "max_tokens": max_tokens
    }
    
    logger.info(f"[AI] Requesting model: {_MODEL}")
    logger.info(f"[AI] System Prompt: {system[:200]}...")
    logger.info(f"[AI] User Prompt: {prompt[:300]}...")
    logger.info(f"[AI] Max Tokens: {max_tokens} | JSON Mode: {json_mode}")
        
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode("utf-8"),
        headers=headers,
        method="POST"
    )
    
    try:
        logger.info(f"[AI] Sending HTTP POST to OpenRouter: {url}")
        with urllib.request.urlopen(req, timeout=15) as response:
            res = json.loads(response.read().decode("utf-8"))
            logger.info(f"[AI] OpenRouter HTTP response received. Status: {response.status}")
            if "choices" in res and len(res["choices"]) > 0:
                msg = res["choices"][0].get("message", {})
                content_raw = msg.get("content")
                if content_raw is not None:
                    content = content_raw.strip()
                    logger.info(f"[AI] Completion output length: {len(content)} chars.")
                    logger.info(f"[AI] Completion content: {content[:200]}...")
                    return content
            
            logger.warning(f"[AI] OpenRouter API choices missing or empty. Response keys: {list(res.keys())}")
            if "error" in res:
                logger.error(f"[AI] OpenRouter error payload details: {res['error']}")
            else:
                logger.info(f"[AI] Full Response payload: {res}")
            return ""
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8") if e.fp else ""
        logger.error(f"[AI] OpenRouter HTTP Error {e.code}: {err_body}")
        if e.code == 429:
            raise Exception("429 RESOURCE_EXHAUSTED: OpenRouter rate limit exceeded.")
        raise Exception(f"OpenRouter HTTP {e.code}: {e.reason}")
    except Exception as e:
        logger.error(f"[AI] OpenRouter connection/processing error: {e}")
        raise e


def _chat(prompt: str, system: str = "You are an expert HR AI assistant. Always respond with valid JSON only. No markdown formatting, no code fences, just raw JSON.", max_tokens: int = 1024) -> dict:
    """Call OpenRouter and parse JSON response."""
    try:
        logger.info("[AI] Starting JSON Chat request.")
        text = _call_openrouter(prompt, system, max_tokens, json_mode=True)
        if not text:
            logger.info("[AI] Chat request returned empty string.")
            return {}
        # Clean markdown fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        parsed_json = json.loads(text)
        logger.info(f"[AI] JSON successfully parsed. Keys: {list(parsed_json.keys())}")
        return parsed_json
    except Exception as e:
        logger.error(f"[AI] _chat error parsing response: {e}")
        return {}


def _chat_text(prompt: str, system: str = "You are an intelligent HR assistant.", max_tokens: int = 512) -> str:
    """Call OpenRouter and return plain text response."""
    try:
        logger.info("[AI] Starting Plain Text Chat request.")
        return _call_openrouter(prompt, system, max_tokens, json_mode=False)
    except Exception as e:
        logger.error(f"[AI] _chat_text error: {e}")
        raise e


# ─────────────────────────────────────────────
# RESUME SCREENING
# ─────────────────────────────────────────────
def screen_resume(candidate_skills: str, job_requirements: str, experience_years: float) -> dict:
    logger.info(f"[AI] screen_resume called (experience: {experience_years} years)")
    candidate_skills = candidate_skills or ""
    job_requirements = job_requirements or ""

    if _AI_ENABLED:
        logger.info("[AI] screen_resume: calling OpenRouter LLM...")
        result = _chat(f"""Evaluate this job candidate objectively.

Candidate Skills: {candidate_skills}
Experience: {experience_years} years
Job Requirements: {job_requirements}

Return JSON with exactly these keys:
{{
  "score": <integer 0-100>,
  "skill_match": <integer 0-100>,
  "strengths": ["...", "..."],
  "weaknesses": ["...", "..."],
  "recommendation": "<STRONG CANDIDATE|MODERATE|WEAK MATCH>",
  "summary": "<2-3 sentence professional summary>"
}}""")
        if result and "score" in result:
            score = max(0, min(100, int(result.get("score", 50))))
            skill_match = max(0, min(100, int(result.get("skill_match", 50))))
            strengths = result.get("strengths", [])
            weaknesses = result.get("weaknesses", [])
            recommendation = result.get("recommendation", "MODERATE")
            summary = (
                f"AI Screening Score: {score}/100\n"
                f"Skill Match: {skill_match}%\n"
                f"Strengths: {'; '.join(strengths)}\n"
                f"Areas of Concern: {'; '.join(weaknesses)}\n"
                f"Recommendation: {recommendation}"
            )
            logger.info(f"[AI] screen_resume: LLM evaluation parsed successfully. Score: {score}")
            return {"score": score, "summary": summary, "skill_match": float(skill_match)}
        logger.warning("[AI] screen_resume: OpenRouter returned invalid response. Falling back.")

    logger.info("[AI] screen_resume: running rule-based fallback calculation...")
    # ── Rule-based fallback ──
    cand_list = [s.strip().lower() for s in candidate_skills.split(",") if s.strip()]
    job_list = [s.strip().lower() for s in job_requirements.split(",") if s.strip()]
    if job_list:
        matching = sum(1 for s in job_list if any(s in cs for cs in cand_list))
        skill_match = (matching / len(job_list)) * 100
    else:
        skill_match = 60.0
    exp_score = min(experience_years * 10, 30)
    score = min(round((skill_match * 0.6) + exp_score + 10, 1), 100)
    strengths, weaknesses = [], []
    if skill_match > 60:
        strengths.append("Strong skill alignment with job requirements")
    else:
        weaknesses.append("Limited skill match with requirements")
    if experience_years >= 3:
        strengths.append(f"Good experience level ({experience_years} years)")
    else:
        weaknesses.append("Limited professional experience")
    rec = "STRONG CANDIDATE" if score >= 75 else "MODERATE" if score >= 50 else "WEAK MATCH"
    summary = (
        f"AI Screening Score: {score}/100\nSkill Match: {round(skill_match)}%\n"
        f"Strengths: {'; '.join(strengths)}\nAreas of Concern: {'; '.join(weaknesses)}\n"
        f"Recommendation: {rec}"
    )
    return {"score": score, "summary": summary, "skill_match": round(skill_match, 1)}


# ─────────────────────────────────────────────
# INTERVIEW QUESTIONS
# ─────────────────────────────────────────────
def generate_interview_questions(job_title: str, interview_type: str, skills: str) -> List[Dict]:
    logger.info(f"[AI] generate_interview_questions called for '{job_title}' (type: {interview_type})")
    if _AI_ENABLED:
        logger.info("[AI] generate_interview_questions: calling OpenRouter LLM...")
        result = _chat(f"""Generate 5 interview questions for a {job_title} role.
Interview type: {interview_type}
Key skills: {skills}

Return JSON:
{{
  "questions": [
    {{"question": "...", "category": "{interview_type}", "difficulty": "easy|medium|hard"}},
    ...
  ]
}}""")
        if result and "questions" in result and len(result["questions"]) >= 3:
            logger.info(f"[AI] generate_interview_questions: successfully generated {len(result['questions'])} questions.")
            return result["questions"][:5]
        logger.warning("[AI] generate_interview_questions: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] generate_interview_questions: using static bank fallback questions...")
    # ── Static fallback ──
    banks = {
        "technical": [
            {"question": f"Explain your experience with the key technologies required for {job_title}.", "category": "technical", "difficulty": "medium"},
            {"question": "Describe a complex technical problem you solved. What was your approach?", "category": "technical", "difficulty": "hard"},
            {"question": "How do you ensure code quality and maintainability?", "category": "technical", "difficulty": "medium"},
            {"question": "Explain the difference between scalability and performance optimization.", "category": "technical", "difficulty": "medium"},
            {"question": "How do you handle technical debt in a fast-paced environment?", "category": "technical", "difficulty": "hard"},
        ],
        "behavioral": [
            {"question": "Tell me about a conflict with a team member and how you resolved it.", "category": "behavioral", "difficulty": "medium"},
            {"question": "Describe a situation where you had to meet a tight deadline.", "category": "behavioral", "difficulty": "medium"},
            {"question": "Give an example of leadership in your previous role.", "category": "behavioral", "difficulty": "medium"},
            {"question": "How do you prioritize work with multiple competing deadlines?", "category": "behavioral", "difficulty": "easy"},
            {"question": "Tell me about a time you failed. What did you learn?", "category": "behavioral", "difficulty": "hard"},
        ],
        "hr": [
            {"question": "Why are you interested in this role and our company?", "category": "hr", "difficulty": "easy"},
            {"question": "Where do you see yourself in 5 years?", "category": "hr", "difficulty": "easy"},
            {"question": "What are your salary expectations?", "category": "hr", "difficulty": "medium"},
            {"question": "Why are you looking to leave your current role?", "category": "hr", "difficulty": "medium"},
            {"question": "What motivates you professionally?", "category": "hr", "difficulty": "easy"},
        ],
    }
    questions = banks.get(interview_type, banks["technical"])
    if interview_type not in banks:
        questions = banks["technical"][:2] + banks["behavioral"][:2] + banks["hr"][:1]
    return questions


# ─────────────────────────────────────────────
# INTERVIEW EVALUATION
# ─────────────────────────────────────────────
def evaluate_interview(responses: List[str], questions: List[Dict]) -> Dict:
    logger.info(f"[AI] evaluate_interview called with {len(responses)} responses.")
    if _AI_ENABLED and responses and questions:
        qa_pairs = "\n".join(
            f"Q{i+1}: {q.get('question','')}\nA{i+1}: {responses[i] if i < len(responses) else 'No answer'}"
            for i, q in enumerate(questions)
        )
        logger.info("[AI] evaluate_interview: calling OpenRouter LLM...")
        result = _chat(f"""Evaluate this interview objectively. Score each dimension 1.0-5.0.

{qa_pairs}

Return JSON:
{{
  "scores": {{
    "technical_knowledge": <1.0-5.0>,
    "communication": <1.0-5.0>,
    "problem_solving": <1.0-5.0>,
    "cultural_fit": <1.0-5.0>,
    "enthusiasm": <1.0-5.0>
  }},
  "overall_score": <1.0-5.0>,
  "feedback": "<professional 3-4 sentence evaluation>",
  "recommendation": "<hire|next_round|reject>"
}}""")
        if result and "scores" in result:
            scores = result["scores"]
            overall = round(sum(scores.values()) / len(scores), 1)
            logger.info(f"[AI] evaluate_interview: LLM evaluation parsed successfully. Overall: {overall}")
            return {
                "scores": scores,
                "overall_score": result.get("overall_score", overall),
                "feedback": result.get("feedback", "Evaluation completed."),
                "recommendation": result.get("recommendation", "next_round"),
            }
        logger.warning("[AI] evaluate_interview: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] evaluate_interview: running deterministic fallback evaluator...")
    # ── Deterministic fallback (not random) ──
    base = 3.5
    scores = {
        "technical_knowledge": round(base + 0.5, 1),
        "communication": round(base + 0.7, 1),
        "problem_solving": round(base + 0.3, 1),
        "cultural_fit": round(base + 0.8, 1),
        "enthusiasm": round(base + 0.6, 1),
    }
    overall = round(sum(scores.values()) / len(scores), 1)
    rec = "hire" if overall >= 4.0 else "next_round" if overall >= 3.0 else "reject"
    feedback = (
        "Candidate demonstrated adequate understanding of core concepts. "
        "Communication was clear and structured. "
        f"Overall performance suggests a '{rec.replace('_', ' ')}' decision."
    )
    return {"scores": scores, "overall_score": overall, "feedback": feedback, "recommendation": rec}


# ─────────────────────────────────────────────
# JOB DESCRIPTION GENERATOR
# ─────────────────────────────────────────────
def generate_job_description(title: str, department: str, experience_min: int, experience_max: int, skills: str) -> dict:
    logger.info(f"[AI] generate_job_description called for '{title}' (dept: {department})")
    if _AI_ENABLED:
        logger.info("[AI] generate_job_description: calling OpenRouter LLM...")
        result = _chat(f"""Write a professional job description for:
Title: {title}
Department: {department}
Experience: {experience_min}-{experience_max} years
Key Skills: {skills}

Return JSON:
{{
  "description": "<3-4 paragraph role overview>",
  "responsibilities": ["...", "...", "...", "...", "..."],
  "requirements": ["...", "...", "...", "...", "..."],
  "nice_to_have": ["...", "...", "..."],
  "benefits": ["...", "...", "..."]
}}""")
        if result and "description" in result:
            logger.info("[AI] generate_job_description: LLM generated description successfully.")
            return result
        logger.warning("[AI] generate_job_description: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] generate_job_description: returning static job description template...")
    return {
        "description": f"We are looking for a talented {title} to join our {department} team. You will work on challenging problems and collaborate with a high-performing team.",
        "responsibilities": [
            f"Design and develop solutions as a {title}",
            "Collaborate with cross-functional teams",
            "Participate in code reviews and technical discussions",
            "Mentor junior team members",
            "Contribute to technical roadmap and architecture decisions",
        ],
        "requirements": [
            f"{experience_min}-{experience_max} years of relevant experience",
            f"Proficiency in: {skills}",
            "Strong problem-solving and analytical skills",
            "Excellent communication skills",
            "Bachelor's degree in relevant field or equivalent experience",
        ],
        "nice_to_have": ["Open source contributions", "Relevant certifications", "Startup experience"],
        "benefits": ["Competitive salary", "Health insurance", "Flexible work hours"],
    }


# ─────────────────────────────────────────────
# AI PERFORMANCE REVIEW WRITER
# ─────────────────────────────────────────────
def generate_performance_review(
    employee_name: str,
    designation: str,
    bullet_points: str,
    ratings: dict,
) -> dict:
    logger.info(f"[AI] generate_performance_review called for employee: {employee_name} ({designation})")
    if _AI_ENABLED:
        logger.info("[AI] generate_performance_review: calling OpenRouter LLM...")
        result = _chat(f"""Write a professional performance review for:
Employee: {employee_name}
Role: {designation}
Manager's notes: {bullet_points}
Ratings: Technical={ratings.get('technical', 'N/A')}, Communication={ratings.get('communication', 'N/A')}, Leadership={ratings.get('leadership', 'N/A')}

Return JSON:
{{
  "manager_review": "<professional 3-4 paragraph review>",
  "strengths": "<key strengths paragraph>",
  "improvements": "<areas for improvement paragraph>",
  "recommendation": "<promote|increment|no_change|pip>"
}}""")
        if result and "manager_review" in result:
            logger.info("[AI] generate_performance_review: LLM generated review successfully.")
            return result
        logger.warning("[AI] generate_performance_review: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] generate_performance_review: returning static review template fallback...")
    return {
        "manager_review": f"{employee_name} has demonstrated consistent performance in their role as {designation}. {bullet_points}",
        "strengths": "Shows strong technical aptitude and collaborative spirit.",
        "improvements": "Can improve on time management and proactive communication.",
        "recommendation": "increment",
    }


# ─────────────────────────────────────────────
# ATTRITION RISK PREDICTION
# ─────────────────────────────────────────────
def calculate_attrition_risk(employee, reviews: list, leaves: list, attendance_count: int, skip_llm: bool = False) -> dict:
    logger.info(f"[AI] calculate_attrition_risk called for {employee.full_name} ({employee.designation})")
    risk_score = 0
    factors = []

    # Tenure risk
    joining = employee.joining_date
    tenure_months = (get_ist_date() - joining).days // 30 if joining else 24
    if tenure_months < 12:
        risk_score += 25
        factors.append("Less than 1 year tenure — high flight risk window")
    elif tenure_months < 18:
        risk_score += 15
        factors.append("Early tenure phase — moderate flight risk")

    # Leave pattern risk
    recent_leaves = len([l for l in leaves if l.status.value == "approved"])
    if recent_leaves > 8:
        risk_score += 25
        factors.append(f"High leave usage ({recent_leaves} days) — possible disengagement")
    elif recent_leaves > 5:
        risk_score += 10
        factors.append(f"Above-average leave usage ({recent_leaves} days)")

    # Performance risk
    if reviews:
        last_rating = reviews[0].overall_rating if reviews[0].overall_rating else None
        if last_rating and last_rating < 3.0:
            risk_score += 30
            factors.append(f"Low performance rating ({last_rating}/5) — PIP risk")
        elif last_rating and last_rating < 3.5:
            risk_score += 15
            factors.append(f"Below-average performance ({last_rating}/5)")
    else:
        risk_score += 10
        factors.append("No performance review on record")

    # Salary risk (low CTC relative to designation)
    if employee.ctc and employee.ctc < 800000:
        risk_score += 20
        factors.append("Below-market compensation — retention risk")

    # Attendance risk
    if attendance_count < 15:
        risk_score += 10
        factors.append("Low attendance this month")

    risk_score = min(risk_score, 100)
    risk_level = "high" if risk_score >= 60 else "medium" if risk_score >= 30 else "low"

    # LLM explanation
    explanation = ""
    if not skip_llm and _AI_ENABLED and factors:
        logger.info("[AI] calculate_attrition_risk: querying LLM for retention advice...")
        result = _chat(f"""An employee named {employee.full_name} ({employee.designation}) has an attrition risk score of {risk_score}/100.
Risk factors identified: {'; '.join(factors)}

Write a 2-sentence HR recommendation on how to retain this employee.
Return JSON: {{"recommendation": "..."}}""")
        explanation = result.get("recommendation", "")
        if explanation:
            logger.info("[AI] calculate_attrition_risk: LLM advice generated successfully.")

    if not explanation:
        logger.info("[AI] calculate_attrition_risk: using static risk level fallback description.")
        if risk_level == "high":
            explanation = "Immediate manager check-in and compensation review recommended."
        elif risk_level == "medium":
            explanation = "Schedule a career development conversation within 30 days."
        else:
            explanation = "Employee appears stable. Continue regular engagement."

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "factors": factors,
        "recommendation": explanation,
    }


# ─────────────────────────────────────────────
# HR COPILOT — Natural Language Query
# ─────────────────────────────────────────────
def hr_copilot_chat(message: str, context: dict) -> str:
    logger.info(f"[AI] hr_copilot_chat received message: '{message}'")
    if not _AI_ENABLED:
        logger.warning("[AI] hr_copilot_chat: AI is not enabled. Prompting configuration.")
        return "AI Copilot requires an OPENROUTER_API_KEY environment variable. Please set it to enable this feature. Get a free key at https://openrouter.ai/keys"

    system = """You are an intelligent HR assistant for an HRMS system called TechCorp HRMS.
You have access to real HR data provided in the context. Answer questions naturally and helpfully.
Be concise, professional, and data-driven. If data is not in context, say so honestly.

STRICT GUIDELINES:
1. DO NOT HALLUCINATE: Do not make up facts, numbers, or events. Only use the provided context.
2. CURRENT USER CONTEXT: The employee asking the question is defined in the 'current_user' block. When the user uses 'I', 'me', 'my', 'mine', or asks about their own details, refer directly to the 'current_user' data block.
3. LEAVE BALANCE VS LEAVE REQUESTS:
   - "Leave left" or "leave balance" refers to remaining leaves. Answer this using 'casual_leave_balance', 'sick_leave_balance', and 'earned_leave_balance' from the 'current_user' block.
   - "Leave requests" refers to past or pending leave applications, which are listed in 'current_user_leave_requests' or 'pending_leaves_detail'.
4. If a query is personal (e.g. "how many leave left"), immediately look up the current user's leave balances in 'current_user' and list them clearly (e.g. Casual: X, Sick: Y, Earned: Z).
5. ORGANIZATIONAL / EMPLOYEE QUERIES: If the user asks about other employees or general organization statistics (e.g., headcount, manager hierarchies, departments, email addresses, joining dates), refer to the 'employee_list' block. This list contains the complete list of employees, including active and inactive status, their human-readable department names, reporting manager names, emails, joining dates, and leave balances (subject to role visibility). Match names, emails, or designations precisely to retrieve information about specific colleagues.
6. CONFIDENTIAL INFORMATION SECURITY: Under no circumstances should you ever reveal or make up confidential record data such as PAN numbers, Aadhaar numbers, credentials, bank account numbers, bank routing/IFSC codes, or CTC/salary/compensation details for any employee (including the requester). If the user asks for these details (e.g., "What is my PAN number?", "What is Sanjay's salary?", "What is my CTC?", or "Show me Suresh's bank details"), you must decline to answer, state that this is confidential data not accessible in chat, and instruct them to check their official Profile or Salary/Documents section instead. Do not try to guess or hallucinate these values."""

    context_str = json.dumps(context, indent=2, default=str)
    prompt = f"""HR Data Context:
{context_str}

User Question: {message}

Answer the question based on the data above. Be specific with numbers and names."""

    try:
        logger.info("[AI] hr_copilot_chat: sending query to LLM...")
        result = _chat_text(prompt, system, max_tokens=512)
        if result:
            logger.info("[AI] hr_copilot_chat response generated successfully.")
            return result
        logger.warning("[AI] hr_copilot_chat: LLM returned empty string. Returning default warning.")
        return "Sorry, I couldn't process that request. Please try again."
    except Exception as e:
        logger.error(f"[AI] hr_copilot_chat error: {e}")
        err_msg = str(e)
        if "429" in err_msg or "RESOURCE_EXHAUSTED" in err_msg or "quota" in err_msg.lower():
            return "I have temporarily exceeded the OpenRouter API rate limits (RESOURCE_EXHAUSTED). Please wait a moment and try again shortly!"
        return "Sorry, I couldn't process that request. Please try again."


# ─────────────────────────────────────────────
# RESUME PARSER — Extract structured data from resume text
# ─────────────────────────────────────────────
def parse_resume_text(resume_text: str) -> dict:
    """Parse extracted resume text into structured candidate data using AI."""
    logger.info(f"[AI] parse_resume_text called. Length: {len(resume_text) if resume_text else 0} characters.")
    if _AI_ENABLED and resume_text:
        logger.info("[AI] parse_resume_text: calling OpenRouter LLM resume parser...")
        result = _chat(f"""Extract structured information from this resume text.
Be thorough and accurate. If a field is not found, use null.

Resume Text:
{resume_text[:4000]}

Return JSON:
{{
  "full_name": "<candidate full name>",
  "email": "<email address or null>",
  "phone": "<phone number or null>",
  "current_company": "<current/last company or null>",
  "current_designation": "<current/last job title or null>",
  "experience_years": <total years of experience as number>,
  "skills": "<comma-separated skills list>",
  "education": "<highest education - degree, college>",
  "location": "<city, state or null>",
  "expected_salary": null,
  "summary": "<2-3 sentence professional summary>"
}}""", max_tokens=1024)
        if result and "full_name" in result:
            logger.info(f"[AI] parse_resume_text successful. Name found: {result.get('full_name')}")
            return result
        logger.warning("[AI] parse_resume_text: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] parse_resume_text: returning empty structured fallback schema...")
    # Basic fallback — return empty structured response
    return {
        "full_name": "",
        "email": "",
        "phone": "",
        "current_company": "",
        "current_designation": "",
        "experience_years": 0,
        "skills": "",
        "education": "",
        "location": "",
        "expected_salary": None,
        "summary": "Resume parsed in fallback mode. Please review and fill details manually."
    }


# ─────────────────────────────────────────────
# AI ONBOARDING PLAN GENERATOR
# ─────────────────────────────────────────────
def generate_onboarding_plan(employee_name: str, designation: str, department: str) -> dict:
    """Generate a personalized onboarding plan for a new employee."""
    logger.info(f"[AI] generate_onboarding_plan called for {employee_name} ({designation} in {department})")
    if _AI_ENABLED:
        logger.info("[AI] generate_onboarding_plan: calling OpenRouter LLM onboarding generator...")
        result = _chat(f"""Create a detailed 30-day onboarding plan for:
Employee: {employee_name}
Role: {designation}
Department: {department}

Return JSON:
{{
  "plan_name": "30-Day Onboarding: {designation}",
  "tasks": [
    {{
      "title": "<task title>",
      "description": "<what to do>",
      "category": "<documentation|training|access|introduction|equipment>",
      "day": <which day (1-30)>,
      "priority": "<high|medium|low>"
    }},
    ... (generate 12-15 tasks spread across 30 days)
  ]
}}""", max_tokens=2048)
        if result and "tasks" in result:
            logger.info(f"[AI] generate_onboarding_plan: LLM generated onboarding plan with {len(result['tasks'])} tasks.")
            return result
        logger.warning("[AI] generate_onboarding_plan: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] generate_onboarding_plan: using static department onboarding template fallback...")
    # Fallback plan
    return {
        "plan_name": f"30-Day Onboarding: {designation}",
        "tasks": [
            {"title": "Complete HR documentation", "description": "Submit all joining documents, ID proofs, and bank details", "category": "documentation", "day": 1, "priority": "high"},
            {"title": "System access setup", "description": "Get email, Slack, JIRA, and other tool access", "category": "access", "day": 1, "priority": "high"},
            {"title": "Team introduction", "description": "Meet with team members and understand team structure", "category": "introduction", "day": 1, "priority": "high"},
            {"title": "Equipment setup", "description": "Laptop, monitor, and workstation setup", "category": "equipment", "day": 1, "priority": "high"},
            {"title": "Company overview session", "description": "Understand company mission, values, and culture", "category": "training", "day": 2, "priority": "medium"},
            {"title": "Department orientation", "description": f"Deep dive into {department} department goals and processes", "category": "training", "day": 3, "priority": "medium"},
            {"title": "Meet your buddy", "description": "Introduction to assigned onboarding buddy", "category": "introduction", "day": 2, "priority": "medium"},
            {"title": "Security & compliance training", "description": "Complete mandatory security awareness training", "category": "training", "day": 5, "priority": "high"},
            {"title": "Project overview", "description": "Understand current projects and your role", "category": "training", "day": 5, "priority": "medium"},
            {"title": "First task assignment", "description": "Start with a small starter task to get familiar", "category": "training", "day": 7, "priority": "medium"},
            {"title": "Week 1 check-in", "description": "1:1 with manager to discuss first week experience", "category": "introduction", "day": 7, "priority": "high"},
            {"title": "Tool & process training", "description": f"Complete {department}-specific tool training", "category": "training", "day": 10, "priority": "medium"},
            {"title": "Week 2 check-in", "description": "Review progress and address any concerns", "category": "introduction", "day": 14, "priority": "medium"},
            {"title": "30-day goal setting", "description": "Set initial performance goals with manager", "category": "training", "day": 15, "priority": "high"},
            {"title": "Month-end review", "description": "Comprehensive 30-day review and feedback session", "category": "introduction", "day": 30, "priority": "high"},
        ],
    }


# ─────────────────────────────────────────────
# AI ENGAGEMENT ANALYSIS
# ─────────────────────────────────────────────
def analyze_survey_sentiment(responses: List[str]) -> dict:
    """Analyze sentiment of survey responses."""
    logger.info(f"[AI] analyze_survey_sentiment called with {len(responses) if responses else 0} responses.")
    if _AI_ENABLED and responses:
        logger.info("[AI] analyze_survey_sentiment: calling OpenRouter LLM sentiment analysis...")
        result = _chat(f"""Analyze the sentiment of these employee survey responses:
{json.dumps(responses[:20])}

Return JSON:
{{
  "overall_sentiment": "<positive|neutral|negative>",
  "sentiment_score": <0.0 to 1.0, where 1.0 is most positive>,
  "key_themes": ["theme1", "theme2", "theme3"],
  "concerns": ["concern1", "concern2"],
  "positives": ["positive1", "positive2"],
  "summary": "<2-3 sentence summary of the feedback>"
}}""")
        if result and "sentiment_score" in result:
            logger.info(f"[AI] analyze_survey_sentiment: LLM scored sentiment as: {result.get('sentiment_score')}")
            return result
        logger.warning("[AI] analyze_survey_sentiment: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] analyze_survey_sentiment: using static fallback sentiment scores...")

    return {
        "overall_sentiment": "neutral",
        "sentiment_score": 0.5,
        "key_themes": ["General feedback"],
        "concerns": [],
        "positives": [],
        "summary": "Survey responses received. AI analysis requires API key for detailed insights."
    }


def detect_burnout_risk(employee_name: str, overtime_hours: float, leave_days: int, mood_scores: List[int]) -> dict:
    """Detect burnout risk based on multiple signals."""
    logger.info(f"[AI] detect_burnout_risk called for {employee_name}")
    risk_score = 0
    factors = []

    if overtime_hours > 20:
        risk_score += 30
        factors.append(f"High overtime ({overtime_hours}h this month)")
    elif overtime_hours > 10:
        risk_score += 15
        factors.append(f"Moderate overtime ({overtime_hours}h)")

    if leave_days > 5:
        risk_score += 20
        factors.append(f"Frequent leaves ({leave_days} days)")

    if mood_scores:
        avg_mood = sum(mood_scores) / len(mood_scores)
        if avg_mood < 2.5:
            risk_score += 35
            factors.append(f"Low mood trend (avg {avg_mood:.1f}/5)")
        elif avg_mood < 3.5:
            risk_score += 15
            factors.append(f"Below-average mood (avg {avg_mood:.1f}/5)")

    risk_score = min(risk_score, 100)
    risk_level = "high" if risk_score >= 60 else "medium" if risk_score >= 30 else "low"

    recommendation = ""
    if _AI_ENABLED and factors:
        logger.info("[AI] detect_burnout_risk: querying LLM for burnout recommendation...")
        result = _chat(f"""Employee {employee_name} has burnout risk indicators:
{'; '.join(factors)}
Risk score: {risk_score}/100

Provide a 2-sentence actionable recommendation for their manager.
Return JSON: {{"recommendation": "..."}}""")
        recommendation = result.get("recommendation", "")
        if recommendation:
            logger.info("[AI] detect_burnout_risk: LLM recommendation generated successfully.")

    if not recommendation:
        logger.info("[AI] detect_burnout_risk: using static rule-based risk recommendation.")
        if risk_level == "high":
            recommendation = "Urgent: Schedule a wellness check-in. Consider workload redistribution and mandatory time off."
        elif risk_level == "medium":
            recommendation = "Monitor closely. Encourage regular breaks and discuss workload balance in next 1:1."
        else:
            recommendation = "No immediate concerns. Continue regular check-ins."

    return {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "factors": factors,
        "recommendation": recommendation,
    }


# ─────────────────────────────────────────────
# AI SKILL GAP ANALYSIS
# ─────────────────────────────────────────────
def analyze_skill_gaps(employee_skills: List[str], role_requirements: List[str], designation: str) -> dict:
    """Analyze skill gaps for an employee vs their role requirements."""
    logger.info(f"[AI] analyze_skill_gaps called for designation: {designation}")
    if _AI_ENABLED:
        logger.info("[AI] analyze_skill_gaps: calling OpenRouter LLM gap analyzer...")
        result = _chat(f"""Analyze skill gaps for a {designation}:
Current skills: {', '.join(employee_skills)}
Required skills: {', '.join(role_requirements)}

Return JSON:
{{
  "matched_skills": ["skill1", "skill2"],
  "missing_skills": ["skill3", "skill4"],
  "skill_score": <0-100>,
  "recommended_training": [
    {{"skill": "skill3", "priority": "high|medium|low", "suggested_course": "course name"}},
    ...
  ],
  "career_advice": "<1-2 sentence career development advice>"
}}""")
        if result and "matched_skills" in result:
            logger.info("[AI] analyze_skill_gaps: LLM response parsed successfully.")
            return result
        logger.warning("[AI] analyze_skill_gaps: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] analyze_skill_gaps: using simple list comparison fallback...")
    # Fallback
    emp_lower = [s.lower().strip() for s in employee_skills]
    req_lower = [s.lower().strip() for s in role_requirements]
    matched = [s for s in role_requirements if s.lower().strip() in emp_lower]
    missing = [s for s in role_requirements if s.lower().strip() not in emp_lower]
    score = int((len(matched) / max(len(role_requirements), 1)) * 100)

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "skill_score": score,
        "recommended_training": [{"skill": s, "priority": "high", "suggested_course": f"Learn {s}"} for s in missing[:5]],
        "career_advice": f"Focus on acquiring {', '.join(missing[:3])} to strengthen your profile for {designation}." if missing else "Great skill coverage! Consider deepening expertise in current skills."
    }


# ─────────────────────────────────────────────
# AI WORKFORCE ANALYTICS
# ─────────────────────────────────────────────
def generate_workforce_insights(stats: dict) -> dict:
    """Generate AI insights from workforce data."""
    logger.info("[AI] generate_workforce_insights called.")
    if _AI_ENABLED:
        logger.info("[AI] generate_workforce_insights: calling OpenRouter LLM insight generator...")
        result = _chat(f"""Analyze this HR workforce data and generate actionable insights:
{json.dumps(stats, default=str)}

Return JSON:
{{
  "insights": [
    {{"title": "<insight title>", "description": "<1-2 sentence detail>", "type": "positive|warning|action", "priority": "high|medium|low"}},
    ... (generate 4-6 insights)
  ],
  "executive_summary": "<3-4 sentence executive summary of the workforce state>"
}}""")
        if result and "insights" in result:
            logger.info(f"[AI] generate_workforce_insights: LLM generated {len(result['insights'])} insights successfully.")
            return result
        logger.warning("[AI] generate_workforce_insights: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] generate_workforce_insights: returning basic default workforce insights...")
    return {
        "insights": [
            {"title": "Workforce Overview", "description": f"Total {stats.get('total_employees', 0)} employees across departments.", "type": "positive", "priority": "low"},
            {"title": "Open Positions", "description": f"{stats.get('open_positions', 0)} positions currently open for hiring.", "type": "action", "priority": "medium"},
        ],
        "executive_summary": "Workforce metrics are within normal ranges. AI-powered detailed analysis requires API key configuration."
    }


# ─────────────────────────────────────────────
# AI SUCCESSION PLANNING
# ─────────────────────────────────────────────
def assess_succession_readiness(employee_name: str, designation: str, target_role: str, performance_rating: float, tenure_years: float, skills: List[str]) -> dict:
    """Assess an employee's readiness for a target role."""
    logger.info(f"[AI] assess_succession_readiness called for {employee_name} -> {target_role}")
    if _AI_ENABLED:
        logger.info("[AI] assess_succession_readiness: calling OpenRouter LLM succession assessor...")
        result = _chat(f"""Assess succession readiness:
Employee: {employee_name}
Current Role: {designation}
Target Role: {target_role}
Performance Rating: {performance_rating}/5
Tenure: {tenure_years} years
Skills: {', '.join(skills)}

Return JSON:
{{
  "readiness": "<ready_now|1-2_years|3+_years>",
  "readiness_score": <0-100>,
  "strengths_for_role": ["..."],
  "development_gaps": ["..."],
  "development_actions": [
    {{"action": "...", "timeline": "...", "priority": "high|medium|low"}}
  ],
  "assessment": "<2-3 sentence assessment>"
}}""")
        if result and "readiness" in result:
            logger.info(f"[AI] assess_succession_readiness: LLM assessment parsed successfully. Readiness: {result.get('readiness')}")
            return result
        logger.warning("[AI] assess_succession_readiness: LLM returned empty or invalid response. Falling back.")

    logger.info("[AI] assess_succession_readiness: running mathematical assessment fallback logic...")
    # Fallback
    score = min(int(performance_rating * 15 + tenure_years * 5 + len(skills) * 2), 100)
    readiness = "ready_now" if score >= 75 else "1-2_years" if score >= 50 else "3+_years"
    return {
        "readiness": readiness,
        "readiness_score": score,
        "strengths_for_role": skills[:3],
        "development_gaps": ["Leadership experience", "Strategic thinking"],
        "development_actions": [
            {"action": "Leadership training program", "timeline": "6 months", "priority": "high"},
            {"action": "Cross-functional project lead", "timeline": "3 months", "priority": "medium"},
        ],
        "assessment": f"{employee_name} shows {'strong' if score >= 75 else 'moderate' if score >= 50 else 'developing'} readiness for {target_role}."
    }


# ─────────────────────────────────────────────
# AI RETRIEVAL-AUGMENTED GENERATION (RAG)
# ─────────────────────────────────────────────
def extract_file_text(file_path: str) -> str:
    """Robustly extract plain text from PDF, DOCX, or TXT files."""
    logger.info(f"[RAG] extract_file_text called for path: {file_path}")
    if not file_path or not os.path.exists(file_path):
        logger.warning(f"[RAG] file_path is empty or does not exist: {file_path}")
        return ""
    
    ext = os.path.splitext(file_path)[1].lower()
    try:
        if ext == ".pdf":
            logger.info("[RAG] Parsing PDF document using PyMuPDF...")
            import fitz
            doc = fitz.open(file_path)
            text = ""
            for page in doc:
                text += page.get_text()
            return text
        elif ext in [".docx", ".doc"]:
            logger.info("[RAG] Parsing Word document using python-docx...")
            import docx
            doc = docx.Document(file_path)
            return "\n".join([p.text for p in doc.paragraphs])
        elif ext in [".txt", ".md", ".json", ".csv"]:
            logger.info("[RAG] Parsing text-based document...")
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
    except Exception as e:
        logger.error(f"[RAG] Error parsing {file_path}: {e}")
    return ""


def search_documents_rag(query: str, db, employee_id: Optional[int] = None) -> str:
    """RAG Retrieval: Search all active documents (isolated by role), chunk them, and return matching context."""
    logger.info(f"[RAG] search_documents_rag called for query: '{query}'")
    from app.models.document import Document, DocumentStatus
    
    # Clean query and extract key terms (ignoring standard stop words)
    stop_words = {"what", "is", "our", "the", "a", "an", "on", "for", "in", "to", "with", "of", "about", "policy", "employee", "company"}
    terms = [word.lower() for word in query.split() if word.isalnum() and word.lower() not in stop_words]
    
    if not terms:
        logger.info("[RAG] Query terms list is empty after removing stop words.")
        return ""
        
    # Get active documents
    doc_query = db.query(Document).filter(Document.status == DocumentStatus.ACTIVE)
    if employee_id:
        doc_query = doc_query.filter((Document.employee_id == employee_id) | (Document.employee_id == None))
    
    documents = doc_query.all()
    logger.info(f"[RAG] Found {len(documents)} active documents to scan.")
    
    scored_chunks = []
    for doc in documents:
        if not doc.file_path or not os.path.exists(doc.file_path):
            continue
            
        text = extract_file_text(doc.file_path)
        if not text:
            continue
            
        # Split into paragraph chunks (excluding empty/tiny lines)
        chunks = [c.strip() for c in text.split("\n\n") if len(c.strip()) > 15]
        for c in chunks:
            # Simple keyword scoring (TF-IDF approximation)
            score = 0
            chunk_lower = c.lower()
            for term in terms:
                count = chunk_lower.count(term)
                if count > 0:
                    score += count * (1.5 if term in doc.title.lower() or (doc.tags and term in doc.tags.lower()) else 1.0)
            
            if score > 0:
                scored_chunks.append({
                    "text": c,
                    "source": doc.file_name,
                    "title": doc.title,
                    "score": score
                })
                
    # Sort chunks by score desc and take top 3
    scored_chunks.sort(key=lambda x: x["score"], reverse=True)
    top_chunks = scored_chunks[:3]
    
    logger.info(f"[RAG] Top matching scored chunks found: {len(top_chunks)}")
    if not top_chunks:
        return ""
        
    context_blocks = []
    for ch in top_chunks:
        logger.info(f"[RAG] Matched chunk from document '{ch['title']}' (Score: {ch['score']})")
        context_blocks.append(f"[Source Document: {ch['title']} ({ch['source']})]\n{ch['text']}")
        
    return "\n\n".join(context_blocks)
