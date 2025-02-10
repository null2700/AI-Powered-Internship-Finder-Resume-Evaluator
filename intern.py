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
genai.configure(api_key="AIzaSyCcETag2wmwbqXDInoC1WVH7bsfqUK1SKE")

# Initialize MongoDB
mongo_client = MongoClient("mongodb://localhost:27017/")
mongo_db = mongo_client["resume_db"]
resumes_collection = mongo_db["resumes"]
logs_collection = mongo_db["logs"]

# Function to extract text from PDF
def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

# Function to get ATS analysis from Gemini AI
def get_gemini_response(resume_text, job_description):
    prompt = f"""
    Hey, act like a highly experienced ATS (Application Tracking System) with deep expertise.
    Analyze the following resume against this job description and provide ATS feedback.

    Resume Text: {resume_text}
    Job Description: {job_description}
    
    Expected JSON Response Format:
    {{
        "ATS_Match_Score": "85%",
        "Missing_Keywords": ["Kubernetes", "GCP"],
        "Summary": "Your resume lacks key skills such as Kubernetes."
    }}
    """
    
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    
    try:
        return json.loads(response.text)  # Convert AI response to JSON
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response", "raw_text": response.text}

# Function to search for internships with metadata
def search_google_jobs(query):
    jobs = []
    for url in search(query, num_results=10):
        try:
            response = requests.get(url, timeout=5)
            soup = BeautifulSoup(response.text, "html.parser")
            
            title = soup.title.string if soup.title else "No Title Found"
            description = soup.find("meta", {"name": "description"})
            description = description["content"] if description else "No description available."

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

