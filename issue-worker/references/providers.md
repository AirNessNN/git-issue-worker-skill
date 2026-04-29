# Provider Reference

The issue-worker CLI supports GitHub, GitLab SaaS, self-hosted GitLab, and Gitee. Do not assume their APIs are interchangeable. Keep provider-specific behavior inside adapters.

## Unified Adapter Capabilities

Adapters should expose these conceptual operations:

- `detectProvider(remoteUrl)`
- `getProject()`
- `listIssues(state, labels, assignee)`
- `getIssue(id)`
- `listComments(id)`
- `createIssue(title, body, labels)`
- `createComment(id, body)`
- `updateIssueState(id, state)`
- `createBranch(base, branch)`
- `createPullOrMergeRequest(branch, base, title, body)`
- `linkIssueToPR(issue, pr)`
- `closeIssue(id)`

The CLI implements provider detection, project lookup, issue list/get/comment/close, token testing, remote branch creation, and PR/MR creation.

CLI-facing issue state values are normalized across providers:

- `open`
- `closed`
- `all`

Adapters translate those values before calling provider APIs. For example, GitLab receives `opened` when the user or agent passes `--state open`. Provider-specific values such as GitLab `opened` are also accepted for compatibility, but agent workflows should prefer normalized values.

## GitHub

- SaaS API base: `https://api.github.com`
- Repository id: `owner/repo`
- Issue id: issue `number`
- Authentication: `Authorization: Bearer <token>` plus standard GitHub API headers.
- List issues: `GET /repos/{owner}/{repo}/issues`
- Create issue: `POST /repos/{owner}/{repo}/issues`
- Get issue: `GET /repos/{owner}/{repo}/issues/{issue_number}`
- Comments: `GET/POST /repos/{owner}/{repo}/issues/{issue_number}/comments`
- Close issue: `PATCH /repos/{owner}/{repo}/issues/{issue_number}` with `{"state":"closed"}`
- Pull requests are also issues for conversation purposes, but PR creation/management uses the pulls API.
- Auto-close can be done by including `Fixes #123` or `Closes #123` in the PR description when the user wants merge-time closure.

Fine-grained PAT scopes depend on operation:

- Read issues: repository Issues read.
- Comment/close: repository Issues write.
- Create PR: Pull requests write, usually Contents write for branch pushes.

## GitLab SaaS And Self-Hosted GitLab

- SaaS API base: `https://gitlab.com/api/v4`
- Self-hosted API base: `https://{host}/api/v4`
- Project id can be numeric `project_id` or URL-encoded `namespace/project`.
- Issue id in project endpoints is issue `iid`, not global `id`.
- Comments are called notes.
- Merge requests are MRs.
- Authentication: `PRIVATE-TOKEN: <token>` or `Authorization: Bearer <token>`. The CLI uses `PRIVATE-TOKEN`.
- List issues: `GET /projects/{project_id}/issues`
- Create issue: `POST /projects/{project_id}/issues`
- Get issue: `GET /projects/{project_id}/issues/{issue_iid}`
- Comments: `GET/POST /projects/{project_id}/issues/{issue_iid}/notes`
- Close issue: `PUT /projects/{project_id}/issues/{issue_iid}` with `state_event=close`
- Auto-close can be done by including `Closes #123` in an MR description when the user wants merge-time closure.

For private GitLab projects, 404 can mean the project exists but the token lacks permission. Also check whether `namespace/project` was URL-encoded correctly when using a path instead of a numeric project id.

## Gitee

- API base: `https://gitee.com/api/v5`
- Repository id: `owner/repo`
- Issue id may be a string issue number.
- Pull requests are called Pull Requests.
- Authentication differs from GitHub/GitLab. Gitee commonly accepts `access_token` in query/body parameters; adapters must handle this separately and avoid logging URLs containing tokens.
- List issues: `GET /repos/{owner}/{repo}/issues`
- Create issue: `POST /repos/{owner}/{repo}/issues`
- Get issue: `GET /repos/{owner}/{repo}/issues/{number}`
- Comments: `GET/POST /repos/{owner}/{repo}/issues/{number}/comments`
- Close issue: use the Gitee issue update endpoint with the provider-specific state value. The CLI sends a conservative close request and reports provider errors clearly.

Because token placement can affect logs, never print full Gitee request URLs when a token is in query parameters.

Gitee endpoints vary more across product/version than GitHub/GitLab. Treat Gitee branch, PR, and close operations as provider-sensitive and verify errors from the API before assuming a permissions problem.

## Provider Detection

Detection starts from the git remote URL:

- `github.com` -> `github`
- `gitlab.com` -> `gitlab`
- `gitee.com` -> `gitee`
- any other host -> probe `https://{host}/api/v4/version` to detect self-hosted GitLab

If the host cannot be detected, ask the user for the provider and API base URL.

Remote URL parsing must support:

- HTTPS: `https://github.com/owner/repo.git`
- SSH scp-like: `git@github.com:owner/repo.git`
- SSH URL: `ssh://git@gitlab.example.com/group/project.git`

Strip a trailing `.git` from repo paths.

## Error Reporting

When an API call fails, report:

- provider
- host
- endpoint type, such as project lookup, issue get, comment create, or issue close
- HTTP status code
- short response message when safe
- likely causes
- provider-supported values or a retry suggestion when the failure is a known argument compatibility problem

Common interpretations:

- 401: token missing, expired, malformed, or unsupported auth mode.
- 403: token lacks scope, account lacks project permission, or provider policy blocks the request.
- 404: wrong repo/project path, missing permission, private GitLab project hidden as not found, or GitLab URL encoding error.
- 422: invalid state transition, duplicate resource, bad labels, or validation error.
- 429: rate limit.

## Branch And PR/MR Interface

Branch and PR/MR support uses the same config and token model:

- create a branch from `defaultBranch`
- push only after user confirmation or explicit workflow policy
- create PR/MR with issue link, summary, implementation notes, and tests
- include `Closes`/`Fixes` only when merge-time issue closure is desired
- never close the issue immediately just because a PR/MR was opened

CLI commands:

```bash
issue-worker work start <id> --create-branch --confirm
issue-worker work finish <id> --create-pr --confirm
```

Add `--json` to workflow commands when an agent needs stable result fields instead of human guidance text.
