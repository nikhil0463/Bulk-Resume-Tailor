import os
import pandas as pd
import fitz # PyMuPDF for PDF reading
from google import genai
from google.genai import types
import json
from dotenv import load_dotenv
import csv

# --- Configuration ---
load_dotenv()

INPUT_CSV = "jobs_summary.csv" 
OUTPUT_CSV = "job_matches_with_resumes.csv" # Renamed output file for clarity
RESUME_FILE = "resume.pdf"  # PATH TO YOUR RESUME FILE
JD_COLUMN = 'description'   # Job description column name

# --- Gemini API Setup ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found. Please set it in your .env file.")

try:
    client = genai.Client() 
except Exception as e:
    print(f"Error initializing Gemini Client: {e}")
    exit()

# --- FUNCTION: LOAD RESUME ---
def load_resume_text(pdf_path):
    """Extracts text from a local PDF file using PyMuPDF (fitz)."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
        return text.strip()
    except FileNotFoundError:
        raise FileNotFoundError(f"Resume file not found at: {pdf_path}")
    except Exception as e:
        raise Exception(f"Error reading PDF resume: {e}")

# --- LLM Prompt Function (Updated for Full Resume Generation and Scoring) ---
def get_tailoring_prompt(resume_text, job_description):
    """
    Constructs the prompt for Gemini to generate a tailored resume and score it.
    """
    return f"""
    You are an Applicant Tracking System (ATS) optimization expert and professional resume builder. 
    Your goal is to tailor the candidate's existing resume to maximize its match score for the provided Job Description (JD).
    
    Instructions:
    1. **Tailor the Resume:** Based on the current resume text, revise the Professional Summary, Skills, and Experience sections to incorporate exact keywords, tools, and quantified achievements from the JD. The output must be the **full, single-page resume text**, ready for submission. Preserve the original format and structure as much as possible, but update the content aggressively for relevance.
    2. **Generate ATS Score:** Calculate an ATS Match Score (0-100) based on keyword frequency, relevance, and formatting (assume simple text formatting passes).
    3. **Provide Reasoning:** Give a brief explanation of the score and the top 2-3 gaps remaining.

    CANDIDATE'S CURRENT RESUME TEXT (Maintain this simple text format):
    ---
    {resume_text}
    ---

    TARGET JOB DESCRIPTION:
    ---
    {job_description}
    ---
    
    Respond in JSON format with keys: "TAILORED_RESUME", "ATS_MATCH_SCORE" (integer), and "SCORE_REASONING".
    """

# --- Main Processing Logic ---
def process_jobs_with_ai(df, resume_text):
    
    if JD_COLUMN not in df.columns:
        raise ValueError(f"DataFrame is missing the required job description column: '{JD_COLUMN}'.")
        
    extracted_data_list = []
    
    for index, row in df.iterrows():
        job_description = row[JD_COLUMN] 
        job_title = row.get('title', 'N/A')
        job_company = row.get('company', 'N/A')
        
        print(f"[{index + 1}/{len(df)}] Tailoring resume for: {job_title} at {job_company}")
        
        try:
            prompt = get_tailoring_prompt(resume_text, job_description)
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[prompt],
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema={
                        "type": "object",
                        "properties": {
                            "TAILORED_RESUME": {"type": "string"},
                            "ATS_MATCH_SCORE": {"type": "integer"},
                            "SCORE_REASONING": {"type": "string"}
                        },
                        "required": ["TAILORED_RESUME", "ATS_MATCH_SCORE", "SCORE_REASONING"]
                    }
                ),
            )
            
            json_response = json.loads(response.text)
            extracted_data_list.append(json_response)
            
        except Exception as e:
            print(f"Skipping row {index}: Gemini API call failed or JSON parsing error: {e}")
            # Append error data to maintain DataFrame alignment
            extracted_data_list.append({
                "TAILORED_RESUME": "AI Generation Failed",
                "ATS_MATCH_SCORE": 0,
                "SCORE_REASONING": f"Error: {e}"
            })
            
    return extracted_data_list

# ----------------------------------------------------
# EXECUTION
# ----------------------------------------------------

try:
    # 1. Load data and resume text
    resume_text = load_resume_text(RESUME_FILE) 
    df = pd.read_csv(INPUT_CSV)
    
    # 2. Run the AI processing
    ai_results = process_jobs_with_ai(df, resume_text)
    
    # 3. Create a DataFrame from the list of extracted JSONs
    ai_df = pd.DataFrame(ai_results)
    
    # 4. Merge the new AI columns back into the original DataFrame 
    # Drop the original long description column
    df_final = pd.concat([df.drop(columns=[JD_COLUMN], errors='ignore'), ai_df], axis=1)
    
    # 5. Save the final, augmented CSV
    df_final.to_csv(OUTPUT_CSV, index=False, quoting=csv.QUOTE_NONNUMERIC, escapechar="\\")
    
    print("-" * 50)
    print(f"AI Tailoring complete! Results saved to {OUTPUT_CSV}")
    print("New Columns Added: TAILORED_RESUME, ATS_MATCH_SCORE, SCORE_REASONING")
    print("\n--- Preview of ATS Scores ---")
    print(df_final[['title', 'company', 'ATS_MATCH_SCORE', 'SCORE_REASONING']].head())

except FileNotFoundError:
    print(f"FATAL ERROR: Ensure '{INPUT_CSV}' and '{RESUME_FILE}' are in the current directory.")
except ValueError as e:
    print(f"Configuration Error: {e}")
except Exception as e:
    print(f"An unexpected error occurred during processing: {e}")
