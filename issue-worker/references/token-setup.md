# Token Setup

Tokens are sensitive local credentials. Do not paste them into chat, issue comments, logs, commit messages, or PR/MR descriptions.

Environment variables are temporary overrides only:

- `ISSUE_WORKER_TOKEN`
- `GITHUB_TOKEN`
- `GITLAB_TOKEN`
- `GITEE_TOKEN`

Do not use global long-term exports such as `export GITLAB_TOKEN=...` as the normal setup. A user may have multiple GitHub, GitLab, Gitee, or self-hosted GitLab accounts.

## Credential Keys

Long-term credentials should be stored by provider, host, and username:

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

Project config stores only the reference:

```json
{
  "credentialRef": "gitlab://git.arlth.cn/huhw"
}
```

It must never store the token.

## Commands

If `issue-worker` is not on `PATH`, replace it with the bundled command:

```bash
python3 /home/airness/.agents/skills/issue-worker/scripts/issue-worker
```

Set a token without echoing it:

```bash
issue-worker token set
```

For a user-facing setup instruction, prefer this one-liner because it works even when the CLI is not on `PATH` and keeps the token out of chat:

```bash
read -rsp 'Issue-worker token: ' ISSUE_WORKER_TOKEN && echo && printf '%s\n' "$ISSUE_WORKER_TOKEN" | python3 /home/airness/.agents/skills/issue-worker/scripts/issue-worker token set --from-stdin; unset ISSUE_WORKER_TOKEN
```

Test a saved token:

```bash
issue-worker token test
```

Remove a saved token:

```bash
issue-worker token remove
```

The CLI first tries `git credential` for storage. If that is unavailable, it falls back to a local credentials file:

- Linux/macOS: `~/.config/issue-worker/credentials.json`
- Windows: `%APPDATA%\issue-worker\credentials.json` when `APPDATA` is available, otherwise the user's home config path

The fallback file is machine-private. Keep permissions restricted and never commit it.

## GitHub Token

Prefer a fine-grained Personal Access Token.

Create it at:

```text
https://github.com/settings/personal-access-tokens/new
```

Minimum permissions depend on the task:

- Read issues: repository Issues read.
- Comment or close issues: repository Issues write.
- Create PR: Pull requests write.
- Push branches or modify code through the API: Contents write.

Use the smallest repository scope possible. If a token was pasted into chat or logs, revoke it and create a new one.

## GitLab Token

For GitLab SaaS or self-hosted GitLab, create a Personal Access Token from the target account.

Create it at:

```text
https://{gitlab-host}/-/user_settings/personal_access_tokens
```

For example:

```text
https://git.arlth.cn/-/user_settings/personal_access_tokens
```

Common permissions:

- Read project and issue data: `read_api`.
- Comment, close issues, create MRs, and broader write actions: usually `api`.

Some self-hosted GitLab instances customize permissions or token policies. If `read_api` fails for issue reads, check the instance's access rules.

## Gitee Token

Create a Gitee private token from account settings.

Create it at:

```text
https://gitee.com/profile/personal_access_tokens
```

Grant only the permissions required for the workflow:

- issue read/write for issue operations
- pull request permission for PR creation
- repo permission for branch or repository operations when needed

Gitee token transport differs from GitHub and GitLab. The adapter must avoid printing request URLs that include `access_token`.

## Testing And Troubleshooting

Run:

```bash
issue-worker doctor
issue-worker token test
```

Interpretation:

- 401: token missing, expired, revoked, malformed, or wrong auth mechanism.
- 403: token lacks scope or account lacks project permission.
- 404: wrong project path, private project hidden by permissions, or GitLab project path URL encoding issue.

If using a self-hosted GitLab, confirm:

- `apiBaseUrl` is correct, usually `https://{host}/api/v4`
- the token belongs to a user who can access the project
- `projectId` is either numeric or correctly URL encoded when passed to the API
