"""Bounded Wikimedia Commons diagram search for generated presentations.

Only image thumbnails returned by the Commons API are fetched. Missing or
uncertain license/relevance information produces no image, letting the
presentation renderer use its own editable visual instead.
"""

import html
import json
import re
from dataclasses import dataclass
from io import BytesIO
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from PIL import Image, UnidentifiedImageError


API_ENDPOINT = 'https://commons.wikimedia.org/w/api.php'
API_MAX_BYTES = 256_000
IMAGE_MAX_BYTES = 3_000_000
IMAGE_MAX_PIXELS = 8_000_000
REQUEST_TIMEOUT_SECONDS = 5
SEARCH_RESULTS = 8
MAX_IMAGE_DOWNLOADS = 2
USER_AGENT = (
    'ProBrainyAI-PresentationBot/1.0 '
    '(https://pro-brainy-ai-toolkit-vgvz.onrender.com/)'
)

_LICENSE_RE = re.compile(r'^CC BY(?:-SA)? [234]\.0$', re.IGNORECASE)
_STOP_WORDS = {'and', 'the', 'for', 'with', 'from', 'into', 'diagram', 'chart',
               'process', 'illustration', 'overview', 'visual', 'showing'}


@dataclass(frozen=True)
class DiagramImage:
    image_bytes: bytes
    title: str
    attribution: str
    license: str
    license_url: str
    source_url: str


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


_OPENER = build_opener(_NoRedirect)


def _plain_text(value, limit=180):
    """Reduce Commons HTML metadata to one safe line for slide credits."""
    if not isinstance(value, str):
        return ''
    without_tags = re.sub(r'<[^>]*>', ' ', value)
    return ' '.join(html.unescape(without_tags).split())[:limit]


def _metadata_value(metadata, key):
    entry = metadata.get(key, {}) if isinstance(metadata, dict) else {}
    return _plain_text(entry.get('value', '')) if isinstance(entry, dict) else ''


def _allowed_media_url(url):
    if not isinstance(url, str):
        return False
    parts = urlsplit(url)
    path = unquote(parts.path)
    return bool(
        parts.scheme == 'https'
        and parts.netloc in {'upload.wikimedia.org', 'thumb.wikimedia.org'}
        and not parts.username and not parts.password
        and not parts.query and not parts.fragment
        and path.startswith('/wikipedia/commons/')
        and all(segment not in {'.', '..'} for segment in path.split('/'))
        and '\\' not in path
    )


def _fetch_bounded(url, max_bytes):
    """Never follow redirects; cap response size before reading into memory."""
    request = Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'image/png,image/jpeg,application/json'})
    with _OPENER.open(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        reported_size = response.headers.get('Content-Length')
        if reported_size and reported_size.isdigit() and int(reported_size) > max_bytes:
            raise ValueError('Response is too large.')
        content = response.read(max_bytes + 1)
        if len(content) > max_bytes:
            raise ValueError('Response is too large.')
        return content, response.headers.get('Content-Type', '').split(';', 1)[0].lower()


def _query_pages(query):
    parameters = urlencode({
        'action': 'query',
        'format': 'json',
        'formatversion': '2',
        'generator': 'search',
        'gsrnamespace': '6',
        'gsrsearch': query,
        'gsrlimit': str(SEARCH_RESULTS),
        'prop': 'imageinfo',
        'iiprop': 'url|mime|extmetadata',
        'iiurlwidth': '1200',
    })
    payload, content_type = _fetch_bounded(API_ENDPOINT + '?' + parameters, API_MAX_BYTES)
    if content_type and content_type != 'application/json':
        return []
    parsed = json.loads(payload)
    if not isinstance(parsed, dict) or not isinstance(parsed.get('query'), dict):
        return []
    pages = parsed['query'].get('pages', [])
    if not isinstance(pages, list):
        return []
    pages = [page for page in pages if isinstance(page, dict)]
    return sorted(pages, key=lambda page: (
        page.get('index') if isinstance(page.get('index'), int) else SEARCH_RESULTS + 1
    ))


def _license_details(metadata):
    name = _metadata_value(metadata, 'LicenseShortName')
    if not name:
        return None
    if name.casefold() in {'cc0', 'cc0 1.0', 'public domain', 'pd'}:
        return name, _metadata_value(metadata, 'LicenseUrl')
    if not _LICENSE_RE.fullmatch(name):
        return None
    url = _metadata_value(metadata, 'LicenseUrl')
    parts = urlsplit(url)
    if parts.scheme != 'https' or parts.netloc != 'creativecommons.org':
        return None
    if not (parts.path.startswith('/licenses/by/') or parts.path.startswith('/licenses/by-sa/')):
        return None
    return name, url


def _relevant(query, title):
    terms = [
        term for term in re.findall(r'[a-z0-9]+', query.casefold())
        if len(term) >= 4 and term not in _STOP_WORDS
    ]
    if not terms:
        return False
    title_terms = set(re.findall(r'[a-z0-9]+', title.casefold()))
    return sum(term in title_terms for term in set(terms)) >= min(2, len(set(terms)))


def _valid_image(payload, content_type):
    if content_type not in {'image/png', 'image/jpeg'}:
        return False
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format not in {'PNG', 'JPEG'}:
                return False
            if image.width * image.height > IMAGE_MAX_PIXELS:
                return False
            image.verify()
    except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError):
        return False
    return True


