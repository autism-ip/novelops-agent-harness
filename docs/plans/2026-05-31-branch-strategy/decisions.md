# Decisions — Branch Strategy

## D1: Branch naming convention

**Decision**: `feature/ZEN-{n}-{short-slug}`

**Rationale**:
- `feature/` prefix clearly indicates branch purpose
- `ZEN-{n}` maps directly to Linear issue ID for traceability
- Short slug is human-readable and grep-friendly
- Avoids Linear's longer auto-generated names (`y1327514070/zen-28-...`)

**Trade-off**: Local branch names diverge from Linear's `gitBranchName` field.
Acceptable because the ZEN ID provides the mapping.

## D2: One branch per issue vs per milestone

**Decision**: One branch per issue (14 branches)

**Rationale**:
- Each PR maps to exactly one Linear issue
- Review scope is bounded and focused
- Parallel development is possible within milestones
- Merge conflicts are minimized

## D3: Branch source

**Decision**: All branches created from `main` HEAD

**Rationale**:
- Clean starting point
- No inter-branch dependency at branch creation time
- Dependency chain is enforced at merge time, not creation time
- Allows branches to be developed in any order if needed

## D4: PR merge strategy

**Decision**: Merge branches to `main` in dependency order

**Rationale**:
- `main` stays green
- Each merge builds on the previous
- Dependency chain naturally enforced
- Recommended order: ZEN-28 → ZEN-29 → ZEN-30 → ZEN-31/ZEN-32 (parallel) → ...
