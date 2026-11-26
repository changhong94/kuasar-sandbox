"""Run with python3 -m unittest discover -s .../aligned -p 'test_*.py'."""
import json
from pathlib import Path
import shlex
import tempfile
import types
import unittest
from unittest.mock import patch
from languages import LANGUAGES, PRODUCTS, print_command, select_language
import startup


def config(language='python'):
    c = {n: {'kind': 'e2b', 'template': 'python-template'} for n in PRODUCTS}
    c['_image_digest'] = 'sha256:' + 'a' * 64
    c['_languages'] = {language: {'image': language + '@sha256:' + 'b' * 64,
        'digest': 'sha256:' + 'b' * 64,
        'templates': {n: language + '-' + n for n in PRODUCTS}}}
    return select_language(c, language)


class LanguageTests(unittest.TestCase):
    def test_no_fallback_or_mutation(self):
        c = {n: {'template': 'original'} for n in PRODUCTS}
        c['_image_digest'] = 'sha256:' + 'a' * 64
        self.assertEqual(select_language(c, 'python')['_language'], 'python')
        self.assertNotIn('_language', c)
        with self.assertRaisesRegex(ValueError, 'missing'): select_language(c, 'node')
        for l in LANGUAGES:
            selected = config(l)
            self.assertEqual(selected['kuasar-fork']['template'], l + '-kuasar-fork')
            selected['_languages'][l]['templates'].pop('cube')
            with self.assertRaises(ValueError): select_language(selected, l)

    def test_real_interpreter_and_quoting(self):
        for l, spec in LANGUAGES.items():
            marker = "READY_'$(touch unsafe)"
            command, code = print_command(l, marker, 'NATIVE_safe')
            args = shlex.split(command.split('; ', 1)[1])
            self.assertEqual(args, ['exec', spec['binary'], spec['flag'], code, marker])
            self.assertNotIn('python', code if l != 'python' else '')

    def test_stream_timing_and_cleanup_all_languages(self):
        for l in LANGUAGES:
            with self.subTest(language=l), tempfile.TemporaryDirectory() as d:
                class Sandbox:
                    sandbox_id = 'test-sandbox'
                    killed = False
                    @classmethod
                    def create(cls, template, **kwargs):
                        self.assertEqual(template, l + '-kuasar-fork')
                        obj = cls()
                        obj.commands = types.SimpleNamespace(run=obj.run)
                        cls.last = obj
                        return obj
                    def run(obj, command, **kwargs):
                        args = shlex.split(command.split('; ', 1)[1])
                        self.assertEqual(args[1], LANGUAGES[l]['binary'])
                        native = shlex.split(command.split('; ', 1)[0])[-1]
                        output = native + '\n' + args[-1] + '\n'
                        # Markers crossing callback boundaries must be recognized.
                        for chunk in [output[:4], output[4:-1], output[-1:]]:
                            kwargs['on_stdout'](chunk)
                        return types.SimpleNamespace(exit_code=0, stdout=output)
                    def kill(obj): obj.killed = True
                c = config(l); path = Path(d) / 'sample.json'
                with patch.object(startup, 'pool_wait', return_value={'supported': False}):
                    self.assertTrue(startup.sample('kuasar-fork', c, path, c['kuasar-fork'], Sandbox))
                row = json.loads(path.read_text())
                self.assertTrue(Sandbox.last.killed)
                self.assertEqual(row['language'], l)
                self.assertEqual(row['interpreter_print_ms'], (row['received_ns']-row['start_ns'])/1e6)
                self.assertLessEqual(row['native_received_ns'], row['received_ns'])
                self.assertEqual('python_print_ms' in row, l == 'python')
                self.assertFalse(path.with_suffix('.ledger').exists())

    def test_exec_failure_is_preserved_and_destroyed(self):
        class BadSandbox:
            sandbox_id = 'bad'
            @classmethod
            def create(cls, *args, **kw):
                obj = cls();cls.last = obj
                obj.commands = types.SimpleNamespace(run=lambda *a, **k: types.SimpleNamespace(exit_code=1,stdout=''))
                return obj
            def kill(self): self.killed = True
        with tempfile.TemporaryDirectory() as d, patch.object(startup, 'pool_wait', return_value={'supported': False}):
            c = config('ruby');path = Path(d)/'bad.json'
            self.assertFalse(startup.sample('cube',c,path,c['cube'],BadSandbox))
            self.assertTrue(BadSandbox.last.killed)
            self.assertFalse(json.loads(path.read_text())['success'])


if __name__ == '__main__': unittest.main()
