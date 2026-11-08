from io import BytesIO
from flask import Blueprint, render_template, request, send_file
from werkzeug.utils import secure_filename
from services.humanizer_service import DocumentHumanizationError, humanize_docx, humanize_text
import PyPDF2


humanizer_bp = Blueprint('humanizer', __name__)


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

    try:
        return content.decode('utf-8')
    except Exception:
        return content.decode('latin-1', errors='ignore')


@humanizer_bp.route('/humanizer', methods=['GET', 'POST'])
def humanizer():
    output = None
    orig_filename = None

    if request.method == 'POST':
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename.lower().endswith('.docx'):
            try:
                processed = humanize_docx(
                    uploaded_file.read(),
                    request.form.get('education_level', 'Primary school'),
                )
            except DocumentHumanizationError as exc:
                return render_template('tools/humanizer.html', output=str(exc)), 422
            safe_name = secure_filename(uploaded_file.filename) or 'document.docx'
            download_name = f'{safe_name[:-5]}_humanized.docx'
            return send_file(
                processed,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )
        user_text = _read_uploaded_text(uploaded_file) if uploaded_file else request.form.get('text')
        education_level = request.form.get('education_level', 'Primary school')
        # preserve original filename when available (from upload or redirected form)
        orig_filename = (uploaded_file.filename if uploaded_file and uploaded_file.filename else None)

        if user_text and user_text.strip():
            output = humanize_text(user_text.strip(), education_level)
        else:
            output = 'Please paste text or upload a .txt, .pdf, or .docx file to humanize.'

    return render_template('tools/humanizer.html', output=output, orig_filename=orig_filename)


@humanizer_bp.route('/humanizer/download', methods=['POST'])
def humanizer_download():
    # Pasted text and text extracted from PDFs are plain text downloads.
    content = request.form.get('download_content')

    if not content:
        return render_template('tools/humanizer.html', output='Nothing to download.' )

    filename = secure_filename(request.form.get('download_filename') or '')
    if not filename.lower().endswith('.txt'):
        filename = 'humanized.txt'
    bio = BytesIO()
    bio.write((content or '').encode('utf-8'))
    bio.seek(0)
    return send_file(bio, as_attachment=True, download_name=filename, mimetype='text/plain')
