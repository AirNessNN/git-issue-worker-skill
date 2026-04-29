# issue-worker skill

`issue-worker` 是一个面向代码仓库 Issue 工作流的 agent skill。它帮助 AI agent 从 GitHub、GitLab、私有 GitLab 或 Gitee 的 Issue 出发，读取需求、梳理验收标准、实施代码变更、运行验证，并准备 Issue 评论或 PR/MR 后续说明。

## 使用 skills 安装

[`skills` CLI](https://skills.sh/docs/cli) 可以直接通过 `npx` 运行，不需要提前单独安装。

先预览这个仓库中可安装的 skill：

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --list
```

也可以使用 GitHub 镜像：

```bash
npx skills add https://github.com/AirNessNN/git-issue-worker-skill.git --list
```

安装 `issue-worker` 到当前项目：

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --skill issue-worker
```

使用 GitHub 源安装：

```bash
npx skills add https://github.com/AirNessNN/git-issue-worker-skill.git --skill issue-worker
```

安装到当前用户的全局 skill：

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --skill issue-worker --global
```

或从 GitHub 安装到全局：

```bash
npx skills add https://github.com/AirNessNN/git-issue-worker-skill.git --skill issue-worker --global
```

为所有支持的 agent 全局安装，并跳过确认提示：

```bash
npx skills add https://gitee.com/airnessnn/git-issue-worker-skill.git --global --all
```

GitHub 源对应命令：

```bash
npx skills add https://github.com/AirNessNN/git-issue-worker-skill.git --global --all
```

安装完成后，在处理仓库 Issue 时告诉 agent 使用 `issue-worker` skill，例如：

```text
使用 issue-worker 查看 123 号 Issue 并完成实现。
```

## 更新

当本仓库有更新后，更新当前项目中的 skill：

```bash
npx skills update issue-worker
```

如果是全局安装，使用：

```bash
npx skills update issue-worker --global
```

## 移除

从当前项目移除：

```bash
npx skills remove issue-worker
```

移除全局安装：

```bash
npx skills remove issue-worker --global
```

## 交互语言

`issue-worker` 要求 agent 在与用户交互时跟随用户使用的语言，不会固定使用英语。Issue 评论、PR/MR 标题与描述、进度说明、阻塞说明、完成总结等面向人的文本，也应优先使用用户当前会话中的语言；命令、代码标识符、错误原文和平台保留字段保持原样。

## 常用参数

- `--skill issue-worker`：只安装这个仓库中的 `issue-worker` skill。
- `--global`：安装到用户级别，而不是当前项目。
- `--agent <agent>`：只安装到指定 agent；使用 `--agent '*'` 可指定所有支持的 agent。
- `--all`：等价于 `--skill '*' --agent '*' -y`，用于安装全部 skill 到全部支持的 agent 并跳过确认。
- `DISABLE_TELEMETRY=1`：运行 `skills` 前设置该环境变量，可关闭 CLI 遥测。
