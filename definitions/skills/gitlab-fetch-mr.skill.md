---
name: gitlab-fetch-mr
description: Fetch MR metadata and full diff from a GitLab merge request.
---

# Skill: gitlab-fetch-mr

## Input

- `project` — GitLab project path (`namespace/project`) containing the merge request (required)
- `mr-iid` — merge request IID (project-scoped number) to fetch (required)

## Output

Structured MR data made available to the calling agent:

- `$mr_title` — merge request title
- `$mr_body` — merge request description body
- `$mr_author` — username of the MR author
- `$mr_target_branch` — target branch name (branch the MR will be merged into)
- `$mr_source_branch` — source branch name (branch containing the changes)
- `$mr_files` — list of changed files with additions and deletions per file
- `$mr_additions` — total lines added
- `$mr_deletions` — total lines deleted
- `$mr_diff` — full unified diff of all changes

## Steps

### 1. Fetch MR metadata

Use the GitLab MCP tool if available:

```
mcp__gitlab__get_merge_request  project=<project>  mr_iid=<mr-iid>
```

Fall back to the `glab` CLI when unavailable:

```bash
glab mr view <mr-iid> --repo <project> --output json
```

### 2. Fetch the full diff

Use the GitLab MCP tool if available:

```
mcp__gitlab__get_merge_request_diff  project=<project>  mr_iid=<mr-iid>
```

Fall back to the `glab` CLI when unavailable:

```bash
glab mr diff <mr-iid> --repo <project>
```

For large MRs (>500 lines changed), focus on:
1. New or modified functions and their signatures
2. Error handling paths
3. Security-sensitive code (auth, input validation, SQL, shell commands)
4. Configuration and environment variable changes

### 3. Return structured data

Expose the fetched data as the output variables listed above for the calling agent.
Stop and report an error if the MR does not exist or the request fails.
If the diff is empty, report that the MR has no changes and stop.
