"""Environment names must be identical at launch time and inside the container.

The slug is derived from the defining module. A script run as ``python foo.py`` has
``__module__ == "__main__"`` locally, but the remote resolver re-imports it as ``foo``
(``resolver_args: ('mod', 'foo', 'instance', 'wf')``). If the slug differs, the image
cache built at launch is keyed ``main_*`` while the container looks up ``foo_*`` and the
run dies with ``Environment 'foo_..._env' not found in image cache``.
"""

import sys
import types

from flyte_migrate._workflow import module_slug


def test_dotted_module_is_slugified():
    assert module_slug("examples.deck_example") == "examples_deck_example"


def test_missing_module_falls_back_to_main():
    assert module_slug(None) == "main"


def test_main_at_the_root_slugs_to_the_stem(monkeypatch, tmp_path):
    """``cd examples && python deck_example.py`` -> container imports ``deck_example``."""
    script = tmp_path / "deck_example.py"
    script.touch()
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(script)
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    monkeypatch.chdir(tmp_path)

    assert module_slug("__main__") == "deck_example"


def test_main_below_the_root_keeps_the_dotted_path(monkeypatch, tmp_path):
    """``python examples/deck_example.py`` -> container imports ``examples.deck_example``.

    flyte names the module by its path relative to the root dir (default: cwd), so the
    slug has to carry the package prefix or it won't match the image cache key.
    """
    script = tmp_path / "examples" / "deck_example.py"
    script.parent.mkdir()
    script.touch()
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(script)
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    monkeypatch.chdir(tmp_path)

    assert module_slug("__main__") == "examples_deck_example"


def test_main_outside_the_root_falls_back_to_the_stem(monkeypatch, tmp_path):
    """cwd is not an ancestor of the script, so there is no relative path to use."""
    script = tmp_path / "elsewhere" / "deck_example.py"
    script.parent.mkdir()
    script.touch()
    cwd = tmp_path / "somewhere_else"
    cwd.mkdir()
    fake_main = types.ModuleType("__main__")
    fake_main.__file__ = str(script)
    monkeypatch.setitem(sys.modules, "__main__", fake_main)
    monkeypatch.chdir(cwd)

    assert module_slug("__main__") == "deck_example"


def test_main_without_a_file_falls_back_to_main(monkeypatch):
    """REPL / ``python -c`` have no ``__main__.__file__`` to read."""
    fake_main = types.ModuleType("__main__")
    monkeypatch.setitem(sys.modules, "__main__", fake_main)

    assert module_slug("__main__") == "main"
