/goal

# Task Execution Rules

## Goal

Implement all tasks defined in `docs/usage-fix-plan.md` until fully completed.

Do not stop at partial implementation. Continue until every item in the plan is implemented, verified, and working correctly.

---

## Mandatory Workflow

1. Load memory and project instructions before starting any task.
2. Read and understand the entire `docs/usage-fix-plan.md`.
3. Create an execution plan based on the document.
4. Implement tasks incrementally.
5. Test every completed change.
6. Fix any discovered issues.
7. Re-run tests after fixes.
8. Only mark a task as completed after successful validation.

---

## Validation Requirements

Before declaring any task complete:

* Verify implementation matches requirements.
* Run relevant tests.
* Verify no regressions were introduced.
* Confirm logs show no unexpected errors.
* Confirm application behavior matches expected outcome.

Never assume code works without verification.

---

## Python Execution Rules

When Python execution is required:

* Always use the project's configured Python environment.
* Never rely on system Python unless explicitly required by the project.
* Use the existing project tooling and dependency management.

---

## Memory & User Rules

Before starting implementation:

* Load memory and user-specific instructions.
* Follow all discovered project rules and workflows.

Memory loading is mandatory and must occur before making changes.

---

## Error Escalation Policy

If the same issue, bug, or failing test has been attempted more than 5 times without successful resolution:

1. Stop further retries.
2. Summarize findings.
3. Explain attempted solutions.
4. Ask the user for guidance before continuing.

Do not enter infinite fix loops.

---

## Backend Development Rules

When modifying backend Python code:

* All new functions must use type hints.
* All modified function signatures must use type hints where practical.
* Include parameter types and return types.

Example:

```python
def get_user(user_id: int) -> User:
    ...
```

---

## Docker Rules

Use Docker only when necessary.

Requirements:

* Always use `docker-compose.dev.yml`.
* Prefer existing running containers.
* Assume autoreload is already configured.
* Do not rebuild containers unless required by the task.

Forbidden:

```bash
docker compose down -v
```

or any command that removes database volumes.

Database data must be preserved at all times.

---

## Image Handling Restrictions

Do NOT open, inspect, analyze, or process image files.

The model used for this task does not support image analysis and attempting to read image files may cause task failure.

Ignore image assets unless the user explicitly provides alternative instructions.

---

## Completion Criteria

The task is considered complete only when:

* All items in `docs/usage-fix-plan.md` are implemented.
* Relevant tests pass.
* No known errors remain.
* Validation has been performed.
* Results have been reported to the user.
