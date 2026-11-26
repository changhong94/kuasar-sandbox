"""Shared interpreter definitions. Preparation never executes these commands."""
import copy
import re
import shlex

PRODUCTS = ('kuasar-off', 'kuasar-uffd', 'cube', 'agentenv', 'kuasar-mlink', 'kuasar-fork')
LANGUAGES = {
    'python': {'binary': '/usr/local/bin/python3', 'flag': '-c',
               'code': 'import sys; print(sys.argv[1], flush=True)'},
    'node': {'binary': '/usr/local/bin/node', 'flag': '-e',
             'code': 'process.stdout.write(process.argv[1] + "\\n")'},
    'ruby': {'binary': '/usr/local/bin/ruby', 'flag': '-e',
             'code': 'STDOUT.sync = true; puts ARGV.fetch(0)'},
}


def select_language(config, language):
    """Resolve six prepared templates before starting any timed request.

    No fallback to the Python template is permitted for another interpreter.
    A template must have been built from the pinned image in the language entry.
    Existing Python-only configurations remain valid.
    """
    if language not in LANGUAGES:
        raise ValueError(f'unknown language: {language}')
    result = copy.deepcopy(config)
    names = {k for k in result if not k.startswith('_')}
    if names != set(PRODUCTS):
        raise ValueError(f'expect all six products, got {sorted(names)}')
    entry = result.get('_languages', {}).get(language)
    if entry is None and language != 'python':
        raise ValueError(f'missing _languages.{language}; prepare six matching templates first')
    if entry is not None:
        digest = entry['digest']
        if not re.fullmatch(r'sha256:[0-9a-f]{64}', digest):
            raise ValueError('image digest must be a pinned sha256')
        if set(entry['templates']) != set(PRODUCTS):
            raise ValueError(f'{language} must declare exactly six template IDs')
        for name in PRODUCTS:
            template = entry['templates'][name]
            if not isinstance(template, str) or not template.strip() or '<' in template:
                raise ValueError(f'{language}: prepare template for {name}')
            result[name]['template'] = template
        result['_image_digest'] = digest
        result['_image'] = entry['image']
    elif not re.fullmatch(r'sha256:[0-9a-f]{64}', result.get('_image_digest', '')):
        raise ValueError('Python image digest must be pinned')
    result['_language'] = language
    return result


def print_command(language, marker, native_marker):
    spec = LANGUAGES[language]
    command = ('printf "%s\\n" ' + shlex.quote(native_marker) + '; ' +
               shlex.join(['exec', spec['binary'], spec['flag'], spec['code'], marker]))
    return command, spec['code']
