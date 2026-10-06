# Runtime Contract

This document defines the minimum runtime assumptions used by the hidden autograding checks for
the `2793` continuous assessment repository.

## Scope

These checks are an objective baseline only. They do not replace manual grading of:

- architecture reasoning
- documentation quality
- trade-off judgment
- technical defense
- integrity review

## Required root files

The repository must contain:

- `README.md`
- `requirements.txt`
- `.env.example`

By the end of `F1`, the repository must also contain:

- `manage.py`

## Required install path

Your repository must install successfully with:

```bash
pip install -r requirements.txt
```

## Required Django bootstrap path

By the end of `F1`, the repository must support:

```bash
python manage.py check
python manage.py migrate --noinput
```

The hidden checks assume `manage.py` sets `DJANGO_SETTINGS_MODULE` correctly for local execution.

## Required environment behavior

Your project must run with a local `.env` created from `.env.example`.

The hidden checks do not require production credentials. They expect the project to work with a
local SQLite or similarly lightweight development configuration.

## Milestone-tag grading

This repository is graded by Classroom 50, not GitHub Classroom. You accept the assignment once
and keep working on the same repository through all three stages -- there is no separate branch
or Pull Request per stage.

Grading is triggered by pushing a milestone tag, not by every push:

```bash
git tag f1
git push origin f1
```

The three recognised milestone tags are `f1`, `f2`, and `summative`, pushed in that order as you
complete each stage. Pushing a tag grades the commit it points at and publishes a Release carrying
the result. Work on `main` (or your own branches, merged back before you tag) however you like --
the tag is what matters, not the branch.

A single long-lived Feedback pull request is opened automatically when you accept the assignment.
Its base never moves, so it always shows the full diff from your starting point to your latest
work. Post a comment on it at each milestone using the template in
`.github/pull_request_template.md`.
