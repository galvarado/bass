# common/pdf.py
import os
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from weasyprint import HTML, default_url_fetcher


def _local_path_from_url(url: str) -> str | None:
    # /media/...
    if url.startswith(settings.MEDIA_URL):
        return os.path.join(settings.MEDIA_ROOT, url[len(settings.MEDIA_URL):])

    # /static/...
    if url.startswith(settings.STATIC_URL):
        rel = url[len(settings.STATIC_URL):]

        static_root = getattr(settings, "STATIC_ROOT", None)
        if static_root:
            p = os.path.join(static_root, rel)
            if os.path.exists(p):
                return p

        for d in getattr(settings, "STATICFILES_DIRS", []):
            p = os.path.join(str(d), rel)
            if os.path.exists(p):
                return p

    return None


def render_pdf(request, template_name: str, context: dict, filename: str = "document.pdf") -> HttpResponse:
    html_str = render_to_string(template_name, context)

    base_url = request.build_absolute_uri("/")

    def url_fetcher(url: str):
        # si llega absoluto http://localhost/static/... -> /static/...
        if url.startswith(base_url):
            url = url[len(base_url) - 1:]  # deja "/" inicial

        p = _local_path_from_url(url)
        if p and os.path.exists(p):
            # IMPORTANTE: delegar al default fetcher usando file://
            return default_url_fetcher(Path(p).resolve().as_uri())

        return default_url_fetcher(url)

    pdf_bytes = HTML(string=html_str, base_url=base_url, url_fetcher=url_fetcher).write_pdf()

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    resp["Content-Disposition"] = f'inline; filename="{filename}"'
    return resp
