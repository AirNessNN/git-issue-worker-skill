---
name: issue-worker
description: Use this skill proactively when a task involves an issue, GitHub issue, GitLab issue, Gitee issue, extracting requirements from an issue, handling or implementing an issue, replying to an issue, closing an issue, creating a PR or MR for an issue, repository maintenance, open source maintenance workflow, or any work that starts from reading code repository issues and moving them toward completion.
---

# issue-worker

Use this skill when work starts from a repository issue or when the user asks to inspect, implement, reply to, close, or create a PR/MR for an issue on GitHub, GitLab SaaS, self-hosted GitLab, or Gitee.

This skill is cross-agent: it must work for Codex, OpenCode, Claude Code, Cursor, and other agents. Do not rely on private agent tools. Use the bundled `scripts/issue-worker` CLI and ordinary shell/git commands.

## Interaction Language

Use the user's language for all human-facing interaction. Infer it from the user's latest request and the surrounding conversation. Apply it to status updates, questions, blockers, final summaries, issue comments, PR/MR titles, and PR/MR descriptions. Do not default to English unless the user is using English or the repository has an explicit convention that requires English.

Preserve commands, code identifiers, branch names, commit hashes, API fields, and quoted error output in their original form. If the issue tracker content uses a different language from the user, respond in the user's language while quoting exact issue text only when needed.

## First Steps

1. Run from the repository root. Do not assume `issue-worker` is on `PATH`. First try `issue-worker --help`; if it fails with "command not found", always invoke the bundled CLI directly:

   ```bash
   python3 <skill-dir>/scripts/issue-worker <subcommand>
   ```

   When asking the user to run a command, give the exact bundled command form with the real skill path, not only `issue-worker ...`.
2. Check whether `.issue-worker/project.json` exists.
3. If it does not exist, initialize it before asking for issue content:
   - Run `issue-worker init --username <local-or-repo-username>` when the remote lets provider detection succeed.
   - If provider detection needs help, pass explicit options such as `--provider gitlab --api-base-url https://git.arlth.cn/api/v4 --username huhw`.
   - `init` may succeed without a token; it still records non-sensitive project config so future agents know how to continue.
4. Run `issue-worker doctor`.
5. If `doctor` says the token is missing, do not try the web UI or conclude the issue is inaccessible. Configure credentials first:
   - Explain where to create the token for the detected provider/host and the minimum scope: issue reads usually need `read_api` on GitLab, Issues read on GitHub, and issue read permission on Gitee.
   - Give the user a complete local command that hides input and pipes it into the bundled CLI, for example:

     ```bash
     read -rsp 'Issue-worker token: ' ISSUE_WORKER_TOKEN && echo && printf '%s\n' "$ISSUE_WORKER_TOKEN" | python3 /home/airness/.agents/skills/issue-worker/scripts/issue-worker token set --from-stdin; unset ISSUE_WORKER_TOKEN
     ```

   - Tell the user to paste the token into that terminal prompt, not into chat. If the CLI lacks `--from-stdin`, use the bundled `python3 <skill-dir>/scripts/issue-worker token set` command and say it will prompt for hidden input.
6. Check `git status` before editing code. If the worktree contains user changes, do not overwrite them; explain the risk and ask how to proceed.
7. Get issue content through the CLI:
   - If the user provided an id or URL, run `issue-worker issues get <id> --json`.
   - If the user only said "handle the issue", run `issue-worker issues list --state open --limit 20` and pick an obvious single open issue; if multiple issues are plausible, ask which one.
   - Include comments, labels, state, and linked PR/MR information when available.
8. Extract the requirement before implementation: goal, acceptance criteria, risks, unclear points, and likely files or subsystems.

## Recovery When Issue Access Fails

Do not stop after discovering the repository has no local business code or the browser shows a login page. The issue tracker is the source of requirements, so use this recovery order:

1. Ensure `.issue-worker/project.json` exists. If missing, run `issue-worker init` or create it from the git remote with explicit provider/API options.
2. Run `issue-worker doctor` and report the exact failing check.
3. If token is missing, explain token creation and provide a complete local hidden-input setup command using the bundled CLI path. Do not ask the user to paste the token into chat.
4. If token exists but API lookup fails, report provider, host, repo path/project id, endpoint type, HTTP status, and likely cause.
5. Only ask for the issue body or issue link as a fallback after the CLI path is initialized and token/API recovery is blocked.

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

Long-term credentials should use the issue-worker private credentials file first, because system or git credential helpers can trigger confusing interactive password prompts. Credential keys use:

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

The CLI stores tokens in a local private credentials file under the user's config directory, such as `~/.config/issue-worker/credentials.json` on Unix-like systems or the corresponding Windows config directory. Treat that file as machine-private and never commit it.

## Default Workflow

### Prepare

- Run `issue-worker doctor`; if it fails because config or credentials are missing, follow "Recovery When Issue Access Fails" before asking the user for issue text.
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

If the user asked you to implement the issue and branch policy is `ask`, ask a short branch question only if creating a branch is material to the workflow. Otherwise continue on the current branch after noting the policy.

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
  - the user's language for the title text, with an issue reference such as `Fix #{issueId}: {issue title}` when the project convention uses GitHub-style issue references.
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
issue-worker init --provider gitlab --api-base-url https://git.arlth.cn/api/v4 --username huhw
issue-worker doctor
issue-worker token set
issue-worker token test
issue-worker token remove
issue-worker issues list --state open
issue-worker issues list --state open --limit 20 --json
issue-worker issues get 123 --json
issue-worker issues create --title "Bug title" --body "Description" --confirm
issue-worker issues comment 123 --body "进度更新..." --confirm
issue-worker issues close 123 --confirm
issue-worker work start 123
issue-worker work start 123 --create-branch --confirm
issue-worker work finish 123
issue-worker work finish 123 --create-pr --confirm
```

`work start --create-branch` can create a remote branch through the provider API. `work finish --create-pr` can create a GitHub/Gitee PR or GitLab MR through the provider API. Both require confirmation in non-interactive use.

When `issue-worker` is not installed globally, replace `issue-worker` with:

```bash
python3 /home/airness/.agents/skills/issue-worker/scripts/issue-worker
```

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
