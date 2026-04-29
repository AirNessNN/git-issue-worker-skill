# Issue Workflow

This workflow turns a repository issue into implemented, verified, and communicated code changes.

## A. Prepare

1. Run `issue-worker doctor`.
2. Confirm `.issue-worker/project.json` matches the current git remote and repository.
3. Run `git status`.
4. If the worktree has user changes, do not overwrite them. Explain the risk and ask how to proceed.
5. Read the issue:
   - title
   - state
   - labels
   - body
   - comments
   - linked PR/MR where available

## B. Extract Requirements

Summarize:

- issue goal
- acceptance criteria
- constraints and risks
- unclear points
- likely implementation area

If requirements are unclear, ask the user before large code changes. If the user agrees, comment on the issue to request clarification.

## C. Start Work

Use `workflow.branchMode`:

- `always`: create `issue/{issueId}-{short-slug}` from `defaultBranch`.
- `ask`: ask whether to create a branch.
- `never`: work on the current branch and warn about the risk.

Recommended branch name:

```text
issue/{issueId}-{short-slug}
```

Only post a "started work" issue comment when the user confirms or project policy allows it.

The CLI can create the remote branch when the user or policy confirms it:

```bash
issue-worker work start <issueId> --create-branch --confirm
```

## D. Implement

- Follow repository style and existing architecture.
- Make focused changes tied to the issue.
- Do not commit unless the user asks or workflow config explicitly allows it.
- Run targeted tests for the touched behavior.
- Run broader validation when the change affects shared code or public behavior.

If blocked:

1. Explain the blocker in the conversation.
2. Include the evidence: command, error, endpoint, status code, or missing decision.
3. Ask before posting a blocker comment to the issue.
4. Do not close the issue.

## E. Finish

Summarize:

- changed behavior
- touched components
- validation commands
- validation results
- remaining risk

Use `workflow.completionMode`:

- `mr`: create PR/MR when supported and policy/user confirmation permits.
- `direct`: push directly only with explicit confirmation.
- `ask`: ask before push, PR/MR creation, and issue closure.

PR/MR title:

```text
Fix #{issueId}: {issue title}
```

PR/MR body:

- issue link
- requirement summary
- implementation summary
- test results
- `Closes #123` or `Fixes #123` only when the user wants merge-time auto-close

Default rule: do not close the issue before the PR/MR is merged. Close early only when the user explicitly asks.

The CLI can create a PR/MR when the user or policy confirms it:

```bash
issue-worker work finish <issueId> --create-pr --confirm
```

If no PR/MR is created and the work is complete, ask whether to close the issue. Before closing, comment with the completion summary and validation result.

## Communication Style

- Guide new users step by step.
- Explain token setup without requiring API expertise.
- Be direct about risky actions: close issue, push, create PR/MR, merge, delete, or exposed token.
- Report API failures with provider, host, endpoint type, HTTP status, and likely cause.
