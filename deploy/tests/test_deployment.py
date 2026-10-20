"""Deployment checks with no database, Docker daemon, or model API required."""
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
TASK_TEMP = ROOT / ".tmp" / "deployment-retry"
TASK_TEMP.mkdir(parents=True, exist_ok=True)


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SettingsTests(unittest.TestCase):
    def test_deployment_environment_overrides_local_defaults(self):
        with patch.dict(os.environ, {
            "MYSQL_HOST": "mysql", "MYSQL_USER": "rag", "MYSQL_PASSWORD": "secret",
            "MYSQL_PORT": "3307", "MYSQL_POOL_MAX": "5", "SQL_ECHO": "false",
            "POSTGRES_HOST": "postgres", "POSTGRES_PORT": "5433",
            "POSTGRES_PASSWORD": "pg-secret", "JWT_SECRET": "random-key",
        }):
            settings = load_module("deploy_settings", ROOT / "fastapi-app/settings.py")
        credentials = settings.TORTOISE_ORM["connections"]["default"]["credentials"]
        self.assertEqual((credentials["host"], credentials["port"], credentials["user"]), ("mysql", 3307, "rag"))
        self.assertEqual(credentials["password"], "secret")
        self.assertEqual(credentials["maxsize"], 5)
        self.assertFalse(credentials["echo"])
        self.assertEqual(settings.PGVECTOR["host"], "postgres")
        self.assertEqual(settings.PGVECTOR["port"], 5433)
        self.assertEqual(settings.PGVECTOR["password"], "pg-secret")
        self.assertEqual(settings.JWT_SECRET, "random-key")


class FileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        fastapi = types.ModuleType("fastapi")
        fastapi.UploadFile = object
        exceptions = types.ModuleType("common.exception_handler")
        exceptions.CustomException = ValueError
        with patch.dict(sys.modules, {"fastapi": fastapi, "common.exception_handler": exceptions}):
            self.service = load_module("deploy_file_service", ROOT / "fastapi-app/service/file_service.py")
        self.service.UPLOAD_DIR = self.temp.name
        self.service.DOWNLOAD_PREFIX = "/api/files/download/"

    def test_save_and_resolve_unicode_filename(self):
        upload = types.SimpleNamespace(filename="文档 a.txt", file=io.BytesIO(b"demo"))
        url = self.service.save(upload)
        self.assertEqual(url, "/api/files/download/%E6%96%87%E6%A1%A3%20a.txt")
        self.assertEqual(Path(self.service.resolve(upload.filename)).read_bytes(), b"demo")

    def test_reject_traversal_for_upload_and_download(self):
        for filename in (None, "", ".", "..", "../outside", "/etc/passwd", "..\\outside", "a\x00b"):
            with self.subTest(filename=filename):
                with self.assertRaises(ValueError):
                    self.service.save(types.SimpleNamespace(filename=filename, file=io.BytesIO(b"bad")))
                with self.assertRaises(ValueError):
                    self.service.resolve(filename)

    def test_reject_symlink_outside_upload_directory(self):
        with tempfile.TemporaryDirectory() as outside:
            target = Path(outside) / "secret.txt"
            target.write_text("secret")
            (Path(self.temp.name) / "link.txt").symlink_to(target)
            with self.assertRaises(ValueError):
                self.service.save(types.SimpleNamespace(filename="link.txt", file=io.BytesIO(b"bad")))
            with self.assertRaises(ValueError):
                self.service.resolve("link.txt")
            self.assertEqual(target.read_text(), "secret")

    def test_missing_file(self):
        with self.assertRaises(ValueError):
            self.service.resolve("missing.txt")


