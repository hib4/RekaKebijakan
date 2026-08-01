import json
import threading
from pathlib import Path
from flask import request, has_request_context

_thread_local = threading.local()

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


def set_locale(locale: str):
    """Set locale for current thread. Call at the start of background threads."""
    _thread_local.locale = locale if locale in _translations else 'en'


def get_locale() -> str:
    if has_request_context():
        raw = request.headers.get('Accept-Language', 'en')
        return raw if raw in _translations else 'en'
    return getattr(_thread_local, 'locale', 'en')


def t(key: str, **kwargs) -> str:
    locale = get_locale()
    messages = _translations.get(locale, _translations.get('en', {}))

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
    lang_config = _languages.get(locale, _languages.get('en', {}))
    return lang_config.get('llmInstruction', 'Please respond in English.')
