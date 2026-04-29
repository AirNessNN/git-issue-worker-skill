import json
import os
import re
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "issue-worker" / "scripts" / "issue-worker"
LIVE_REPO_REMOTE = "git@git.arlth.cn:huhw/issue-test.git"
LIVE_API_BASE = "https://git.arlth.cn/api/v4"
LIVE_HOST = "git.arlth.cn"
LIVE_REPO_PATH = "huhw/issue-test"


def run_cmd(args, cwd, env=None, check=True):
    merged_env = os.environ.copy()
    merged_env["PYTHONPYCACHEPREFIX"] = tempfile.mkdtemp(prefix="issue-worker-pycache-")
    if env:
        merged_env.update(env)
    proc = subprocess.run(
        [str(CLI)] + args,
        cwd=str(cwd),
        env=merged_env,
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


def gitlab_api(method, path, token, body=None):
    url = LIVE_API_BASE + path
    data = None
    headers = {"PRIVATE-TOKEN": token, "Accept": "application/json", "User-Agent": "issue-worker-live-test"}
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read()
            return json.loads(raw.decode("utf-8")) if raw else None
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        raise AssertionError(f"GitLab API {method} {path} failed: HTTP {exc.code} {raw}") from exc


def project_path():
    return urllib.parse.quote(LIVE_REPO_PATH, safe="")


def write_live_config(repo, default_branch):
    config = {
        "version": 1,
        "provider": "gitlab",
        "host": LIVE_HOST,
        "apiBaseUrl": LIVE_API_BASE,
        "repoPath": LIVE_REPO_PATH,
        "projectId": LIVE_REPO_PATH,
        "defaultBranch": default_branch,
        "credentialRef": "gitlab://git.arlth.cn/live-test",
        "workflow": {
            "branchMode": "ask",
            "branchPrefix": "issue/",
            "completionMode": "ask",
            "autoClose": "after_merge_or_confirm",
            "commentPolicy": "progress_blocker_done",
        },
    }
    path = repo / ".issue-worker" / "project.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(config, indent=2), encoding="utf-8")


@unittest.skipUnless(os.environ.get("ISSUE_WORKER_LIVE_GITLAB") == "1", "set ISSUE_WORKER_LIVE_GITLAB=1 to run live GitLab tests")
class LiveGitLabIssueTest(unittest.TestCase):
    def setUp(self):
        token = os.environ.get("GITLAB_TOKEN") or os.environ.get("ISSUE_WORKER_LIVE_GITLAB_TOKEN")
        if not token:
            self.skipTest("GITLAB_TOKEN or ISSUE_WORKER_LIVE_GITLAB_TOKEN is required")
        self.token = token
        self.env = {"ISSUE_WORKER_TOKEN": token}
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        git(["init", "-q"], self.repo)
        git(["remote", "add", "origin", LIVE_REPO_REMOTE], self.repo)
        project = gitlab_api("GET", f"/projects/{project_path()}", token)
        self.default_branch = project.get("default_branch") or "main"
        write_live_config(self.repo, self.default_branch)

    def tearDown(self):
        self.tmp.cleanup()

    def test_live_read_issue_flow(self):
        doctor = run_cmd(["doctor"], self.repo, env=self.env)
        self.assertIn("API project lookup succeeded", doctor.stdout)

        listed = run_cmd(["issues", "list", "--state", "all", "--limit", "10", "--json"], self.repo, env=self.env)
        issues = json.loads(listed.stdout)
        self.assertIsInstance(issues, list)
        if not issues:
            return

        issue_id = str(issues[0].get("iid") or issues[0].get("id"))
        got = run_cmd(["issues", "get", issue_id, "--json"], self.repo, env=self.env)
        payload = json.loads(got.stdout)
        self.assertEqual(str(payload["issue"].get("iid") or payload["issue"].get("id")), issue_id)
        self.assertIn("comments", payload)

    @unittest.skipUnless(os.environ.get("ISSUE_WORKER_LIVE_GITLAB_WRITE") == "1", "set ISSUE_WORKER_LIVE_GITLAB_WRITE=1 to run live write tests")
    def test_live_write_comment_branch_and_mr(self):
        stamp = int(time.time())
        marker = f"issue-worker live test {stamp}"
        branch = f"issue-worker-live-{stamp}"
        created = run_cmd(
            [
                "issues",
                "create",
                "--title",
                marker,
                "--body",
                "Temporary issue created by issue-worker live integration test.",
                "--confirm",
                "--json",
            ],
            self.repo,
            env=self.env,
        )
        created_issue = json.loads(created.stdout)
        issue_id = str(created_issue["iid"])
        mr_iid = None

        try:
            comment = run_cmd(["issues", "comment", issue_id, "--body", marker, "--confirm"], self.repo, env=self.env)
            self.assertIn("Comment posted", comment.stdout)

            start = run_cmd(
                [
                    "work",
                    "start",
                    issue_id,
                    "--create-branch",
                    "--branch",
                    branch,
                    "--base",
                    self.default_branch,
                    "--confirm",
                ],
                self.repo,
                env=self.env,
            )
            self.assertIn("Branch created", start.stdout)

            gitlab_api(
                "POST",
                f"/projects/{project_path()}/repository/commits",
                self.token,
                {
                    "branch": branch,
                    "commit_message": marker,
                    "actions": [
                        {
                            "action": "create",
                            "file_path": f".issue-worker-live/{stamp}.txt",
                            "content": marker,
                        }
                    ],
                },
            )

            title = f"issue-worker live test {stamp}"
            body = f"Issue: live test\n\nValidation:\n- live integration test marker: {marker}"
            finish = run_cmd(
                [
                    "work",
                    "finish",
                    issue_id,
                    "--create-pr",
                    "--branch",
                    branch,
                    "--base",
                    self.default_branch,
                    "--title",
                    title,
                    "--body",
                    body,
                    "--confirm",
                ],
                self.repo,
                env=self.env,
            )
            self.assertRegex(finish.stdout, re.compile(r"MR created"))
            match = re.search(r"/merge_requests/(\d+)", finish.stdout)
            if match:
                mr_iid = match.group(1)

            closed = run_cmd(["issues", "close", issue_id, "--confirm"], self.repo, env=self.env)
            self.assertIn("Issue closed", closed.stdout)
            closed_get = run_cmd(["issues", "get", issue_id, "--json"], self.repo, env=self.env)
            closed_payload = json.loads(closed_get.stdout)
            self.assertEqual(closed_payload["issue"].get("state"), "closed")
        finally:
            if mr_iid:
                gitlab_api(
                    "PUT",
                    f"/projects/{project_path()}/merge_requests/{mr_iid}",
                    self.token,
                    {"state_event": "close"},
                )


if __name__ == "__main__":
    unittest.main()
