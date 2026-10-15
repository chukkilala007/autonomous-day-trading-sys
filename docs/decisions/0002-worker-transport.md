# D02: Private worker framing

Use a 1 MiB maximum length-framed JSON request, per-instance 256-bit random shared token, protocol version, core role and random request correlation ID on an internal Docker network. Tokens are file-mounted and compared in constant time; never broker secrets. Transport is private-host plaintext, not suitable for a multi-host or hostile network. Deploy TLS before extending that boundary. Client timeouts discard late responses; core must inhibit the instance on failure. Worker crashes cannot mutate core state because evaluations return proposed state only.

The worker image has no operational database mount, no Docker socket, no broker network and no external network. Container deployment tests are exercised again in the integrated paper stage; localhost protocol tests already cover unauthorized/incorrect instance requests, size bounds and timeouts.
