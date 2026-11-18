# Branching Strategy & Workflow: LoanTrack

## 1. Branching Model Followed
For this assignment, we adopted a variant of the **Git Flow** branching model structured around:
- **`main`**: The production branch. Always deployable, stable, and tagged with version releases (`v1.0.0` for Docker Compose release, `v1.1.0` for Kubernetes release).
- **`develop`**: The integration branch where completed features converge before tagging and release to `main`.
- **`feature/*`**: Short-lived branches created off `develop` (e.g., `feature/app-tier`, `feature/docker-compose`, `feature/kubernetes-workloads`).

### Merge & Review Rules
1. **No direct commits** to `main` or `develop`. All changes enter through Pull Requests (PRs).
2. Each PR targets `develop` (or `main` during release integration), contains a descriptive summary of changes, and includes explicit self-review comments on critical diff points (e.g., security, probe thresholds, cache layer boundaries).
3. Commit messages adhere to structured conventional commit guidelines (e.g., `feat(backend): add readiness probe and retry backoff`), avoiding generic messages like `update`, `fix`, or `wip`.

---

## 2. Would I Recommend This Model to a Team of Five Shipping Daily?

**Short answer: No, I would not recommend classic Git Flow for a 5-person team shipping daily.**

### Why Git Flow Fails High-Velocity Small Teams
1. **Integration Friction & Merge Debt**: When 5 engineers merge multiple times a day into `develop`, `develop` becomes an unstable staging ground. Changes sit unreleased, increasing drift between `develop` and `main`, leading to painful merge conflicts and "works on `develop` but breaks on `main`" surprises.
2. **Release Overhead**: Managing separate `develop` and `main` branches creates duplicate PR cycles (feature -> `develop`, then `develop` -> `main`), adding administrative overhead without adding quality for a small team.
3. **Incompatible with Continuous Deployment (CD)**: Daily shipping requires that every merged change can immediately flow through automated CI/CD pipelines to staging or production. Having a separate integration branch delays customer feedback.

### Recommended Alternative: Trunk-Based Development (TBD)
For a 5-engineer team shipping daily, I strongly recommend **Trunk-Based Development** paired with **Feature Flags**:
- **Single Source of Truth (`main`)**: All developers branch directly from `main` into short-lived branches (living < 24 hours).
- **Small, Frequent Merges**: Engineers merge 1–2 small PRs per day directly into `main` after passing automated test suites and peer code reviews.
- **Feature Flags / Dark Launches**: Incomplete features or breaking changes are toggled off via runtime configuration rather than held hostage on long-running branches.
- **Fast Feedback Loop**: Continuous Integration runs against `main`, guaranteeing that trunk is continuously green and instantly deployable to production.
