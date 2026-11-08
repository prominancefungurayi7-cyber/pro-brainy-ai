import base64
import hashlib
import json
import logging
from queue import Empty, Queue
from threading import BoundedSemaphore, Event, Thread
from io import BytesIO
from flask import Blueprint, Response, flash, g, redirect, render_template, request, send_file, stream_with_context, url_for
from flask_login import current_user, login_required
from werkzeug.utils import secure_filename
from services.humanizer_service import (
    DocumentHumanizationError, build_voice_profile, humanize_docx,
    humanize_docx_progress, humanize_text,
)
from models.user import UserVoiceProfile, db
from services.upload_text import UploadTextError, check_text_length, read_uploaded_text


humanizer_bp = Blueprint('humanizer', __name__)
STREAM_KEEPALIVE_SECONDS = 15
# Gunicorn has two request threads on Render. A document job may occupy one
# stream for minutes, so always leave a thread available for health and login.
_DOCX_JOB_SLOTS = BoundedSemaphore(1)


def _event(payload):
    return 'data: ' + json.dumps(payload, separators=(',', ':')) + '\n\n'


def _stream_docx(content, download_name, voice_sample=None, voice_profile=None,
                 thorough=False):
    if not _DOCX_JOB_SLOTS.acquire(blocking=False):
        yield _event({'type': 'error', 'message': 'Document processing is busy. Please try again shortly.'})
        return
    updates = Queue()
    cancelled = Event()

    def process_document():
        try:
            for update in humanize_docx_progress(content, voice_sample, voice_profile, thorough):
                if cancelled.is_set():
                    break
                updates.put(update)
        except Exception as exc:
            if not cancelled.is_set():
                updates.put(exc)
        finally:
            updates.put(None)
            _DOCX_JOB_SLOTS.release()

    # Gemini can spend longer than a proxy's idle timeout on one batch.
    # Keep the response active while that work runs in a separate thread.
    try:
        Thread(target=process_document, daemon=True, name='docx-humanizer').start()
    except Exception:
        _DOCX_JOB_SLOTS.release()
        raise
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
            file_bytes = output.getbuffer()
            yield _event({
                'type': 'file-start', 'filename': download_name,
                'size': len(file_bytes), 'sha256': hashlib.sha256(file_bytes).hexdigest(),
            })
            del file_bytes
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
    finally:
        cancelled.set()


@humanizer_bp.route('/humanizer', methods=['GET', 'POST'])
def humanizer():
    output = None
    orig_filename = None
    error = None
    saved_voice = db.session.get(UserVoiceProfile, current_user.id)
    voice_profile = saved_voice.style_guide if saved_voice else None

    if request.method == 'POST':
        voice_sample = (request.form.get('voice_sample') or '').strip()[:1500]
        thorough = request.form.get('quality') == 'thorough'
        uploaded_file = request.files.get('file')
        if uploaded_file and uploaded_file.filename.lower().endswith('.docx'):
            content = uploaded_file.read()
            safe_name = secure_filename(uploaded_file.filename) or 'document.docx'
            download_name = f'{safe_name[:-5]}_humanized.docx'
            if 'text/event-stream' in request.headers.get('Accept', ''):
                g.tool_streaming = True
                response = Response(
                    stream_with_context(_stream_docx(content, download_name,
                                                     voice_sample, voice_profile, thorough)),
                    mimetype='text/event-stream',
                )
                response.headers['Cache-Control'] = 'no-store'
                response.headers['X-Accel-Buffering'] = 'no'
                response.headers['X-Content-Type-Options'] = 'nosniff'
                return response
            if not _DOCX_JOB_SLOTS.acquire(blocking=False):
                return render_template(
                    'tools/humanizer.html',
                    error='Document processing is busy. Please try again shortly.',
                    voice_profile=voice_profile,
                ), 429
            try:
                processed = humanize_docx(content, voice_sample, voice_profile, thorough)
            except DocumentHumanizationError as exc:
                return render_template('tools/humanizer.html', error=str(exc),
                                       voice_profile=voice_profile), 422
            finally:
                _DOCX_JOB_SLOTS.release()
            g.tool_generated = True
            return send_file(
                processed,
                as_attachment=True,
                download_name=download_name,
                mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            )
        try:
            user_text = (
                read_uploaded_text(uploaded_file)
                if uploaded_file else check_text_length(request.form.get('text'))
            )
        except UploadTextError as exc:
            user_text = None
            error = str(exc)
        # preserve original filename when available (from upload or redirected form)
        orig_filename = (uploaded_file.filename if uploaded_file and uploaded_file.filename else None)

        if error is None and user_text and user_text.strip():
            try:
                output = humanize_text(user_text.strip(), voice_sample, voice_profile, thorough)
                g.tool_generated = True
            except DocumentHumanizationError as exc:
                error = str(exc)
        elif error is None:
            error = 'Please paste text or upload a .txt, .pdf, or .docx file to humanize.'

    return render_template('tools/humanizer.html', output=output, error=error,
                           orig_filename=orig_filename, voice_profile=voice_profile), (422 if error else 200)


@humanizer_bp.route('/humanizer/voice', methods=['POST'])
@login_required
def save_voice():
    try:
        style_guide = build_voice_profile(request.form.get('writing_samples'))
    except DocumentHumanizationError as exc:
        flash(str(exc), 'danger')
        return redirect(url_for('humanizer.humanizer'))
    profile = db.session.get(UserVoiceProfile, current_user.id)
    if profile is None:
        db.session.add(UserVoiceProfile(user_id=current_user.id, style_guide=style_guide))
    else:
        profile.style_guide = style_guide
    db.session.commit()
    g.tool_generated = True
    flash('Your writing voice has been saved. The original samples were not stored.', 'success')
    return redirect(url_for('humanizer.humanizer'))


@humanizer_bp.route('/humanizer/voice/delete', methods=['POST'])
@login_required
def delete_voice():
    profile = db.session.get(UserVoiceProfile, current_user.id)
    if profile:
        db.session.delete(profile)
        db.session.commit()
    flash('Your saved writing voice was removed.', 'success')
    return redirect(url_for('humanizer.humanizer'))


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
