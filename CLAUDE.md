# Better Crafty

A fork of Crafty Controller 4.11.0: Python Tornado + peewee/SQLite back end,
jQuery + Bootstrap 4 + bootbox front end. **Read `handoff.md` first.** It
records everything done so far, what is unfinished, the owner's open
questions, and how to set up and test on any machine.

## Working rules (from the owner)

- Work on branch `claude/login-server-admin-improvements-ctbqdu`; it is the
  only branch and the repo default. Push with
  `git push -u origin claude/login-server-admin-improvements-ctbqdu`.
- Do not open a pull request unless the owner asks for one.
- Subagents use far more of the owner's usage than expected: use them
  sparingly.
- Keep status updates short and plain.
- Never ask the owner to paste a password or token into the chat.
- After each piece of work, update `handoff.md`: the owner's request in
  their words, a section for the session, and a row in the commits table.

## Before every commit

- `black --check app tests main.py` and `pylint app tests main.py` (must be
  clean: GitHub Actions fails the build otherwise).
- `pytest -q tests` (171 pass).
- `node dev/command-data/test_complete.js` after touching command
  suggestions.
- For UI changes, the browser checks in `dev/handoff-tools/` (see
  "Development setup" in `handoff.md`), and look at the page at phone width.

## Gotchas

- Tornado templates: never split a `{{ }}` or `{% %}` across lines.
  Templates are cached, so restart Crafty after changing one.
- Put values into HTML strings only through `escapeHtml()` (`misc.js`),
  bootbox titles and messages included.
- Translations: only `app/translations/en_EN.json` is updated. Edit it with
  Python's `json` (indent 4, `ensure_ascii=False`, trailing newline).
