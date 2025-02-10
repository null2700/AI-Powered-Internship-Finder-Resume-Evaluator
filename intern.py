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
mongo_db = mongo_client["internshipdata"]
resumes_collection = mongo_db["intern"]

# Function to extract text from PDF
def extract_pdf_text(uploaded_file):
    reader = PdfReader(uploaded_file)
    return "\n".join([page.extract_text() for page in reader.pages if page.extract_text()])

# Function to get ATS analysis from Gemini AI
def get_gemini_response(resume_text, job_description):
    prompt = f"""
    Hey, act like a highly experienced ATS (Application Tracking System) with deep expertise in the tech industry, including software engineering, data science, data analysis, and big data engineering.

            Your primary task is to evaluate a candidate's resume against the given job description, ensuring the best possible guidance for resume optimization. The job market is highly competitive, so you must provide precise, actionable feedback to enhance the resume's ATS compatibility.

            Analyze the following resume text carefully and provide detailed improvement suggestions based on industry best practices and ATS optimization techniques.

            Evaluation Criteria:
            1. ATS Match Score – Assign a percentage score (%) indicating how well the resume aligns with the job description.  
            2. Missing Keywords – List any essential keywords or technical skills from the job description that are missing in the resume.  
            3. Section Formatting Issues – Identify any problems with headings, section names, and date formatting that may affect ATS parsing.  
            4. Job Title Match – Check if the candidate's job titles align with the job description. If not, suggest ways to incorporate them naturally.  
            5. Contact Information – Verify if the resume contains an address, email, and phone number, and highlight any missing details.  
            6. Education & Certifications – Identify whether the education section is properly structured and meets job requirements.  
            7. Hard Skills Matching – Compare listed skills in the resume with those in the job description and provide a skills alignment table.  
            8. Resume File Format – Check if the resume is ATS-compatible (e.g., PDF) and suggest improvements if necessary.  
            9. Overall Summary & Improvements – Provide a professional summary of the findings, along with personalized recommendations for enhancing ATS compliance.  

            Resume Text for Analysis:  
            {resume_text}  

            Job Description:  
            {job_description}  

            Expected JSON Response Format:  
            {  
            "ATS_Match_Score": ,  
            "Missing_Keywords": ["Kubernetes", "GCP", "BigQuery", "Docker"],  
            "Formatting_Issues": ["Work Experience section appears empty", "Date format should be MM/YYYY"],  
            "Job_Title_Match": "The job title 'Python Engineer' was not found in the resume. Consider adding it to the summary.",  
            "Contact_Information": {  
                "mail": "Provided",  
                "Phone": "Provided",  
                "Address": "Not Found"  
            },  
            "Education_Match": "Education information is missing. Add relevant degrees or certifications.",  
            "Hard_Skills_Match": {  
                "Resume_Skills": ["Python", "Relational Database", "Integration Testing"],  
                "JD_Skills": ["Python", "Kubernetes", "BigQuery", "Object-Oriented Programming"],  
                "Missing_Skills": ["Kubernetes", "BigQuery"]  
            },  
            "File_Format": "Resume is in an incompatible format. Convert it to an ATS-friendly PDF.",  
            "Summary": "Your resume has strong Python skills but lacks key cloud-related technologies like Kubernetes and BigQuery. Update your job title to match the description and ensure your experience section is well-structured."  
            }
    """
    
    model = genai.GenerativeModel("gemini-pro")
    response = model.generate_content(prompt)
    
    try:
        parsed_response = json.loads(response.text)
        return parsed_response  # Return valid JSON
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response", "raw_text": response.text}

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
