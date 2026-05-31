# BDD Specs — Branch Strategy

## Feature: Create feature branches from Linear issues

### Scenario: All 14 feature branches exist

```gherkin
Given the repository is on branch "main"
When all feature branches are created
Then the following branches should exist:
  | branch                              | issue  |
  | feature/ZEN-28-fastapi-skeleton     | ZEN-28 |
  | feature/ZEN-29-feishu-repo-layer    | ZEN-29 |
  | feature/ZEN-30-pipeline-worker-loop | ZEN-30 |
  | feature/ZEN-31-frontend-shell       | ZEN-31 |
  | feature/ZEN-32-opencli-adapter      | ZEN-32 |
  | feature/ZEN-33-hotspot-agents       | ZEN-33 |
  | feature/ZEN-34-hotspots-ui          | ZEN-34 |
  | feature/ZEN-35-analysis-agents      | ZEN-35 |
  | feature/ZEN-36-title-cover-agents   | ZEN-36 |
  | feature/ZEN-37-approval-ui          | ZEN-37 |
  | feature/ZEN-38-book-creation        | ZEN-38 |
  | feature/ZEN-39-minibible-briefs     | ZEN-39 |
  | feature/ZEN-40-chapter-agents       | ZEN-40 |
  | feature/ZEN-41-review-desk-ui       | ZEN-41 |
```

### Scenario: Branches are based on main

```gherkin
Given a feature branch "feature/ZEN-28-fastapi-skeleton"
When I compare it with "main"
Then the branch should have the same commit as main HEAD
And the branch should be trackable with "git branch -vv"
```

### Scenario: Linear issue branch names are preserved

```gherkin
Given Linear provides suggested branch names
When I check the Linear issue ZEN-28
Then the gitBranchName field should be "y1327514070/zen-28-initialize-backend-fastapi-harness-skeleton"
And our local branch "feature/ZEN-28-fastapi-skeleton" maps to the same issue
```

### Scenario: Dependency chain is respected during development

```gherkin
Given the dependency chain ZEN-28 → ZEN-29 → ZEN-30
When developing ZEN-29
Then ZEN-28 should be completed and merged to main first
When developing ZEN-30
Then both ZEN-28 and ZEN-29 should be completed and merged to main first
```
