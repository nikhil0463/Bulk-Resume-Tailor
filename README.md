# Bulk Resume Tailor

This project helps you automatically tailor a single resume to many job descriptions using a large language model (Google Gemini via `google-genai`). It produces a tailored resume for each job and an ATS-style match score.

What you'll find here
---------------------
- `AI_Resume_Optimiser.py` — Generates a single-page, ATS-optimized resume per job and saves results to `job_matches_with_resumes.csv`.
- `Bulk_Resume_Tailor.py` — The main, more robust script that reads `jobs_summary.csv`, calls the LLM, and saves tailored resumes and scores to `job_matches_with_resumes.csv`.
- `Builk_Resume_Tailor_ModPmt.py` — A variant with a modified prompt and a helper to clean up LLM JSON output. (Filename has a small typo: "Builk_").
- `jobs_summary.csv` — The input CSV with job postings (needs at least a `description` column; `title` is helpful).
- `resume.pdf` — Your resume PDF used as the source for tailoring.

How it works (brief)
--------------------
For each job in `jobs_summary.csv` the scripts:

1. Extract text from `resume.pdf` using PyMuPDF (`fitz`).
2. Build a tailored prompt that includes the job description.
3. Call the Gemini model to get a JSON response containing `TAILORED_RESUME`, `ATS_MATCH_SCORE`, and `SCORE_REASONING`.
4. Save everything back to a CSV file for review.

Quick setup
-----------
You'll need Python 3.9+ and a Gemini API key saved in a local `.env` file as `GEMINI_API_KEY`. Install the essentials with:

```bash
pip install pandas python-dotenv PyMuPDF google-genai
```

To use a virtual environment (recommended):

```bash
python -m venv .venv
# Activate the virtual environment:
# Windows (cmd): .\.venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt  # optional, if you provide requirements
```

Configuration
-------------
Create an `.env` file in the project root with:

```text
GEMINI_API_KEY=your_api_key_here
```

Make sure `resume.pdf` and `jobs_summary.csv` are in the same folder as the scripts (or update the paths inside the scripts).

What the input CSV should look like
----------------------------------
- The CSV must include a `description` column (the full job description). A `title` column is recommended so the script can show progress.
- Other columns (company, location, etc.) are preserved.

Run the scripts (command line)
-----------------------------
From the project root run:

```bash
# Main robust script
python Bulk_Resume_Tailor.py

# Single-page optimiser
python AI_Resume_Optimiser.py

# Variant with modified prompt/parsing
python Builk_Resume_Tailor_ModPmt.py
```

What the scripts produce
------------------------
- `job_matches_with_resumes.csv` — produced by `AI_Resume_Optimiser.py` and `Bulk_Resume_Tailor.py`. This CSV includes the new columns `TAILORED_RESUME`, `ATS_MATCH_SCORE`, and `SCORE_REASONING`.
- `job_matches_with_resumes1.csv` — produced by `Builk_Resume_Tailor_ModPmt.py` (same structure).

Notes about the outputs
-----------------------
- `TAILORED_RESUME`: Full tailored resume text from the model. It may be plain text you can paste into a Word doc.
- `ATS_MATCH_SCORE`: Integer 0–100 estimating the ATS fit.
- `SCORE_REASONING`: A short explanation of the score and remaining gaps.

Common issues and tips
----------------------
- Missing `GEMINI_API_KEY`: Create the `.env` file — the scripts will stop and tell you if the key is missing.
- PDF text extraction: If your resume PDF is a scanned image, text extraction will fail or return gibberish. Use a selectable-text PDF.
- LLM JSON parsing: If the model returns non-JSON wrappers (markdown, stray text), `Builk_Resume_Tailor_ModPmt.py` includes a `robust_json_load` helper to try to clean and parse it.
- Rate limits and API errors: These scripts call the API for every job row. For large datasets add batching, delays, or exponential backoff.

Privacy note
------------
The scripts send your resume and job descriptions to the Gemini API. Only run this on data you are comfortable sharing with the provider.

Small ideas to improve
---------------------
- Add retries and exponential backoff for API calls.
- Add optional concurrency or batching while respecting rate limits.
- Save tailored resumes as separate text files or PDFs.
- Add simple unit tests for JSON parsing helpers.

If you'd like, I can also add a `requirements.txt` and a `.env.example` file to make setup even easier — tell me which and I'll add them.

