# D01: Python and reproducible dependencies

Use Python 3.12 in the digest-pinned official Linux image. pip-tools generates separate SHA256-verified core, test and gateway locks. The initial common image includes test tools to keep offline verification simple; production image slimming belongs to S7. Package installation uses the already locked build tools without build isolation or dependency re-resolution. Gateway imports are checked in a separate build target, without broker credentials.

The installed CLI is used in Docker. Development host Python is not a compatibility guarantee. Container checks in this feature exercise the current Docker host architecture; cross-architecture CI qualification remains an S7 requirement. The dependency lock is authoritative; .in ranges only select candidates when deliberately regenerating locks. CI action revision and base image are immutable references.

Gateway compatibility additionally includes service-identity: an import-only SDK test revealed Twisted's missing hostname-verification dependency. The dependency is explicit in the gateway lock, rather than accepting the warning. Import checks do not claim broker connectivity or verified provider metadata.
