"""
Translations from cam4linux/lang/<code>.json.

The language follows the system setting (LANGUAGE, LC_ALL, LC_MESSAGES, LANG)
unless overridden in the config ("language": "de"). English is the fallback,
both for unsupported languages and for single missing keys.
"""

import json
import os

LANG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "lang")
FALLBACK = "en"

_fallback = {}
_strings = {}
current = FALLBACK


def available():
    """{code: native language name} of all shipped language files."""
    res = {}
    for f in sorted(os.listdir(LANG_DIR)):
        if f.endswith(".json"):
            code = f[:-5]
            res[code] = _load(code).get("language.name", code)
    return res


def _load(code):
    try:
        with open(os.path.join(LANG_DIR, code + ".json"), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return {}


def system_language():
    """First supported language from the environment, else the fallback."""
    langs = available()
    candidates = []
    if os.environ.get("LANGUAGE"):
        candidates += os.environ["LANGUAGE"].split(":")
    for var in ("LC_ALL", "LC_MESSAGES", "LANG"):
        if os.environ.get(var):
            candidates.append(os.environ[var])
            break
    for c in candidates:
        code = c.split(".")[0].split("@")[0].split("_")[0].lower()
        if code in langs:
            return code
    return FALLBACK


def setup(language="auto"):
    global _fallback, _strings, current
    if not language or language == "auto" or language not in available():
        language = system_language()
    current = language
    _fallback = _load(FALLBACK)
    _strings = _load(language) if language != FALLBACK else _fallback


def tr(key, **args):
    if not _fallback:
        setup()
    s = _strings.get(key)
    if s is None:
        s = _fallback.get(key, key)
    if args:
        try:
            return s.format(**args)
        except (KeyError, IndexError, ValueError):
            return s
    return s
