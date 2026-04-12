"""Mock AI Service — Simulates AI-powered resume screening and interviews."""
import random
import json
from typing import List, Dict


def screen_resume(candidate_skills: str, job_requirements: str, experience_years: float) -> dict:
    """Simulate AI resume screening. Returns a score and summary."""
    
    if not candidate_skills:
        candidate_skills = ""
    if not job_requirements:
        job_requirements = ""
    
    candidate_skill_list = [s.strip().lower() for s in candidate_skills.split(",") if s.strip()]
    job_skill_list = [s.strip().lower() for s in job_requirements.split(",") if s.strip()]
    
    # Calculate skill match
    if job_skill_list:
        matching = sum(1 for s in job_skill_list if any(s in cs for cs in candidate_skill_list))
        skill_match = (matching / len(job_skill_list)) * 100
    else:
        skill_match = random.uniform(50, 90)
    
    # Factor in experience
    exp_score = min(experience_years * 10, 30)
    
    # Calculate overall score
    base_score = (skill_match * 0.6) + exp_score + random.uniform(5, 15)
    score = min(round(base_score, 1), 100)
    
    # Generate summary
    strengths = []
    weaknesses = []
    
    if skill_match > 60:
        strengths.append("Strong skill alignment with job requirements")
    else:
        weaknesses.append("Limited skill match with requirements")
    
    if experience_years >= 3:
        strengths.append(f"Good experience level ({experience_years} years)")
    elif experience_years >= 1:
        strengths.append(f"Adequate experience ({experience_years} years)")
    else:
        weaknesses.append("Limited professional experience")
    
    summary = f"AI Screening Score: {score}/100\n"
    summary += f"Skill Match: {round(skill_match)}%\n"
    if strengths:
        summary += f"Strengths: {'; '.join(strengths)}\n"
    if weaknesses:
        summary += f"Areas of Concern: {'; '.join(weaknesses)}\n"
    
    if score >= 75:
        summary += "Recommendation: STRONG CANDIDATE — Proceed to interview"
    elif score >= 50:
        summary += "Recommendation: MODERATE — Consider for phone screening"
    else:
        summary += "Recommendation: WEAK MATCH — May not be suitable"
    
    return {
        "score": score,
        "summary": summary,
        "skill_match": round(skill_match, 1),
    }


def generate_interview_questions(job_title: str, interview_type: str, skills: str) -> List[Dict]:
    """Generate mock AI interview questions based on job and type."""
    
    technical_questions = [
        {"question": f"Explain your experience with the key technologies required for the {job_title} role.", "category": "technical", "difficulty": "medium"},
        {"question": "Describe a complex technical problem you solved recently. What was your approach?", "category": "technical", "difficulty": "hard"},
        {"question": "How do you ensure code quality and maintainability in your projects?", "category": "technical", "difficulty": "medium"},
        {"question": "Explain the difference between scalability and performance optimization.", "category": "technical", "difficulty": "medium"},
        {"question": "How do you handle technical debt in a fast-paced environment?", "category": "technical", "difficulty": "hard"},
    ]
    
    behavioral_questions = [
        {"question": "Tell me about a time when you had a conflict with a team member. How did you resolve it?", "category": "behavioral", "difficulty": "medium"},
        {"question": "Describe a situation where you had to meet a tight deadline. How did you manage it?", "category": "behavioral", "difficulty": "medium"},
        {"question": "Give an example of how you've shown leadership in your previous role.", "category": "behavioral", "difficulty": "medium"},
        {"question": "How do you prioritize your work when you have multiple competing deadlines?", "category": "behavioral", "difficulty": "easy"},
        {"question": "Tell me about a time you failed. What did you learn from it?", "category": "behavioral", "difficulty": "hard"},
    ]
    
    hr_questions = [
        {"question": "Why are you interested in this role and our company?", "category": "hr", "difficulty": "easy"},
        {"question": "Where do you see yourself in 5 years?", "category": "hr", "difficulty": "easy"},
        {"question": "What are your salary expectations?", "category": "hr", "difficulty": "medium"},
        {"question": "Why are you looking to leave your current role?", "category": "hr", "difficulty": "medium"},
        {"question": "What motivates you in your professional life?", "category": "hr", "difficulty": "easy"},
    ]
    
    if interview_type == "technical":
        return technical_questions
    elif interview_type == "behavioral":
        return behavioral_questions
    elif interview_type == "hr":
        return hr_questions
    else:
        return technical_questions[:2] + behavioral_questions[:2] + hr_questions[:1]


def evaluate_interview(responses: List[str], questions: List[Dict]) -> Dict:
    """Simulate AI evaluation of interview responses."""
    
    scores = {
        "technical_knowledge": round(random.uniform(3.0, 4.8), 1),
        "communication": round(random.uniform(3.0, 4.9), 1),
        "problem_solving": round(random.uniform(2.8, 4.7), 1),
        "cultural_fit": round(random.uniform(3.2, 4.9), 1),
        "enthusiasm": round(random.uniform(3.0, 5.0), 1),
    }
    
    overall = round(sum(scores.values()) / len(scores), 1)
    
    feedback_templates = [
        "Candidate demonstrated solid understanding of core concepts.",
        "Communication skills are above average with clear articulation.",
        "Shows good problem-solving approach with structured thinking.",
        "Appears to be a good cultural fit based on values alignment.",
        "Exhibits genuine enthusiasm for the role and growth opportunities.",
    ]
    
    feedback = "\n".join(random.sample(feedback_templates, min(3, len(feedback_templates))))
    
    if overall >= 4.0:
        recommendation = "hire"
        feedback += "\n\nOverall: Strong candidate. Recommended for HIRE."
    elif overall >= 3.0:
        recommendation = "next_round"
        feedback += "\n\nOverall: Decent performance. Consider for NEXT ROUND."
    else:
        recommendation = "reject"
        feedback += "\n\nOverall: Below expectations. NOT RECOMMENDED."
    
    return {
        "scores": scores,
        "overall_score": overall,
        "feedback": feedback,
        "recommendation": recommendation,
    }
