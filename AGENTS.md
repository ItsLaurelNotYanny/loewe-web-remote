# Project Instructions

English | [简体中文](AGENTS_cn.md)

## Stack and design

Use README.md and Cargo.toml as the current design/build references. This project
has two alternative backends: Rust/Cargo and standard-library Python 3. Keep
Python HTML_CONTENT and static/index.html identical. Preserve the frontend's ES5
compatibility for BlackBerry Passport; Node syntax checking alone does not prove it.

## Project gate

<!-- project-gate:start -->
Choose author/reviewer from the current task, not the agent product name.
Authors run `./check.sh --fast` before committing and `./check.sh` before review
submission or handoff. Fix diagnostic causes and re-run; never weaken checks to
pass. Reviewers run `./check.sh` on the exact review target before inspecting the
code diff; on failure return the diagnostic and stop without repairing source.
Missing gate blocks review. Relevant edits invalidate a previous pass.
Run `./scripts/install-hooks.sh` on first author use of each clone. When the stack
changes, update checks using project-gate and preserve custom checks. Hooks require
all nonignored source changes to be staged for commit and a clean HEAD for push;
partial staging or pushing another ref requires an explicit snapshot-aware adaptation.
<!-- project-gate:end -->

## Validation scope

Fast checks cover shell syntax, changed-line whitespace, rustfmt, offline locked
Cargo build/type checking, Clippy with warnings denied, Python syntax/indentation,
page-copy equality, and inline JavaScript syntax. Full adds discovered, nonempty
Rust and Python test suites. Tests use mocks/local loopback; never use a real TV
for mechanical checks. Dependencies must be provisioned before the offline gate. Gate artifacts use
`target/project-gate` rather than temporary reviewer build outputs.
Python formatting beyond indentation, Python type checking, ES5 parsing, sanitizers,
audits, and real-device/browser validation are not configured checks.

## Review records and language

Follow CODE_REVIEW.md's stable finding IDs, fix-commit records, independent closure,
and three-round milestone limit. Keep the English/Chinese review reports synchronized.
Write new code/comments/logs in English. Documentation uses `.md` / `_cn.md` pairs
with language-switch links and synchronized content.

- During development and review, read English documentation as the primary working source; do not also load a Chinese translation containing the same information. Chinese versions are for human readers and remain complete and synchronized. Read Chinese only when explicitly requested, when the user supplies or writes Chinese input without an English counterpart, or when editing/checking the relevant translation sections. Do not read both synchronized versions to look for additional information. Conversation language follows the user's preference.

## Continuous review discipline

- After every review, update both `CODE_REVIEW.md` and `CODE_REVIEW_cn.md` with the exact reviewed commit, gate evidence, stable finding IDs, repair directions, and acceptance criteria. Commit the reports before declaring the handoff complete.
- While the review watch is active, check the current local branch for new commits every 15 minutes after the review-report commit. If remote tracking is configured, fetch it without merging, rebasing, resetting, or changing the author's working tree. Remote submissions must be reviewed in an isolated clean checkout.
- For a new code submission, independently run the full project gate on its exact clean commit before inspecting its diff. A gate failure or missing gate stops that review; record the bounded diagnostic without repairing the author's code.
- Distinguish implementation submissions from reviewer report/policy commits. A report-only commit is not a new repair attempt and must not trigger a review loop of the reviewer's own output.
- Track failed repair rounds by finding ID and submitted commit. If the same finding remains unresolved after two consecutive repair submissions, explicitly flag it in both reports and the user update, listing both commits, the reproduced failure, and the unmet acceptance criteria. Do not count the initial discovery, an unchanged polling result, a gate-only blockage, or a report-only commit as a failed repair round.
- Continue the watch after approval so later submissions are detected, until the user stops it. Persist the last observed/reviewed commit and next check time for recovery; if execution is interrupted, resume from that checkpoint and do not claim checks occurred during the interruption.
- This rule does not authorize publishing reviews or sending messages through external services. The shared repository reports and this chat are the handoff channels unless the user authorizes another channel.
