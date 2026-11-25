# Historical and distributed source identities

The 19 Nov executed source manifest has 130 entries; 127 shared paths match current protected source pins, three differ, and one verification metadata file was added. The recovered original controller confirms `plan()` only changed; `execute()` did not. `config/stages.json` old bytes not recovered; change described by historical stage metadata. The Part 3 preflight path was redacted.

| Path | Historical SHA prefix | 24 Nov SHA prefix | Scope |
|---|---|---|---|
| workflow/continuous.py | 941f2b588458 | 05bce4ccc42f | plan() only (AST diff) |
| config/stages.json | 8c6e5b4be0bf | 1e429fecae8d | stage metadata, original bytes unavailable |
| 03_PART3_SCALABLE_PROCESSING/code/00_preflight_user.py | b084abe87e06 | c76a2f3d27bd | documented private-path redaction |
| config/continuous_verification.json | absent | 7102c1c947c3 | metadata added |

The 799-entry historical manifest is not a current file manifest. 797/799 entries match the available 22 Nov source archive; README and .gitignore differ. The 256 returned-file review is a separate scope. The 25 Nov audit-layer patch to tools/reproduce_development.py rejects duplicate ratios and adds negative controls; scientific producer and original protocol hashes unchanged. Source and full distribution checks must be run on the final release tree, not inferred from prior logs.
