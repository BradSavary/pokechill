"""
Template tag {% asset "css/main.css" %}: the URL of a static file, versioned.

Browsers keep static files in their cache for a while. After an edit (a CSS
rebuild, a changed script), they may still use the old file: new templates
then meet an old stylesheet, and classes added since are missing. Adding
?v=<time of the last change> to the URL gives the file a new address at each
change, so the browser downloads it again ("cache busting").

Declared in settings.TEMPLATES (OPTIONS "libraries"), so it needs no app:
{% load assets %} in a template.
"""

from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@register.simple_tag
def asset(path: str) -> str:
    """URL of the static file `path`, with its last modification time as version."""
    url = static(path)
    source = finders.find(path)  # the file in static/ (None if unknown)
    if not source:
        return url
    return f"{url}?v={int(Path(source).stat().st_mtime)}"
