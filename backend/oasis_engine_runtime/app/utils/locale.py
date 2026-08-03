import json
import threading
from pathlib import Path
from flask import request, has_request_context

_thread_local = threading.local()

DEFAULT_LOCALE = 'id'

_locales_dir = Path(__file__).resolve().parents[2] / 'locales'

# Load language registry
with (_locales_dir / 'languages.json').open('r', encoding='utf-8') as f:
    _languages = json.load(f)

# Load translation files
_translations = {}
for path in _locales_dir.iterdir():
    if path.suffix == '.json' and path.name != 'languages.json':
        locale_name = path.stem
        with path.open('r', encoding='utf-8') as f:
            _translations[locale_name] = json.load(f)


def normalize_locale(locale: str | None) -> str:
    """Resolve locale IDs and Accept-Language values to a supported locale."""
    if not isinstance(locale, str) or not locale.strip():
        return DEFAULT_LOCALE

    candidates = []
    for index, item in enumerate(locale.split(',')):
        parts = [part.strip() for part in item.split(';')]
        locale_id = parts[0].replace('_', '-').lower()
        quality = 1.0
        for parameter in parts[1:]:
            if parameter.lower().startswith('q='):
                try:
                    quality = float(parameter[2:])
                except ValueError:
                    quality = 0.0
        if quality > 0:
            candidates.append((-quality, index, locale_id))

    supported = {name.lower(): name for name in _translations}
    for _, _, locale_id in sorted(candidates):
        if locale_id == '*':
            return DEFAULT_LOCALE
        if locale_id in supported:
            return supported[locale_id]
        base_locale = locale_id.split('-', 1)[0]
        if base_locale in supported:
            return supported[base_locale]
    return DEFAULT_LOCALE


def set_locale(locale: str):
    """Set locale for current thread. Call at the start of background threads."""
    _thread_local.locale = normalize_locale(locale)


def get_locale() -> str:
    if has_request_context():
        return normalize_locale(request.headers.get('Accept-Language'))
    return getattr(_thread_local, 'locale', DEFAULT_LOCALE)


def t(key: str, **kwargs) -> str:
    locale = get_locale()
    messages = _translations.get(locale, _translations.get(DEFAULT_LOCALE, {}))

    value = messages
    for part in key.split('.'):
        if isinstance(value, dict):
            value = value.get(part)
        else:
            value = None
            break

    if value is None:
        value = _translations.get('en', {})
        for part in key.split('.'):
            if isinstance(value, dict):
                value = value.get(part)
            else:
                value = None
                break

    if value is None:
        return key

    if kwargs:
        for k, v in kwargs.items():
            value = value.replace(f'{{{k}}}', str(v))

    return value


def get_language_instruction() -> str:
    locale = get_locale()
    lang_config = _languages.get(locale, _languages.get(DEFAULT_LOCALE, {}))
    return lang_config.get(
        'llmInstruction',
        'Tulis semua konten bahasa alami dalam bahasa Indonesia.'
    )