def find_diagram(query):
    """Return one relevant, credited diagram or None if retrieval is unsafe."""
    if not isinstance(query, str):
        return None
    cleaned_query = ' '.join(query.split())[:100]
    if not cleaned_query or not _relevant(cleaned_query, cleaned_query):
        return None
    search_query = cleaned_query if 'diagram' in cleaned_query.casefold() else cleaned_query + ' diagram'
    try:
        pages = _query_pages(search_query)
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError):
        return None

    downloads = 0
    for page in pages:
        if not isinstance(page, dict) or not isinstance(page.get('title'), str) or not page['title'].startswith('File:'):
            continue
        title = page['title'][5:]
        if not _relevant(cleaned_query, title):
            continue
        if re.search(r'[-_](?:vi|fr|de|es|pt|ru|zh|ar|ja|ko)(?:[._-]|$)',
                     title.casefold()):
            continue
        infos = page.get('imageinfo') or []
        if not isinstance(infos, list) or not infos or not isinstance(infos[0], dict):
            continue
        info = infos[0]
        metadata = info.get('extmetadata') or {}
        license_details = _license_details(metadata)
        if not license_details:
            continue
        license_name, license_url = license_details
        artist = _metadata_value(metadata, 'Artist')
        if not artist and license_name.casefold() not in {'cc0', 'cc0 1.0', 'public domain', 'pd'}:
            continue
        thumbnail_url = info.get('thumburl')
        if isinstance(thumbnail_url, str):
            # Commons may add tracking parameters to thumburl. Never forward
            # query parameters to the media host.
            parts = urlsplit(thumbnail_url)
            thumbnail_url = urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))
        if not _allowed_media_url(thumbnail_url):
            continue
        source_url = info.get('descriptionurl')
        if not isinstance(source_url, str) or not source_url.startswith('https://commons.wikimedia.org/wiki/File:'):
            source_url = 'https://commons.wikimedia.org/wiki/' + quote(page['title'].replace(' ', '_'), safe=':')
        if downloads >= MAX_IMAGE_DOWNLOADS:
            break
        downloads += 1
        try:
            payload, content_type = _fetch_bounded(thumbnail_url, IMAGE_MAX_BYTES)
        except (HTTPError, URLError, OSError, TimeoutError, ValueError):
            continue
        if not _valid_image(payload, content_type):
            continue
        return DiagramImage(
            image_bytes=payload,
            title=_plain_text(title.rsplit('.', 1)[0].replace('_', ' '), 100),
            attribution=artist or 'Wikimedia Commons contributor',
            license=license_name,
            license_url=license_url,
            source_url=source_url,
        )
    return None
