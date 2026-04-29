---
name: issue-worker
description: Use this skill proactively when a task involves an issue, GitHub issue, GitLab issue, Gitee issue, extracting requirements from an issue, handling or implementing an issue, replying to an issue, closing an issue, creating a PR or MR for an issue, repository maintenance, open source maintenance workflow, or any work that starts from reading code repository issues and moving them toward completion.
---

# issue-worker

Use this skill when work starts from a repository issue or when the user asks to inspect, implement, reply to, close, or create a PR/MR for an issue on GitHub, GitLab SaaS, self-hosted GitLab, or Gitee.

This skill is cross-agent: it must work for Codex, OpenCode, Claude Code, Cursor, and other agents. Do not rely on private agent tools. Use the bundled `scripts/issue-worker` CLI and ordinary shell/git commands.

## First Steps

1. Check whether `.issue-worker/project.json` exists in the repository root.
2. If it does not exist, run or guide the user through `issue-worker init`.
3. If it exists, run `issue-worker doctor`.
4. Check `git status` before editing code. If the worktree contains user changes, do not overwrite them; explain the risk and ask how to proceed.
5. Read the issue before coding:
   - `issue-worker issues get <id>`
   - include comments, labels, state, and any linked PR/MR information when available.
6. Extract the requirement before implementation: goal, acceptance criteria, risks, unclear points, and likely files or subsystems.

Read these references when needed:

- `references/workflow.md` for the issue-to-implementation workflow.
- `references/providers.md` for API differences and adapter behavior.
- `references/token-setup.md` for token creation, storage, testing, and removal.

## Configuration Rules

Project configuration belongs in `.issue-worker/project.json` at the repository root. This file is non-sensitive and may be committed. It records provider, host, API base URL, repo path, default branch, credential reference, and workflow defaults.

Never store tokens in `.issue-worker/project.json`.

Environment variables are only temporary overrides:

- `ISSUE_WORKER_TOKEN`
- `GITHUB_TOKEN`
- `GITLAB_TOKEN`
- `GITEE_TOKEN`

Do not ask users to permanently export provider tokens globally. Users may work with multiple GitHub, GitLab, Gitee, or self-hosted GitLab accounts, and global token exports are ambiguous and risky.

Long-term credentials should use system or git credential storage first. Credential keys use:

```text
{provider}://{host}/{username}
```

Examples:

```text
github://github.com/alice
gitlab://gitlab.com/alice
gitlab://git.arlth.cn/huhw
gitee://gitee.com/alice
```

If git credential storage is unavailable, the CLI may fall back to a local private credentials file under the user's config directory, such as `~/.config/issue-worker/credentials.json` on Unix-like systems or the corresponding Windows config directory. Treat that file as machine-private and never commit it.

## Default Workflow

### Prepare

- Run `issue-worker doctor`.
- Confirm the current git repository matches `.issue-worker/project.json`.
- Inspect `git status`.
- Read the issue title, description, comments, labels, and linked PR/MR details where supported.

### Extract Requirements

- Summarize the issue goal, acceptance criteria, risks, and unclear questions.
- If the issue is unclear, ask the user before making large changes.
- If the user allows it, comment on the issue to request clarification.

### Start Work

Follow `workflow.branchMode` from `.issue-worker/project.json`:

- `always`: create a branch from `defaultBranch` named `issue/{issueId}-{short-slug}`.
- `ask`: ask the user before creating the branch.
- `never`: work on the current branch, but warn about the risk.

Ask before posting a "started work" comment unless project workflow policy explicitly allows it.

### Implement

- Follow the repository's existing style and architecture.
- Do not commit unless the user asks or project workflow configuration explicitly permits it.
- Run targeted validation first, then broader checks when the change has wider impact.
- If blocked, report the blocker in the conversation. Only comment the blocker on the issue if the user agrees. Do not close blocked issues.

### Finish

- Summarize code changes, validation commands, and results.
- Follow `workflow.completionMode`:
  - `mr`: create a PR/MR when supported and confirmed by policy.
  - `direct`: direct push only with explicit confirmation.
  - `ask`: ask before pushing, opening PR/MR, or closing the issue.
- PR/MR titles should use:
  - `Fix #{issueId}: {issue title}` for GitHub-style issue references.
  - an equivalent GitLab/Gitee reference when appropriate.
- PR/MR descriptions should include issue link, requirement summary, implementation summary, test results, and a `Closes`/`Fixes` statement only when the user wants merge-time auto-close.
- Do not close an issue before the PR/MR is merged unless the user explicitly asks.
- Before closing an issue, comment with the completion summary and validation result.

## Safety Rules

- Never print, log, comment, or include tokens in PR/MR descriptions.
- Never write tokens into `.issue-worker/project.json`.
- Never put tokens in shell history.
- If a user pastes a token into chat, warn that it is exposed and recommend revoking and regenerating it.
- Before any API write operation, verify target provider, host, repo/project, and issue id.
- Closing, deleting, merging, pushing to a main branch, and direct production-like changes require user confirmation unless the project configuration explicitly permits them.
- For API failures, report platform, host, endpoint type, HTTP status code, and likely causes.
- For 404, distinguish project not found, missing permission, GitLab private project hidden as 404, and URL-encoding mistakes for GitLab project paths.
- For 401/403, suggest expired token or insufficient token scopes.

## CLI Quick Reference

Use the CLI from the skill directory or put `issue-worker/scripts` on `PATH`.

```bash
issue-worker init
issue-worker doctor
issue-worker token set
issue-worker token test
issue-worker token remove
issue-worker issues list --state open
issue-worker issues get 123
issue-worker issues create --title "Bug title" --body "Description" --confirm
issue-worker issues comment 123 --body "Status update..."
issue-worker issues close 123 --confirm
issue-worker work start 123
issue-worker work start 123 --create-branch --confirm
issue-worker work finish 123
issue-worker work finish 123 --create-pr --confirm
```

`work start --create-branch` can create a remote branch through the provider API. `work finish --create-pr` can create a GitHub/Gitee PR or GitLab MR through the provider API. Both require confirmation in non-interactive use.

## Validation

Run local tests before publishing changes:

```bash
PYTHONPYCACHEPREFIX=/tmp/issue-worker-pycache python3 -m unittest discover -s issue-worker/tests -p 'test_*.py' -v
```

The live GitLab test fixture uses `git@git.arlth.cn:huhw/issue-test.git` and `https://git.arlth.cn/api/v4`. Run it only with a token supplied from a secure local environment:

```bash
ISSUE_WORKER_LIVE_GITLAB=1 python3 -m unittest issue-worker/tests/live_gitlab_issue_test.py -v
ISSUE_WORKER_LIVE_GITLAB=1 ISSUE_WORKER_LIVE_GITLAB_WRITE=1 python3 -m unittest issue-worker/tests/live_gitlab_issue_test.py -v
```

The live write test creates a temporary issue, comments on it, creates a branch, creates an MR, closes the issue, and attempts to close the test MR.
