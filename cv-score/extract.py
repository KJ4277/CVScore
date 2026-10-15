import pdfplumber
import docx

def extract_text(path: str) -> str:
    #Return the plain text of a file.
    lower = path.lower()
    if lower.endswith(".pdf"):
        with pdfplumber.open(path) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages)
    if lower.endswith(".docx"):
        return "\n".join(p.text for p in docx.Document(path).paragraphs)
    if lower.endswith(".txt"):
        with open(path, encoding="utf-8") as f:
            return f.read()
    raise ValueError("Please use a PDF, DOCX or TXT file")