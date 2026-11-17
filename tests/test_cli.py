"""The command line runs without a network connection for its offline commands."""
import io
import tempfile
import unittest
from contextlib import redirect_stdout

from okn_connection_map import cli


class TestCli(unittest.TestCase):
    def test_help_and_offline_check(self):
        with tempfile.TemporaryDirectory() as d:
            buf = io.StringIO()
            with redirect_stdout(buf):
                rc = cli.main(["--home", d, "check", "--offline"])
            self.assertEqual(rc, 0)
            self.assertIn("working folder is writable", buf.getvalue())

    def test_version(self):
        with self.assertRaises(SystemExit) as e, redirect_stdout(io.StringIO()):
            cli.main(["--version"])
        self.assertEqual(e.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
