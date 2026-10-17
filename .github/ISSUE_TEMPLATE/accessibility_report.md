name: Accessibility report
description: Report an accessibility barrier — contrast, motion, targets, screen readers, reading load.
labels: ["accessibility"]
body:
  - type: markdown
    attributes:
      value: |
        Accessibility is a core contract of this project, not an
        afterthought — reports like this one are how it stays true.
        The contract lives in
        [ACCESSIBILITY_CONTRACT.md](https://github.com/rylee-bee-labs/worlds/blob/main/docs/accessibility/ACCESSIBILITY_CONTRACT.md).
        Do not include secrets or personal data.
  - type: textarea
    id: barrier
    attributes:
      label: What barrier did you hit?
      description: What you were doing, what you expected, and what happened instead.
    validations:
      required: true
  - type: textarea
    id: impact
    attributes:
      label: Who does it affect?
      description: Assistive tech used (screen reader, magnification, reduced motion, high contrast), or the user group affected.
    validations:
      required: true
  - type: textarea
    id: location
    attributes:
      label: Where?
      description: CLI command, API route, dashboard screen, or document. Be as specific as you can.
    validations:
      required: true