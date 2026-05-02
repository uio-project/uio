---
name: review-and-fix
description: Review a pull request and open a fix branch if blockers are found.
steps:
  - name: review
    agent: reviewer
    arg: "{{ input }}"
    output: review_result

  - name: fix
    agent: coder
    arg: "{{ input }}"
    when: "review_result contains BLOCKER"
---

# Workflow: review-and-fix

This workflow demonstrates agent chaining with a conditional step.

**Step 1 — review:** Runs the `reviewer` agent against the pull request reference
passed as `{{ input }}` (e.g. `owner/repo#42`). The reviewer's final response is
stored in `review_result`.

**Step 2 — fix (conditional):** Runs the `coder` agent with the same PR reference,
but only when `review_result` contains the word `BLOCKER`. If the review is clean
the step is skipped and the workflow exits cleanly.

Run this workflow with:

```
uio workflow run review-and-fix "owner/repo#42"
```
