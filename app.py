import os
from flask import Flask, request, render_template_string, flash, redirect
import docx
import PyPDF2
import requests
from io import BytesIO

app = Flask(__name__)
app.secret_key = b'_5#y2L"F4Q8z\n\xec]/'

ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}

# Your Hugging Face API Token (replace with your own)
HUGGINGFACE_API_TOKEN = 'Enter Your_API_KEY'
HUGGINGFACE_API_URL = 'https://api-inference.huggingface.co/models/facebook/bart-large-cnn'

# HTML Template with Summary Length Dropdown
HTML = """
<!doctype html>
<html lang="en">
<head>
  <title>GPT Document Summarizer</title>
  <style>
    body { font-family: Arial, sans-serif; background-color: #f4f7f8; color: #2c3e50; margin: 40px; }
    h1 { color: #34495e; }
    label, select, input, button { font-size: 1.1em; margin-top: 10px; }
    .summary-box { background-color: #ecf0f1; border-radius: 8px; padding: 15px; max-width: 700px; margin-top: 20px; }
    ul { margin-top: 0; }
    .error { color: red; margin-top: 10px; }
  </style>
</head>
<body>
  <h1>Upload your document (.txt, .pdf, .docx) for summarization</h1>
  <form method="post" enctype="multipart/form-data">
    <label for="length">Summary length:</label>
    <select name="length">
      <option value="short">Short</option>
      <option value="medium" selected>Medium</option>
      <option value="long">Long</option>
    </select>
    <br><br>
    <input type="file" name="file" accept=".txt,.pdf,.docx" required>
    <button type="submit">Summarize</button>
  </form>
  {% with messages = get_flashed_messages() %}
    {% if messages %}
      <div class="error">
        <ul>
          {% for message in messages %}
            <li>{{ message }}</li>
          {% endfor %}
        </ul>
      </div>
    {% endif %}
  {% endwith %}

  {% if summary %}
    <h2>Summary:</h2>
    <div class="summary-box">
      {{ summary|safe }}
    </div>
  {% endif %}
</body>
</html>
"""

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_text_txt(file_stream):
    return file_stream.read().decode('utf-8', errors='ignore')

def extract_text_pdf(file_stream):
    reader = PyPDF2.PdfReader(file_stream)
    text = ''
    for page in reader.pages:
        text += page.extract_text() or ''
    return text

def extract_text_docx(file_stream):
    document = docx.Document(file_stream)
    return '\n'.join([para.text for para in document.paragraphs])

def call_huggingface_summarization(text, length='medium'):
    # Length parameters for different summary types
    if length == 'short':
        min_len, max_len = 50, 150
    elif length == 'long':
        min_len, max_len = 200, 700
    else:  # medium
        min_len, max_len = 100, 300

    headers = {
        "Authorization": f"Bearer {HUGGINGFACE_API_TOKEN}"
    }
    payload = {
        "inputs": text,
        "parameters": {
            "min_length": min_len,
            "max_length": max_len,
            "do_sample": False
        },
        "options": {"wait_for_model": True}
    }
    response = requests.post(HUGGINGFACE_API_URL, headers=headers, json=payload)

    if response.status_code == 200:
        data = response.json()
        if isinstance(data, list) and 'summary_text' in data[0]:
            return data[0]['summary_text']
        else:
            return "Error: Unexpected response format from summarization API."
    else:
        return f"Error: API request failed with status code {response.status_code}. Response: {response.text}"

@app.route('/', methods=['GET', 'POST'])
def home():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part in request.')
            return redirect(request.url)

        file = request.files['file']
        summary_length = request.form.get('length', 'medium')

        if file.filename == '':
            flash('No file selected.')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            ext = file.filename.rsplit('.', 1)[1].lower()
            try:
                if ext == 'txt':
                    text = extract_text_txt(file.stream)
                elif ext == 'pdf':
                    file_bytes = BytesIO(file.read())
                    text = extract_text_pdf(file_bytes)
                elif ext == 'docx':
                    text = extract_text_docx(file.stream)
                else:
                    flash('Unsupported file type.')
                    return redirect(request.url)
            except Exception as e:
                flash(f'Error extracting text: {str(e)}')
                return redirect(request.url)

            if not text.strip():
                flash('Could not extract any text from the uploaded file.')
                return redirect(request.url)

            # Trim input text to avoid token overflow (~4096 tokens)
            MAX_CHARS = 3500
            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + '...'

            summary = call_huggingface_summarization(text, summary_length)

            # Format summary
            sentences = [s.strip() for s in summary.split('.') if len(s.strip()) > 30]
            if len(sentences) > 1:
                bullet_points = '<ul>' + ''.join(f'<li>{s}.</li>' for s in sentences) + '</ul>'
                formatted_summary = bullet_points
            else:
                formatted_summary = f'<p>{summary}</p>'

            return render_template_string(HTML, summary=formatted_summary)

        else:
            flash('Allowed file types: txt, pdf, docx.')
            return redirect(request.url)

    return render_template_string(HTML)

if __name__ == '__main__':
    app.run(debug=True)

