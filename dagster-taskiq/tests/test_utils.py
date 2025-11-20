import pathlib

from tests.utils import tempdir_wrapper


def test_tempdir_wrapper():
    with tempdir_wrapper("/tmp/foobar") as tempfile:
        assert tempfile == "/tmp/foobar"

    with tempdir_wrapper() as tempfile:
        assert pathlib.Path(tempfile).is_dir()
    assert not pathlib.Path(tempfile).is_dir()
