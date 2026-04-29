# issue-worker skill

`issue-worker` is an agent skill for working from repository issues. It helps agents read GitHub, GitLab, self-hosted GitLab, or Gitee issues, extract requirements, implement changes, validate them, and prepare issue comments or PR/MR follow-up.

## Install with skills

The [`skills` CLI](https://skills.sh/docs/cli) can run through `npx`, so no separate installation is required.

Preview the skill published by this repository:

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --list
```

Install `issue-worker` for the current project:

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --skill issue-worker
```

Install it globally for your user account:

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --skill issue-worker --global
```

Install it for all supported agents without prompts:

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --global --all
```

After installation, ask your agent to use the `issue-worker` skill when handling repository issues, for example:

```text
Use issue-worker to inspect issue 123 and implement it.
```

## Update

Update the installed skill when this repository changes:

```bash
npx skills update issue-worker
```

For global installations:

```bash
npx skills update issue-worker --global
```

## Remove

Remove the skill from the current project:

```bash
npx skills remove issue-worker
```

Remove a global installation:

```bash
npx skills remove issue-worker --global
```

## Notes

- `--skill issue-worker` selects only this skill from the repository.
- `--global` installs at user level instead of project level.
- `--agent <agent>` can target specific agents; use `--agent '*'` for all supported agents.
- Set `DISABLE_TELEMETRY=1` before running `skills` if you want to opt out of CLI telemetry.
