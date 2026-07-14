# Contributing

Contributions that improve portability, reliability, tests, or documentation are welcome.

## Rules

- Preserve the explicit confirmation boundary and exactly-once final submission.
- Do not add an unofficial Treatwell scraper, reverse-engineered private API client, CAPTCHA bypass, or credential collection.
- Do not include customer PII, credentials, session cookies, or real booking records in fixtures.
- Keep the core `SKILL.md` compatible with the Agent Skills specification; host-specific extensions belong in references.
- Use semantic browser labels rather than ephemeral element IDs or coordinates.
- Ground claims about Treatwell behavior or terms in current primary sources and include the date checked.

## Checks

```bash
python3 -m compileall -q scripts tests
python3 scripts/validate_skill.py .
python3 -m unittest discover -s tests -v
```

Safe browser verification may reach checkout but must not enter real customer data or activate the final booking action.
