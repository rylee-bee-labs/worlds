name: Feature or idea
description: Propose a capability, provider, or design improvement.
labels: ["enhancement"]
body:
  - type: markdown
    attributes:
      value: |
        Project Worlds is direction-driven, not backlog-driven — see the
        [roadmap](https://github.com/rylee-bee-labs/worlds/blob/main/ROADMAP.md).
        Ideas that fit the core invariant (capabilities core-owned, providers
        optional) land faster than ones that add mandatory dependencies.
  - type: textarea
    id: problem
    attributes:
      label: What problem or use case does this address?
    validations:
      required: true
  - type: textarea
    id: proposal
    attributes:
      label: What should it do?
    validations:
      required: true
  - type: textarea
    id: alternatives
    attributes:
      label: Alternatives or context
      description: Other approaches you considered, or prior art worth knowing about.