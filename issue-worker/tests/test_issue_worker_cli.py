import json
import os
import subprocess
import tempfile
import threading
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "issue-worker" / "scripts" / "issue-worker"


def run_cmd(args, cwd, env=None, input_text=None, check=True):
    merged_env = os.environ.copy()
    merged_env["PYTHONPYCACHEPREFIX"] = tempfile.mkdtemp(prefix="issue-worker-pycache-")
    merged_env["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="issue-worker-config-")
    merged_env.pop("ISSUE_WORKER_TOKEN", None)
    merged_env.pop("GITHUB_TOKEN", None)
    merged_env.pop("GITLAB_TOKEN", None)
    merged_env.pop("GITEE_TOKEN", None)
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        [str(CLI)] + args,
        cwd=str(cwd),
        env=merged_env,
        input=input_text,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if check and proc.returncode != 0:
        raise AssertionError(
            f"command failed: issue-worker {' '.join(args)}\nstdout:\n{proc.stdout}\nstderr:\n{proc.stderr}"
        )
    return proc


def git(args, cwd):
    proc = subprocess.run(["git"] + args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout.strip()


def init_git_repo(remote_url):
    tmp = tempfile.TemporaryDirectory()
    repo = Path(tmp.name)
    git(["init", "-q"], repo)
    git(["remote", "add", "origin", remote_url], repo)
    return tmp, repo


def commit_file(repo, path="README.md", text="test\n"):
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text, encoding="utf-8")
    git(["add", path], repo)
    git(["-c", "user.name=Test Agent", "-c", "user.email=test@example.com", "commit", "-q", "-m", f"add {path}"], repo)


class FakeGitLabState:
    def __init__(self):
        self.base_issues = [
            {"iid": 1, "title": "Fix worker", "state": "opened", "description": "Need a reliable worker."},
            {"iid": 2, "title": "Second issue", "state": "opened", "description": ""},
        ]
        self.created_issues = []
        self.comments = {}
        self.branches = []
        self.merge_requests = []
        self.requests = []

    def all_issues(self):
        return self.base_issues + self.created_issues

    def find_issue(self, iid):
        iid = int(iid)
        for issue in self.all_issues():
            if issue["iid"] == iid:
                return issue
        return None


class FakeGitLabHandler(BaseHTTPRequestHandler):
    state = FakeGitLabState()
    token = "test-token"

    def log_message(self, format, *args):
        return

    def _read_json(self):
        length = int(self.headers.get("Content-Length", "0") or "0")
        if not length:
            return {}
        raw = self.rfile.read(length).decode("utf-8")
        if self.headers.get("Content-Type", "").startswith("application/json"):
            return json.loads(raw)
        return {k: v[0] for k, v in urllib.parse.parse_qs(raw).items()}

    def _send(self, status, data, headers=None):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _check_auth(self):
        if self.headers.get("PRIVATE-TOKEN") != self.token:
            self._send(401, {"message": "401 Unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self._check_auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)
        self.state.requests.append(("GET", path, query))

        if path == "/api/v4/user":
            self._send(200, {"username": "agent"})
            return
        if path == "/api/v4/projects/huhw%2Fissue-test":
            self._send(200, {"id": 1093, "path_with_namespace": "huhw/issue-test", "default_branch": "main"})
            return
        if path == "/api/v4/projects/huhw%2Fissue-test/issues":
            state = query.get("state", [""])[0]
            if state == "open":
                self._send(400, {"message": "state does not have a valid value"})
                return
            page = query.get("page", ["1"])[0]
            if self.state.created_issues:
                self._send(200, self.state.all_issues())
                return
            if page == "1":
                self._send(
                    200,
                    [self.state.base_issues[0]],
                    {"X-Next-Page": "2"},
                )
            else:
                self._send(200, [self.state.base_issues[1]])
            return
        issue_match = re_match_issue(path)
        if issue_match:
            issue = self.state.find_issue(issue_match)
            if issue:
                self._send(200, issue)
                return
        notes_match = re_match_notes(path)
        if notes_match:
            comments = self.state.comments.get(notes_match) or [
                {"body": "Existing note", "author": {"username": "maintainer"}, "created_at": "2026-04-29"}
            ]
            self._send(200, comments)
            return
        self._send(404, {"message": "not found"})

    def do_POST(self):
        if not self._check_auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()
        self.state.requests.append(("POST", path, body))

        notes_match = re_match_notes(path)
        if notes_match:
            note = {"body": body["body"], "web_url": f"http://fake/issues/{notes_match}/notes/1"}
            self.state.comments.setdefault(notes_match, []).append(note)
            self._send(201, note)
            return
        if path == "/api/v4/projects/huhw%2Fissue-test/issues":
            iid = 3 + len(self.state.created_issues)
            issue = {
                "iid": iid,
                "title": body["title"],
                "description": body.get("description", ""),
                "state": "opened",
                "web_url": f"http://fake/issues/{iid}",
            }
            self.state.created_issues.append(issue)
            self._send(201, issue)
            return
        if path == "/api/v4/projects/huhw%2Fissue-test/repository/branches":
            self.state.branches.append(body)
            self._send(201, {"name": body["branch"], "web_url": "http://fake/branch"})
            return
        if path == "/api/v4/projects/huhw%2Fissue-test/merge_requests":
            self.state.merge_requests.append(body)
            self._send(201, {"iid": 7, "web_url": "http://fake/mr/7"})
            return
        self._send(404, {"message": "not found"})

    def do_PUT(self):
        if not self._check_auth():
            return
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        body = self._read_json()
        self.state.requests.append(("PUT", path, body))

        issue_match = re_match_issue(path)
        if issue_match:
            issue = self.state.find_issue(issue_match)
            if issue and body.get("state_event") == "close":
                issue["state"] = "closed"
                self._send(200, issue)
                return
        self._send(404, {"message": "not found"})


def re_match_issue(path):
    prefix = "/api/v4/projects/huhw%2Fissue-test/issues/"
    if path.startswith(prefix) and "/notes" not in path:
        return path[len(prefix):]
    return None


def re_match_notes(path):
    prefix = "/api/v4/projects/huhw%2Fissue-test/issues/"
    suffix = "/notes"
    if path.startswith(prefix) and path.endswith(suffix):
        return path[len(prefix):-len(suffix)]
    return None


class FakeGitLabServer:
    def __enter__(self):
        FakeGitLabHandler.state = FakeGitLabState()
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), FakeGitLabHandler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/api/v4"
        self.state = FakeGitLabHandler.state
        return self

    def __exit__(self, exc_type, exc, tb):
        self.httpd.shutdown()
        self.thread.join(timeout=5)
        self.httpd.server_close()


def write_project_config(repo, api_base_url):
    config = {
        "version": 1,
        "provider": "gitlab",
        "host": "git.arlth.cn",
        "apiBaseUrl": api_base_url,
        "repoPath": "huhw/issue-test",
        "projectId": "huhw/issue-test",
        "defaultBranch": "main",
        "credentialRef": "gitlab://git.arlth.cn/agent",
        "workflow": {
            "branchMode": "ask",
            "branchPrefix": "issue/",
            "completionMode": "ask",
            "autoClose": "after_merge_or_confirm",
            "commentPolicy": "progress_blocker_done",
        },
    }
    config_path = repo / ".issue-worker" / "project.json"
    config_path.parent.mkdir(parents=True)
    config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
    return config_path


class InitTests(unittest.TestCase):
    def test_init_detects_github_gitlab_and_gitee_without_token(self):
        cases = [
            ("https://github.com/example/repo.git", "github", "github.com", "https://api.github.com", "example/repo"),
            ("git@gitlab.com:group/sub/repo.git", "gitlab", "gitlab.com", "https://gitlab.com/api/v4", "group/sub/repo"),
            ("https://gitee.com/owner/repo.git", "gitee", "gitee.com", "https://gitee.com/api/v5", "owner/repo"),
        ]
        for remote, provider, host, api_base, repo_path in cases:
            with self.subTest(remote=remote):
                tmp, repo = init_git_repo(remote)
                with tmp:
                    run_cmd(["init", "--username", "alice", "--default-branch", "main"], repo)
                    config = json.loads((repo / ".issue-worker" / "project.json").read_text())
                    self.assertEqual(config["provider"], provider)
                    self.assertEqual(config["host"], host)
                    self.assertEqual(config["apiBaseUrl"], api_base)
                    self.assertEqual(config["repoPath"], repo_path)
                    self.assertNotIn("token", json.dumps(config).lower())

    def test_multiple_remotes_require_explicit_remote_in_non_interactive_mode(self):
        tmp = tempfile.TemporaryDirectory()
        with tmp:
            repo = Path(tmp.name)
            git(["init", "-q"], repo)
            git(["remote", "add", "aaa", "https://github.com/example/a.git"], repo)
            git(["remote", "add", "bbb", "https://github.com/example/b.git"], repo)
            proc = run_cmd(["init", "--username", "alice"], repo, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("Multiple remote candidates", proc.stderr)

    def test_init_without_token_prints_actionable_bundled_setup_command(self):
        tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
        with tmp:
            proc = run_cmd(
                ["init", "--provider", "gitlab", "--api-base-url", "https://git.arlth.cn/api/v4", "--username", "huhw"],
                repo,
            )
            self.assertIn("https://git.arlth.cn/-/user_settings/personal_access_tokens", proc.stdout)
            self.assertIn("Token 配置说明", proc.stdout)
            self.assertIn("只读取项目和 issue 通常只需要 read_api", proc.stdout)
            self.assertIn(str(CLI), proc.stdout)
            self.assertIn("token set --from-stdin", proc.stdout)
            self.assertNotIn("Run `issue-worker token set` later", proc.stdout)

    def test_doctor_without_token_prints_actionable_bundled_setup_command(self):
        tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
        with tmp:
            write_project_config(repo, "https://git.arlth.cn/api/v4")
            proc = run_cmd(["doctor"], repo, check=False)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("https://git.arlth.cn/-/user_settings/personal_access_tokens", proc.stdout)
            self.assertIn("Token 配置说明", proc.stdout)
            self.assertIn(str(CLI), proc.stdout)
            self.assertIn("token set --from-stdin", proc.stdout)


class FakeGitLabAgentScenarioTests(unittest.TestCase):
    def test_agent_issue_flow_against_fake_gitlab(self):
        with FakeGitLabServer() as server:
            tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
            with tmp:
                write_project_config(repo, server.url)
                env = {"ISSUE_WORKER_TOKEN": FakeGitLabHandler.token}

                doctor = run_cmd(["doctor"], repo, env=env)
                self.assertIn("API project lookup succeeded", doctor.stdout)

                listed = run_cmd(["issues", "list", "--state", "open", "--limit", "2", "--json"], repo, env=env)
                issues = json.loads(listed.stdout)
                self.assertEqual([issue["iid"] for issue in issues], [1, 2])
                issue_list_query = [
                    request[2]
                    for request in server.state.requests
                    if request[0] == "GET" and request[1] == "/api/v4/projects/huhw%2Fissue-test/issues"
                ][0]
                self.assertEqual(issue_list_query["state"], ["opened"])

                got = run_cmd(["issues", "get", "1", "--json"], repo, env=env)
                payload = json.loads(got.stdout)
                self.assertEqual(payload["issue"]["title"], "Fix worker")
                self.assertEqual(payload["comments"][0]["body"], "Existing note")

                created = run_cmd(
                    [
                        "issues",
                        "create",
                        "--title",
                        "Agent-created issue",
                        "--body",
                        "Created by an agent scenario test.",
                        "--confirm",
                        "--json",
                    ],
                    repo,
                    env=env,
                )
                created_payload = json.loads(created.stdout)
                self.assertEqual(created_payload["iid"], 3)
                self.assertEqual(server.state.created_issues[0]["title"], "Agent-created issue")

                created_get = run_cmd(["issues", "get", "3", "--json"], repo, env=env)
                created_get_payload = json.loads(created_get.stdout)
                self.assertEqual(created_get_payload["issue"]["state"], "opened")

                comment = run_cmd(
                    ["issues", "comment", "3", "--body", "Agent progress update", "--confirm"],
                    repo,
                    env=env,
                )
                self.assertIn("Comment posted", comment.stdout)
                self.assertEqual(server.state.comments["3"][0]["body"], "Agent progress update")

                commented_get = run_cmd(["issues", "get", "3", "--json"], repo, env=env)
                commented_payload = json.loads(commented_get.stdout)
                self.assertEqual(commented_payload["comments"][0]["body"], "Agent progress update")

                comment_json = run_cmd(
                    ["issues", "comment", "3", "--body", "Structured progress update", "--confirm", "--json"],
                    repo,
                    env=env,
                )
                comment_payload = json.loads(comment_json.stdout)
                self.assertTrue(comment_payload["comment"]["posted"])
                self.assertEqual(comment_payload["comment"]["raw"]["body"], "Structured progress update")

                start = run_cmd(
                    [
                        "work",
                        "start",
                        "1",
                        "--create-branch",
                        "--branch",
                        "issue/1-fix-worker",
                        "--base",
                        "main",
                        "--confirm",
                    ],
                    repo,
                    env=env,
                )
                self.assertIn("Branch created", start.stdout)
                self.assertEqual(server.state.branches[0]["branch"], "issue/1-fix-worker")

                finish = run_cmd(
                    [
                        "work",
                        "finish",
                        "1",
                        "--create-pr",
                        "--branch",
                        "issue/1-fix-worker",
                        "--base",
                        "main",
                        "--title",
                        "Fix #1: Fix worker",
                        "--body",
                        "Issue: fake\n\nValidation: fake",
                        "--confirm",
                    ],
                    repo,
                    env=env,
                )
                self.assertIn("MR created", finish.stdout)
                self.assertEqual(server.state.merge_requests[0]["source_branch"], "issue/1-fix-worker")

                finish_json = run_cmd(
                    [
                        "work",
                        "finish",
                        "1",
                        "--create-pr",
                        "--branch",
                        "issue/1-fix-worker",
                        "--base",
                        "main",
                        "--title",
                        "Fix #1: Fix worker",
                        "--body",
                        "Issue: fake\n\nValidation: fake",
                        "--confirm",
                        "--json",
                    ],
                    repo,
                    env=env,
                )
                finish_payload = json.loads(finish_json.stdout)
                self.assertTrue(finish_payload["mr"]["created"])
                self.assertEqual(finish_payload["mr"]["url"], "http://fake/mr/7")
                self.assertIn("comment_issue_completion", finish_payload["next_actions"])
                self.assertIn("preflight", finish_payload)

                closed = run_cmd(["issues", "close", "3", "--confirm", "--json"], repo, env=env)
                closed_payload = json.loads(closed.stdout)
                self.assertTrue(closed_payload["close"]["performed"])
                closed_get = run_cmd(["issues", "get", "3", "--json"], repo, env=env)
                closed_payload = json.loads(closed_get.stdout)
                self.assertEqual(closed_payload["issue"]["state"], "closed")

    def test_json_doctor_and_work_start_preflight(self):
        with FakeGitLabServer() as server:
            tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
            with tmp:
                commit_file(repo)
                write_project_config(repo, server.url)
                (repo / "scratch.txt").write_text("temporary\n", encoding="utf-8")
                env = {"ISSUE_WORKER_TOKEN": FakeGitLabHandler.token}

                doctor = run_cmd(["doctor", "--json"], repo, env=env)
                doctor_payload = json.loads(doctor.stdout)
                self.assertTrue(doctor_payload["ok"])
                self.assertEqual(doctor_payload["config"]["provider"], "gitlab")
                self.assertTrue(doctor_payload["token"]["found"])

                start = run_cmd(["work", "start", "1", "--local", "--json"], repo, env=env)
                start_payload = json.loads(start.stdout)
                self.assertIn("preflight", start_payload)
                self.assertIn("scratch.txt", start_payload["preflight"]["status"]["untracked"])
                self.assertIn("review_worktree_changes", start_payload["next_actions"])

    def test_invalid_state_error_is_actionable(self):
        with FakeGitLabServer() as server:
            tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
            with tmp:
                write_project_config(repo, server.url)
                env = {"ISSUE_WORKER_TOKEN": FakeGitLabHandler.token}
                proc = run_cmd(["issues", "list", "--state", "bad-state"], repo, env=env, check=False)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("[gitlab/issues/list] invalid state value", proc.stderr)
                self.assertIn("Suggestion: retry with --state open", proc.stderr)

    def test_write_commands_require_confirmation_in_non_interactive_mode(self):
        with FakeGitLabServer() as server:
            tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
            with tmp:
                write_project_config(repo, server.url)
                env = {"ISSUE_WORKER_TOKEN": FakeGitLabHandler.token}
                proc = run_cmd(["issues", "comment", "1", "--body", "No confirm"], repo, env=env, check=False)
                self.assertNotEqual(proc.returncode, 0)
                self.assertIn("requires --confirm", proc.stderr)
                create_proc = run_cmd(["issues", "create", "--title", "No confirm"], repo, env=env, check=False)
                self.assertNotEqual(create_proc.returncode, 0)
                self.assertIn("requires --confirm", create_proc.stderr)
                close_proc = run_cmd(["issues", "close", "1"], repo, env=env, check=False)
                self.assertNotEqual(close_proc.returncode, 0)
                self.assertIn("requires --confirm", close_proc.stderr)

    def test_token_set_from_stdin_saves_and_tests_token(self):
        with FakeGitLabServer() as server:
            tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
            with tmp:
                write_project_config(repo, server.url)
                xdg_home = tempfile.mkdtemp(prefix="issue-worker-config-")
                proc = run_cmd(
                    ["token", "set", "--from-stdin"],
                    repo,
                    env={"XDG_CONFIG_HOME": xdg_home},
                    input_text=FakeGitLabHandler.token + "\n",
                )
                self.assertIn("Token 已通过", proc.stdout)
                self.assertIn("[ok] 项目访问正常", proc.stdout)

    def test_fallback_token_wins_when_git_credential_helper_would_prompt(self):
        with FakeGitLabServer() as server:
            tmp, repo = init_git_repo("git@git.arlth.cn:huhw/issue-test.git")
            with tmp:
                write_project_config(repo, server.url)
                xdg_home = tempfile.mkdtemp(prefix="issue-worker-config-")
                helper = Path(xdg_home) / "prompting-helper.sh"
                helper.write_text(
                    "#!/bin/sh\n"
                    "if [ \"$GIT_TERMINAL_PROMPT\" != \"0\" ]; then\n"
                    "  echo password=wrong-token\n"
                    "  exit 0\n"
                    "fi\n"
                    "exit 1\n",
                    encoding="utf-8",
                )
                helper.chmod(0o700)
                git(["config", "credential.helper", str(helper)], repo)
                run_cmd(
                    ["token", "set", "--from-stdin"],
                    repo,
                    env={"XDG_CONFIG_HOME": xdg_home},
                    input_text=FakeGitLabHandler.token + "\n",
                )

                proc = run_cmd(["token", "test"], repo, env={"XDG_CONFIG_HOME": xdg_home})

                self.assertIn("[ok] 项目访问正常", proc.stdout)


if __name__ == "__main__":
    unittest.main()
