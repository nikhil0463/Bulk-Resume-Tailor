import os
import pandas as pd
from google import genai
from google.genai import types
from dotenv import load_dotenv
import json
import fitz # PyMuPDF for PDF reading
import re

# Load environment variables from .env file
load_dotenv()
try:
    # ----------------------------------------------------
    # GEMINI API CLIENT SETUP
    # ----------------------------------------------------
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))
except Exception as e:
    print("FATAL ERROR: Gemini Client failed to initialize.")
    print("Please ensure GEMINI_API_KEY is set correctly in your .env file.")
    exit()

# ----------------------------------------------------
# CONFIGURATION
# ----------------------------------------------------
RESUME_FILE = "resume.pdf" 
INPUT_CSV = "jobs_summary.csv"
OUTPUT_CSV = "job_matches_with_resumes1.csv"

# Columns from your input CSV
JD_COLUMN = "description" 
TITLE_COLUMN = "title"

# --- HELPER FUNCTIONS ---

def load_resume_text(pdf_path):
    """Extracts text content from a PDF file."""
    try:
        doc = fitz.open(pdf_path)
        text = ""
        for page in doc:
            text += page.get_text("text")
        return text.strip()
    except FileNotFoundError:
        print(f"Error: Resume file '{pdf_path}' not found.")
        print("Please ensure your resume is named 'resume.pdf' and is in the script directory.")
        return None
    except Exception as e:
        print(f"Error processing PDF: {e}")
        return None

def robust_json_load(text):
    """Cleans up common LLM text errors (like markdown wrappers) and parses JSON."""
    
    # 1. Strip markdown code blocks (e.g., ```json ... ```)
    text = re.sub(r"```json\s*|```", "", text, flags=re.DOTALL).strip()
    
    # 2. Attempt to load the cleaned text
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Fallback for when the JSON is still malformed
        print("Warning: Failed to parse clean JSON. Trying simple regex fix.")
        
        # Simple fix for common issue where trailing commas break JSON
        text = re.sub(r",\s*([\]}])", r"\1", text)
        
        try:
            return json.loads(text)
        except:
            print("Error: Could not fix JSON structure.")
            return None


# --- FUNCTION: AI TAILORING PROMPT (Refined for Consistency) ---
def get_tailoring_prompt(resume_text, job_title, job_description):
    """
    Constructs the prompt for the LLM to generate the tailored resume and score with strict formatting,
    incorporating all detailed instructions for keyword and impact optimization.
    """
    
    return f"""
    You are an expert ATS (Applicant Tracking System) specialist and professional resume writer.
    Your task is to rewrite the candidate's resume based on the TARGET JOB DESCRIPTION to maximize the ATS match score and appeal to human recruiters.
    
    --- CANDIDATE'S CURRENT RESUME TEXT ---
    {resume_text}
    
    --- TARGET JOB TITLE ---
    {job_title}
    
    --- TARGET JOB DESCRIPTION ---
    {job_description}
    
    --- OUTPUT REQUIREMENTS ---
    
    1.  **TAILORED_RESUME (Full Text):** Provide the complete, revised resume text.
        * **Heading Consistency:** MUST use the candidate's existing section headers EXACTLY as they appear (e.g., "Career Objective:", "TECHNICAL SKILLS:", "PROFESSIONAL EXPERIENCE:", "EDUCATION:").
        * **Summary Focus:** Rewrite the "Career Objective" to be a sharp, targeted professional summary (max 4-5 lines).
        * **Keyword Optimization:** Integrate critical hard skills (AWS, Python, Spark, ETL, Terraform) and soft skills from the job description directly into the summary and experience bullet points.
        * **Impact and Action:** Every bullet point in the "PROFESSIONAL EXPERIENCE" section MUST start with a strong action verb (e.g., Led, Developed, Optimized, Reduced). Avoid vague phrases (e.g., "Responsible for," "Worked on").
        * **Quantifiable Results:** Focus on measurable outcomes (e.g., "Reduced latency by 40%", "Managed 10 TB data").
        * **Formatting:** All experience bullet points MUST start with the **middle-dot bullet character (•)**, followed by a space. Do not use dashes (-) or asterisks (*). Ensure NO unnecessary blank lines between section contents.
        * **Final Structure:** Resume must be clean text, ready to be copied into a .doc file.
        
    2.  **ATS_MATCH_SCORE (Integer):** Provide a numerical match percentage (0-100) comparing the **tailored** resume against the job description.
    
    3.  **SCORE_REASONING (String):** Give a brief, professional explanation (2-3 sentences) for the score, emphasizing how the resume was tailored to the JD.
    
    4.  **OUTPUT ONLY JSON:** Provide the final output as a single, clean JSON object with the keys: "TAILORED_RESUME", "ATS_MATCH_SCORE", and "SCORE_REASONING".
    """


# --- MAIN EXECUTION ---

# Load the candidate's resume once
resume_text = load_resume_text(RESUME_FILE)

# print(resume_text)

if not resume_text:
    exit()

try:
    # Read the job data
    df = pd.read_csv(INPUT_CSV)
    
    if JD_COLUMN not in df.columns or TITLE_COLUMN not in df.columns:
        print(f"Error: CSV is missing required columns ('{JD_COLUMN}' and/or '{TITLE_COLUMN}').")
        exit()

    # Lists to store results
    tailored_resumes = []
    ats_scores = []
    score_reasoning = []
    
    print(f"Starting AI resume tailoring for {len(df)} jobs...")

    for index, row in df.iterrows():
        job_title = row[TITLE_COLUMN]
        job_description = row[JD_COLUMN]
        
        print(f"[{index + 1}/{len(df)}] Tailoring resume for: {job_title}")
        
        try:
            prompt = get_tailoring_prompt(resume_text, job_title, job_description)
            
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
            
            # Use the robust parser instead of simple json.loads
            parsed = robust_json_load(response.text)
            
            if parsed:
                tailored_resumes.append(parsed.get("TAILORED_RESUME", "Error: Missing Resume"))
                ats_scores.append(parsed.get("ATS_MATCH_SCORE", 0))
                score_reasoning.append(parsed.get("SCORE_REASONING", "Error: Missing Reasoning"))
            else:
                raise Exception("JSON Parsing failed after cleaning.")
            
        except Exception as e:
            print(f"---Skipping row {index}: API or JSON Error: {e}---")
            tailored_resumes.append("ERROR: API/Processing Failure")
            ats_scores.append(0)
            score_reasoning.append(f"Processing failed: {e}")

    # 4. ADD RESULTS TO DATAFRAME AND SAVE
    df["TAILORED_RESUME"] = tailored_resumes
    df["ATS_MATCH_SCORE"] = ats_scores
    df["SCORE_REASONING"] = score_reasoning

    # Save the final augmented CSV
    df.to_csv(OUTPUT_CSV, index=False)
    
    print("-" * 50)
    print(f"✅ SUCCESS! {len(df)} jobs processed.")
    print(f"Tailored resumes and ATS scores saved to: {OUTPUT_CSV}")

except FileNotFoundError:
    print(f"FATAL ERROR: Input file '{INPUT_CSV}' not found. Please check file name.")
except Exception as e:
    print(f"An unexpected error occurred during processing: {e}")
