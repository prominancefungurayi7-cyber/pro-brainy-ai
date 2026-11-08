import base64
import json
import logging
from queue import Empty, Queue
from threading import Thread
from io import BytesIO
from flask import Blueprint, Response, render_template, request, send_file, stream_with_context
from werkzeug.utils import secure_filename
from services.humanizer_service import (
    DocumentHumanizationError, humanize_docx, humanize_docx_progress, humanize_text,
)
import PyPDF2


humanizer_bp = Blueprint('humanizer', __name__)
STREAM_KEEPALIVE_SECONDS = 15


def _event(payload):
    return 'data: ' + json.dumps(payload, separators=(',', ':')) + '\n\n'


def _stream_docx(content, download_name, voice_sample=None):
    updates = Queue()

    def process_document():
        try:
            for update in humanize_docx_progress(content, voice_sample):
                updates.put(update)
        except Exception as exc:
            updates.put(exc)
        finally:
            updates.put(None)

    # Gemini can spend longer than a proxy's idle timeout on one batch.
    # Keep the response active while that work runs in a separate thread.
    Thread(target=process_document, daemon=True, name='docx-humanizer').start()
    try:
        while True:
            try:
                update = updates.get(timeout=STREAM_KEEPALIVE_SECONDS)
            except Empty:
                yield ': keep-alive\n\n'
                continue
            if update is None:
                break
            if isinstance(update, Exception):
                raise update
            if update['type'] == 'progress':
                yield _event(update)
                continue
            output = update['file']
            yield _event({'type': 'file-start', 'filename': download_name})
            while chunk := output.read(48 * 1024):
                yield _event({
                    'type': 'file-chunk',
                    'data': base64.b64encode(chunk).decode('ascii'),
                })
            yield _event({'type': 'complete', 'percent': 100})
    except DocumentHumanizationError as exc:
        yield _event({'type': 'error', 'message': str(exc)})
    except Exception:
        logging.getLogger(__name__).exception('Document humanization stream failed')
        yield _event({'type': 'error', 'message': 'The document could not be completed. Please try again.'})


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
        voice_sample = (request.form.get('voice_sample') or '').strip()[:1500]
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename.lower().endswith('.docx'):
            content = uploaded_file.read()
            safe_name = secure_filename(uploaded_file.filename) or 'document.docx'
            download_name = f'{safe_name[:-5]}_humanized.docx'
            if 'text/event-stream' in request.headers.get('Accept', ''):
                response = Response(
                    stream_with_context(_stream_docx(content, download_name, voice_sample)),
                    mimetype='text/event-stream',
                )
                response.headers['Cache-Control'] = 'no-store'
                response.headers['X-Accel-Buffering'] = 'no'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                return response
            try:
                processed = humanize_docx(content, voice_sample)
            except DocumentHumanizationError as exc:
                return render_template('tools/humanizer.html', output=str(exc)), 422
            return send_file(
                processed,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )
        user_text = _read_uploaded_text(uploaded_file) if uploaded_file else request.form.get('text')
        # preserve original filename when available (from upload or redirected form)
        orig_filename = (uploaded_file.filename if uploaded_file and uploaded_file.filename else None)

        if user_text and user_text.strip():
            output = humanize_text(user_text.strip(), voice_sample)
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
