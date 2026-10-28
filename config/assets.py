"""
Template tag {% asset "css/main.css" %}: the URL of a static file, versioned.

Browsers keep static files in their cache. After an edit (a CSS rebuild, a
changed script), they may still use the old file: new templates then meet an
old stylesheet, and classes added since are missing. Adding ?v=<fingerprint
of the content> to the URL gives the file a new address at each change, so
the browser downloads it again ("cache busting").

The version is a hash of the content, not the date of the last change: on
Vercel, every deployed file has the same date, so dates told nothing apart.
With a reliable version, a versioned file can stay in the browser's cache
for a year without being checked again (see the headers in vercel.json).

Declared in settings.TEMPLATES (OPTIONS "libraries"), so it needs no app:
{% load assets %} in a template.
"""

import hashlib
from functools import lru_cache
from pathlib import Path

from django import template
from django.contrib.staticfiles import finders
from django.templatetags.static import static

register = template.Library()


@lru_cache(maxsize=128)
def fingerprint(source: str, modified_ns: int, size: int) -> str:
    """
    The first 10 characters of the MD5 of a file's content.

    Cached: a file is read once, not at every page. The date and size are
    part of the cache key only so that an edit during development (same
    path, new content) computes a new fingerprint.
    """
    content = Path(source).read_bytes()
    # MD5 is fine here: it only tells versions apart, it protects nothing
    return hashlib.md5(content, usedforsecurity=False).hexdigest()[:10]


@register.simple_tag
def asset(path: str) -> str:
    """URL of the static file `path`, with a fingerprint of its content as version."""
    url = static(path)
    source = finders.find(path)  # the file in static/ (None if unknown)
    if not source:
        return url
    stat = Path(source).stat()
    return f"{url}?v={fingerprint(str(source), stat.st_mtime_ns, stat.st_size)}"
