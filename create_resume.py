"""
create_resume.py
----------------
Generates a clean, valid PDF resume for Manthan Raut using PyMuPDF (fitz).
"""

import os
import fitz

def generate_resume(filename: str):
    doc = fitz.open()
    page = doc.new_page(width=595, height=842) # A4 size

    y = 50

    # Header
    page.insert_text((50, y), "MANTHAN RAUT", fontsize=22, fontname="helvetica-bold", color=(0, 0.33, 0.65))
    y += 20
    page.insert_text((50, y), "Software Engineer & AI Application Developer", fontsize=12, fontname="helvetica-bold", color=(0.2, 0.2, 0.2))
    y += 18
    page.insert_text((50, y), "Email: manthanr141@gmail.com | Phone: +91 9529883808 | Location: India", fontsize=10, fontname="helvetica", color=(0.3, 0.3, 0.3))
    y += 14
    page.insert_text((50, y), "GitHub: github.com/manthanraut | LinkedIn: linkedin.com/in/manthan-raut", fontsize=10, fontname="helvetica", color=(0.3, 0.3, 0.3))
    y += 25

    # Line separator
    page.draw_line((50, y), (545, y), color=(0.8, 0.8, 0.8), width=1)
    y += 20

    # Professional Summary
    page.insert_text((50, y), "PROFESSIONAL SUMMARY", fontsize=12, fontname="helvetica-bold", color=(0, 0.33, 0.65))
    y += 15
    summary = (
        "Enthusiastic and results-driven Software Engineer with expertise in Python, Full Stack Web Development, "
        "REST APIs, and AI/LLM Application Development. Hands-on experience building scalable backends with FastAPI, "
        "SQLAlchemy, PostgreSQL, and integrating LLMs, browser automation, and multi-agent workflows."
    )
    # Simple line wrapping
    words = summary.split()
    line = ""
    for w in words:
        if len(line + " " + w) > 85:
            page.insert_text((50, y), line, fontsize=10, fontname="helvetica")
            y += 14
            line = w
        else:
            line += " " + w if line else w
    if line:
        page.insert_text((50, y), line, fontsize=10, fontname="helvetica")
        y += 20

    # Technical Skills
    page.insert_text((50, y), "TECHNICAL SKILLS", fontsize=12, fontname="helvetica-bold", color=(0, 0.33, 0.65))
    y += 15
    skills = [
        ("Programming Languages", "Python, JavaScript, TypeScript, SQL, HTML5, CSS3"),
        ("Backend Frameworks", "FastAPI, Flask, Django, REST APIs, Node.js"),
        ("Frontend & UI", "React, HTML/CSS, Tailwind CSS, JavaScript (ES6+)"),
        ("Databases & Tools", "PostgreSQL, SQLite, SQLAlchemy, Redis, Docker, Git, Linux, GitHub Actions"),
        ("AI & Automation", "LangChain, Groq LLM, OpenAI API, Playwright, BeautifulSoup, Twilio API"),
    ]
    for cat, items in skills:
        page.insert_text((50, y), f"• {cat}: ", fontsize=10, fontname="helvetica-bold")
        page.insert_text((180, y), items, fontsize=10, fontname="helvetica")
        y += 14
    y += 15

    # Work Experience / Projects
    page.insert_text((50, y), "PROJECTS & EXPERIENCE", fontsize=12, fontname="helvetica-bold", color=(0, 0.33, 0.65))
    y += 15

    proj1 = [
        ("Autonomous Internship Agent (Python, FastAPI, LangChain, Groq, Twilio, Playwright)", "2024"),
        ("• Architected an autonomous multi-agent pipeline to scrape, evaluate, and apply for software engineering internships."),
        ("• Built intelligent job-matching engine using Groq LLM to calculate match scores against candidate resumes."),
        ("• Implemented automated approval notifications via Twilio WhatsApp API and webhook handling for user decisions."),
        ("• Integrated Playwright browser automation for automated application submissions."),
    ]
    for header, date in [proj1[0]]:
        page.insert_text((50, y), header, fontsize=10, fontname="helvetica-bold")
        y += 14
    for line in proj1[1:]:
        page.insert_text((60, y), line[0], fontsize=9.5, fontname="helvetica")
        y += 13
    y += 10

    proj2 = [
        ("AI-Powered Full Stack Web Applications (React, FastAPI, PostgreSQL)", "2023 - 2024"),
        ("• Developed responsive web applications with React frontend and FastAPI REST backend."),
        ("• Designed PostgreSQL relational database schemas with SQLAlchemy ORM and migration tracking."),
        ("• Containerized applications using Docker and deployed CI/CD pipelines via GitHub Actions."),
    ]
    for header, date in [proj2[0]]:
        page.insert_text((50, y), header, fontsize=10, fontname="helvetica-bold")
        y += 14
    for line in proj2[1:]:
        page.insert_text((60, y), line[0], fontsize=9.5, fontname="helvetica")
        y += 13
    y += 15

    # Education
    page.insert_text((50, y), "EDUCATION", fontsize=12, fontname="helvetica-bold", color=(0, 0.33, 0.65))
    y += 15
    page.insert_text((50, y), "Bachelor of Technology in Computer Science / Information Technology", fontsize=10, fontname="helvetica-bold")
    y += 13
    page.insert_text((50, y), "Relevant Coursework: Data Structures & Algorithms, Database Systems, Web Development, Software Engineering", fontsize=9.5, fontname="helvetica", color=(0.3, 0.3, 0.3))

    doc.save(filename)
    print(f"Successfully generated clean PDF resume: {filename}")

if __name__ == "__main__":
    generate_resume("Manthan_Raut_Resume (1).pdf")
    generate_resume("data/current_resume.pdf")
