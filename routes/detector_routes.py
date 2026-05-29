from io import BytesIO
from flask import Blueprint, render_template, request
from services.detector_service import detect_ai
import PyPDF2
import docx


detector_bp = Blueprint('detector', __name__)


def _read_uploaded_text(file_storage):
    if not file_storage or not file_storage.filename:
        return None

    filename = file_storage.filename.lower()
    content = file_storage.read()
    if not content:
        return None

    if filename.endswith('.pdf'):
        try:
            reader = PyPDF2.PdfReader(BytesIO(content))
            return '\n'.join(page.extract_text() or '' for page in reader.pages).strip()
        except Exception:
            return None

    if filename.endswith('.docx'):
        try:
            doc = docx.Document(BytesIO(content))
            return '\n'.join(paragraph.text for paragraph in doc.paragraphs).strip()
        except Exception:
            return None

    try:
        return content.decode('utf-8')
    except Exception:
        return content.decode('latin-1', errors='ignore')


@detector_bp.route('/detector', methods=['GET', 'POST'])
def detector():
    output = None
    analyzed_text = None
    orig_filename = None
    try:
        if request.method == 'POST':
            uploaded_file = request.files.get('file')
            user_text = _read_uploaded_text(uploaded_file) if uploaded_file else request.form.get('text')
            analyzed_text = user_text
            orig_filename = (uploaded_file.filename if uploaded_file and uploaded_file.filename else None)

            if user_text:
                output = detect_ai(user_text)
            else:
                output = 'Please paste text or upload a .txt, .pdf, or .docx file to analyze.'

        return render_template('tools/detector.html', output=output, analyzed_text=analyzed_text, orig_filename=orig_filename)
    except Exception as e:
        import traceback
        print('DETECTOR ROUTE ERROR:', e)
        print(traceback.format_exc())
        return render_template('errors/500.html'), 500
