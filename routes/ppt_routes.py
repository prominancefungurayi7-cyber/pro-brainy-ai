from flask import Blueprint, g, jsonify, render_template, request, send_file
from services.gemini_service import GeminiGenerationError
from services.ppt_service import build_presentation_pptx, generate_presentation
from werkzeug.utils import secure_filename

ppt_bp = Blueprint('ppt', __name__)


@ppt_bp.route('/ppt/download', methods=['POST'])
def ppt_download():
    topic = (request.form.get('topic') or '').strip()
    audience = (request.form.get('audience') or '').strip()
    detail_level = (request.form.get('detail_level') or 'medium').strip()
    try:
        slide_count = int(request.form.get('slides') or 5)
        if not 3 <= slide_count <= 12:
            raise ValueError('Choose 3 to 12 slides.')
        output = build_presentation_pptx(
            topic, audience, slide_count, detail_level,
            include_diagrams=request.form.get('include_diagrams') == 'on',
        )
    except (ValueError, GeminiGenerationError) as exc:
        status = 503 if isinstance(exc, GeminiGenerationError) else 422
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'error': str(exc)}), status
        return render_template('tools/ppt_generator.html', error=str(exc)), status
    name = secure_filename(topic).strip('_-')[:70] or 'presentation'
    g.tool_generated = True
    return send_file(
        output, as_attachment=True, download_name=f'{name}.pptx',
        mimetype='application/vnd.openxmlformats-officedocument.presentationml.presentation',
    )

@ppt_bp.route('/ppt', methods=['GET', 'POST'])
def ppt_generator():
    output = None
    error = None
    status = 200
    if request.method == 'POST':
        topic = (request.form.get('topic') or '').strip()
        audience = request.form.get('audience')
        slides = request.form.get('slides', 5)
        try:
            slides = max(3, min(20, int(slides)))
        except (ValueError, TypeError):
            slides = 5

        if topic:
            try:
                output = generate_presentation(topic, audience, slides)
                g.tool_generated = True
            except GeminiGenerationError as exc:
                error, status = str(exc), 503
        else:
            error = 'Please enter a presentation topic.'

    return render_template('tools/ppt_generator.html', output=output, error=error), status
