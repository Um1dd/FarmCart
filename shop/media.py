"""Public catalog uploads, including bounded byte ranges for video seeking."""
import mimetypes
from pathlib import Path
import re
from django.conf import settings
from django.http import FileResponse, Http404, HttpResponse, StreamingHttpResponse
from django.views.decorators.http import require_safe

@require_safe
def catalog_media(request, path):
    root = Path(settings.MEDIA_ROOT).resolve()
    target = (root / path).resolve()
    allowed = {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.avif', '.bmp', '.tif', '.tiff', '.mp4', '.webm', '.mov'}
    if not target.is_relative_to(root) or not target.is_file() or target.suffix.lower() not in allowed:
        raise Http404
    size = target.stat().st_size
    content_type = mimetypes.guess_type(target.name)[0] or 'application/octet-stream'
    range_header = request.headers.get('Range', '')
    start, end = 0, size - 1
    partial = False
    if range_header:
        if len(range_header) > 128:
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
        match = re.fullmatch(r'bytes=(\d*)-(\d*)', range_header)
        if not match or not any(match.groups()) or size == 0:
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
        first, last = match.groups()
        if first:
            start = int(first)
            end = min(int(last), size - 1) if last else size - 1
        else:
            start = max(0, size - int(last))
        if start > end or start >= size:
            return HttpResponse(status=416, headers={'Content-Range': f'bytes */{size}'})
        partial = True
    length = end - start + 1
    if request.method == 'HEAD':
        response = HttpResponse(content_type=content_type, status=206 if partial else 200)
    elif partial:
        def chunks():
            with target.open('rb') as file:
                file.seek(start)
                remaining = length
                while remaining:
                    chunk = file.read(min(64 * 1024, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        response = StreamingHttpResponse(chunks(), status=206, content_type=content_type)
    else:
        response = FileResponse(target.open('rb'), content_type=content_type)
    response['Accept-Ranges'] = 'bytes'
    response['Content-Length'] = str(max(0, length))
    response['X-Content-Type-Options'] = 'nosniff'
    if partial:
        response['Content-Range'] = f'bytes {start}-{end}/{size}'
    return response
