from flask import Blueprint, g, render_template, request
from services.detector_service import detect_ai
from services.gemini_service import GeminiGenerationError
from services.upload_text import UploadTextError, check_text_length, read_uploaded_text


detector_bp = Blueprint('detector', __name__)


@detector_bp.route('/detector', methods=['GET', 'POST'])
def detector():
    output = None
    error = None
    analyzed_text = None
    orig_filename = None
    status = 200
    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        try:
            user_text = (
                read_uploaded_text(uploaded_file, allow_docx=True)
                if uploaded_file else check_text_length(request.form.get('text'))
            )
        except UploadTextError as exc:
            user_text = None
            error, status = str(exc), 422
        analyzed_text = user_text
        orig_filename = (uploaded_file.filename if uploaded_file and uploaded_file.filename else None)

        if error is None and user_text and user_text.strip():
            try:
                output = detect_ai(user_text.strip())
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        elif error is None:
            error = 'Please paste text or upload a .txt, .pdf, or .docx file to analyze.'

    return render_template('tools/detector.html', output=output, error=error,
                           analyzed_text=analyzed_text, orig_filename=orig_filename), status
