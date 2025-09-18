import os
import re
import docx2txt
import pdfplumber
from flask import Flask, request, jsonify, render_template_string
from rapidfuzz import fuzz

app = Flask(__name__)

# ---------------------------
# Resume Text Extraction
# ---------------------------
def extract_text_from_file(filepath):
    text = ""
    if filepath.lower().endswith(".pdf"):
        with pdfplumber.open(filepath) as pdf:
            for page in pdf.pages:
                text += page.extract_text() or ""
    elif filepath.lower().endswith(".docx"):
        text = docx2txt.process(filepath)
    elif filepath.lower().endswith(".txt"):
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            text = f.read()
    return text

# ---------------------------
# Resume Parsing
# ---------------------------
def parse_resume(text):
    # Skill dictionary
    skill_dict = [
        "python", "java", "sql", "excel", "tableau", "power bi", "statistics",
        "machine learning", "flask", "django", "aws", "azure", "docker", "react"
    ]
    found_skills = [s for s in skill_dict if s.lower() in text.lower()]
    exp_years = re.findall(r"(\d+)\+?\s+years", text.lower())
    exp_years = max([int(y) for y in exp_years], default=0)
    return {"skills": found_skills, "experience_years": exp_years}

# ---------------------------
# JD Matching
# ---------------------------
def match_resume_with_jd(resume_data, jd_text):
    results = []
    if not jd_text:
        return results

    jd_tokens = re.findall(r"\w+", jd_text.lower())
    jd_skills = list(set(jd_tokens))

    for rskill in resume_data.get("skills", []):
        best_score = 0
        best_match = ""
        for jskill in jd_skills:
            score = fuzz.partial_ratio(rskill.lower(), jskill)
            if score > best_score:
                best_score = score
                best_match = jskill
        if best_score > 60:
            results.append({"skill": rskill, "type": best_match, "score": best_score})
    return results

# ---------------------------
# Scoring (Always ≥85 if any match)
# ---------------------------
def compute_score(resume_data, jd_matches, jd_text):
    if not jd_text:
        return 90.0

    if jd_matches:
        avg_skill_score = sum([m["score"] for m in jd_matches]) / len(jd_matches)
    else:
        avg_skill_score = 0

    exp_score = min(resume_data.get("experience_years", 0) * 10, 100)
    overall = 0.7 * avg_skill_score + 0.3 * exp_score

    if jd_matches and overall < 85:
        overall = 85 + (overall / 100) * 15
    return overall

# ---------------------------
# UI Template
# ---------------------------
INDEX_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>ResuScan</title>
  <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
  <style>
    body { background: linear-gradient(135deg,#74ebd5,#ACB6E5); height:100vh; display:flex; align-items:center; justify-content:center; }
    .card { border-radius:20px; box-shadow:0 4px 20px rgba(0,0,0,.2); padding:40px; text-align:center; max-width:600px; width:100%; }
    .score { font-size:60px; font-weight:bold; margin:20px 0; }
    .btn-primary { border-radius:30px; font-size:18px; padding:12px; }
  </style>
</head>
<body>
  <div class="card">
    <h1 class="fw-bold mb-4">ResuScan</h1>
    <form id="uploadForm" method="post" enctype="multipart/form-data" action="/scan">
      <div class="mb-3">
        <input type="file" class="form-control" name="resume" required>
      </div>
      <div class="mb-3">
        <textarea class="form-control" name="jobdesc" rows="4" placeholder="Paste Job Description here..."></textarea>
      </div>
      <button type="submit" class="btn btn-primary w-100">Get Resume Score</button>
    </form>
    <div id="result" class="mt-4"></div>
  </div>

  <script>
    const form = document.getElementById('uploadForm');
    const resultEl = document.getElementById('result');

    form.addEventListener('submit', async (e) => {
      e.preventDefault();
      resultEl.innerHTML = '<p class="text-muted">Scanning...</p>';
      const fd = new FormData(form);
      const resp = await fetch('/scan', { method: 'POST', body: fd });
      const json = await resp.json();
      if (json.error) {
        resultEl.innerHTML = '<p class="text-danger">Error: '+json.error+'</p>';
        return;
      }
      resultEl.innerHTML = `<div class="score text-success">${json.score.toFixed(1)} / 100</div>`;
    });
  </script>
</body>
</html>
"""

# ---------------------------
# Flask Routes
# ---------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML)

@app.route("/scan", methods=["POST"])
def scan():
    if "resume" not in request.files:
        return jsonify({"error": "No resume uploaded"}), 400

    file = request.files["resume"]
    jd_text = request.form.get("jobdesc", "")

    filepath = os.path.join("uploads", file.filename)
    os.makedirs("uploads", exist_ok=True)
    file.save(filepath)

    resume_text = extract_text_from_file(filepath)
    resume_data = parse_resume(resume_text)
    jd_matches = match_resume_with_jd(resume_data, jd_text)
    score = compute_score(resume_data, jd_matches, jd_text)

    return jsonify({"score": score})

if __name__ == "__main__":
    app.run(debug=True)
