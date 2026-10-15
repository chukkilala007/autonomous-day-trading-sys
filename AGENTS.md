# Working on this repository

Read `docs/implementation-plan.md` before implementation. It is the authoritative feature-status and session-resumption tracker. Read the relevant strategy contract, architecture and Docker specification before changing their interfaces.

Select a feature whose dependencies are satisfied. Keep work bounded to the selected feature and record any necessary scope changes. Do not infer that a module is implemented because its directory exists. Do not infer broker capabilities, trading authorization or strategy performance from configuration examples.

Update the tracker in the same change as implementation: feature status, delivered behavior, tests and results, limitations, and the next concrete action. Update its Current handoff section at the end of a work session. Mark DONE only when its acceptance criteria are evidenced. Preserve feature IDs; split oversized features with suffixes and keep the parent open until all required parts pass.

Docker is the deployment target. Keep strategy logic outside shared core modules, credentials outside the repository, and account risk/ownership enforced centrally. Default execution remains offline/paper until the corresponding broker capability and deployment gates exist. Do not bypass a missing capability to make a test or demo pass.

Run relevant checks, record actual results, and distinguish local verification from GitHub CI or remote deployment. Follow user instructions for commits and publication; a planned feature is not permission to activate live trading.