class ScriptTests(unittest.TestCase):
    def test_check_mode_does_not_install_or_start_services(self):
        with tempfile.TemporaryDirectory() as folder:
            docker = Path(folder) / "docker"
            docker.write_text('#!/bin/sh\nprintf "%s\\n" "$*"\n')
            docker.chmod(0o755)
            with patch.dict(os.environ, {"PATH": folder + os.pathsep + os.environ["PATH"]}):
                result = subprocess.run(["bash", str(ROOT / "deploy.sh"), "--check"], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("config --quiet", result.stdout)
            self.assertNotIn(" up ", result.stdout)
            self.assertNotIn(" build ", result.stdout)

    def test_invalid_argument_fails_before_mutations(self):
        result = subprocess.run(["bash", str(ROOT / "deploy.sh"), "--unknown"], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("用法", result.stderr)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TASK_TEMP)
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.key = self.folder / "docker.asc"
        self.source = self.folder / "docker.sources"
        curl = self.folder / "curl"
        curl.write_text('''#!/bin/bash
while [[ "$1" != -o ]]; do shift; done
printf 'official-key\\n' > "$2"
[[ "${DOWNLOAD_FAIL:-0}" != 1 ]]
''')
        curl.chmod(0o755)

    def configure(self, fail=False):
        return subprocess.run([
            "bash", "-c", 'source "$1"; configure_docker_repository ubuntu noble amd64 "$2" "$3"',
            "test", str(ROOT / "deploy/docker-repository.sh"), str(self.key), str(self.source),
        ], env={**os.environ, "PATH": str(self.folder) + os.pathsep + os.environ["PATH"],
                "DOWNLOAD_FAIL": "1" if fail else "0"}, capture_output=True, text=True)

    def test_retry_reuses_matching_configuration(self):
        self.assertEqual(self.configure().returncode, 0)
        before = (self.key.stat().st_mtime_ns, self.source.stat().st_mtime_ns)
        self.assertEqual(self.configure().returncode, 0)
        self.assertEqual(before, (self.key.stat().st_mtime_ns, self.source.stat().st_mtime_ns))

    def test_partial_install_can_resume(self):
        self.key.write_text("official-key\n")
        self.assertEqual(self.configure().returncode, 0)
        self.assertIn("Suites: noble", self.source.read_text())

    def test_conflicting_configuration_is_preserved(self):
        self.source.write_text("user-managed source\n")
        self.assertNotEqual(self.configure().returncode, 0)
        self.assertEqual(self.source.read_text(), "user-managed source\n")
        self.assertFalse(self.key.exists())

    def test_download_failure_does_not_install_partial_files(self):
        self.assertNotEqual(self.configure(fail=True).returncode, 0)
        self.assertFalse(self.key.exists())
        self.assertFalse(self.source.exists())
        self.assertEqual(sorted(p.name for p in self.folder.iterdir()), ["curl"])


class DeploymentRetryTests(unittest.TestCase):
    def test_failed_first_run_keeps_login_pending_until_success(self):
        with tempfile.TemporaryDirectory(dir=TASK_TEMP) as directory:
            folder = Path(directory)
            (folder / "deploy").mkdir()
            binary = folder / "bin"
            binary.mkdir()
            # Exercise the Linux control flow without root or a real Docker daemon.
            script = (ROOT / "deploy.sh").read_text().replace('if [[ "$EUID" != 0 ]]; then', 'if false; then')
            (folder / "deploy.sh").write_text(script)
            fake = '''#!PYTHON
import json, os, subprocess, sys
from pathlib import Path
name = Path(sys.argv[0]).name
args = sys.argv[1:]
if name == 'uname': print('Linux')
elif name == 'openssl':
    print('a' * 32 if args[0] == 'rand' else '$apr1$fake')
elif name == 'curl':
    login = any('/api/login' in a for a in args)
    if login:
        with open('logins', 'a') as f: f.write('login\\n')
    print(json.dumps({'code': '500' if login and os.getenv('FAIL_LOGIN') else '200', 'data': {'token': 'test'}}))
elif name == 'docker':
    if 'build' in args and os.getenv('FAIL_BUILD'): sys.exit(1)
    if 'exec' in args:
        pos = args.index('python')
        sys.exit(subprocess.call([sys.executable] + args[pos + 1:]))
elif name != 'flock': sys.exit('Unexpected command: ' + name)
'''.replace('PYTHON', sys.executable)
            for name in ('uname', 'openssl', 'curl', 'docker', 'flock'):
                target = binary / name
                target.write_text(fake)
                target.chmod(0o755)
            env = {**os.environ, "PATH": str(binary) + os.pathsep + os.environ["PATH"]}

            def run(**flags):
                return subprocess.run(["bash", str(folder / "deploy.sh")], cwd=folder,
                                      env={**env, **flags}, capture_output=True, text=True)

            marker = folder / "deploy/.installed"
            self.assertNotEqual(run(FAIL_BUILD="1").returncode, 0)
            credentials = (folder / "deploy/.env").read_text()
            self.assertFalse(marker.exists())
            self.assertNotEqual(run(FAIL_LOGIN="1").returncode, 0)
            self.assertFalse(marker.exists())
            result = run()
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(marker.exists())
            self.assertEqual((folder / "logins").read_text().splitlines(), ['login', 'login'])
            self.assertEqual(run().returncode, 0)
            self.assertEqual((folder / "logins").read_text().splitlines(), ['login', 'login'])
            self.assertEqual((folder / "deploy/.env").read_text(), credentials)


if __name__ == "__main__":
    unittest.main()
