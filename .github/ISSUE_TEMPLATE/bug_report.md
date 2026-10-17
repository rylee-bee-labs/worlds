name: Bug report
description: Something behaves wrong or breaks.
labels: ["bug"]
body:
  - type: markdown
    attributes:
      value: |
        Thanks for taking the time. Do **not** include secrets, tokens,
        personal data, private endpoints or logs from a live deployment.
        Security issues go to [private reporting](https://github.com/rylee-bee-labs/worlds/security/advisories/new) instead.
  - type: textarea
    id: what-happened
    attributes:
      label: What happened?
      description: A clear description of the unexpected behavior.
    validations:
      required: true
  - type: textarea
    id: expected
    attributes:
      label: What did you expect?
    validations:
      required: true
  - type: textarea
    id: reproduction
    attributes:
      label: How can it be reproduced?
      description: Minimal steps or a synthetic reproduction. Redact anything private.
    validations:
      required: true
  - type: textarea
    id: environment
    attributes:
      label: Environment
      description: OS, Python version, uv version, how you are running it (CLI / API / container).
    validations:
      required: true
  - type: textarea
    id: context
    attributes:
      label: Anything else?
      description: Relevant output (sanitized), screenshots, or notes.