import os
import io
import datetime
import requests
import google.generativeai as genai
import streamlit as st
import json
from pymongo import MongoClient
from PyPDF2 import PdfReader
from bs4 import BeautifulSoup
from googlesearch import search
from fpdf import FPDF
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
genai.configure(api_key="")

# Initialize MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["internshipdata"]
resumes_collection = mongo_db["intern"]

# Function to extract text from PDF
def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

# Function to get ATS analysis from Gemini AI
def get_gemini_response(resume_text, job_description):
    prompt = f"""
    Act as a professional ATS (Applicant Tracking System). Analyze the given resume based on the provided job description.

    Resume Text:  
    {resume_text}  

    Job Description:  
    {job_description}  

    Please respond ONLY in a JSON format with the following structure:
    {{
        "ATS_Match_Score": 85,
        "Missing_Keywords": ["Kubernetes", "GCP"],
        "Formatting_Issues": ["Work Experience section appears empty", "Date format should be MM/YYYY"],
        "Job_Title_Match": "The job title 'Python Engineer' was not found in the resume. Consider adding it.",
        "Contact_Information": {{
            "Email": "Provided",
            "Phone": "Provided",
            "Address": "Not Found"
        }},
        "Education_Match": "Education details are missing. Please add them.",
        "Hard_Skills_Match": {{
            "Resume_Skills": ["Python", "Relational Database"],
            "JD_Skills": ["Python", "Kubernetes"],
            "Missing_Skills": ["Kubernetes"]
        }},
        "File_Format": "ATS-Compatible PDF",
        "Summary": "Your resume is strong but missing key cloud-related skills like Kubernetes."
    }}
    """

    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)

    if not response.text:
        return {"error": "Empty response from AI"}

    try:
        ats_response = json.loads(response.text.strip())  # Ensures proper JSON parsing
        return ats_response
    except json.JSONDecodeError:
        return {"error": "AI response was not valid JSON", "raw_text": response.text}

            

# Function to search for internships with metadata
def search_google_jobs(query):
    jobs = []
    for url in search(query, num_results=5):  # Limit results to 5 for efficiency
        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")
            
            title = soup.title.string if soup.title else "No Title Found"
            description_meta = soup.find("meta", {"name": "description"})
            description = description_meta["content"] if description_meta else "No description available."

            jobs.append({"title": title, "url": url, "description": description})
        except Exception as e:
            jobs.append({"title": "Error Fetching", "url": url, "description": str(e)})
    
    return jobs

# Streamlit UI
st.title("📄 AI-Powered Internship Finder & Resume Evaluator")

# Ask if user has a job description
job_description_available = st.radio("Do you have a job description?", ("Yes", "No"))

if job_description_available == "Yes":
    job_description = st.text_area("Paste the Job Description Here")

    uploaded_file = st.file_uploader("Upload your Resume (PDF)", type=["pdf"], key="resume_upload")

    if uploaded_file and job_description:
        resume_text = extract_pdf_text(uploaded_file)
        st.subheader("📋 Extracted Resume Text")
        st.text_area("", resume_text, height=200)

        if st.button("🔍 Analyze Resume"):
            st.subheader("📊 ATS Analysis & Suggestions")
            ats_feedback = get_gemini_response(resume_text, job_description)

            if "error" in ats_feedback:
                st.write("⚠ Unable to parse response as JSON. Showing raw text output:")
                st.text_area("🔍 ATS Analysis", ats_feedback["raw_text"], height=300)
            else:
                st.json(ats_feedback)

            # Save to MongoDB
            resume_doc = {
                "filename": uploaded_file.name,
                "text": resume_text,
                "uploaded_at": datetime.datetime.utcnow(),
            }
            resumes_collection.insert_one(resume_doc)

else:
    # Accept user input for search keywords
    search_query = st.text_input("Enter keywords to search for internships", value="Software Engineering Internships")

    if st.button("🌍 Find Internships"):
        st.subheader("🔎 Internship Opportunities")
        jobs = search_google_jobs(search_query)

        if jobs:
            for job in jobs:
                st.markdown(f"### [{job['title']}]({job['url']})")
                st.write(job["description"])
                st.write("---")
        else:
            st.write("No internships found.")
