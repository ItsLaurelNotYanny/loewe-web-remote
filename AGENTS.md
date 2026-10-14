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
