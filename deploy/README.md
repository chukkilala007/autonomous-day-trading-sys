# Deployment

The root Compose file runs the persistent offline paper stack: core, two strategy workers and a simulator. See the root README for launch, status, testing and shutdown commands.

Named volumes preserve core and simulator state independently. The isolated smoke drill uses a unique project and removes its own test volumes; normal operations should retain volumes.

Demo/live gateway overrides are not implemented. Future deployments must bind accounts explicitly and meet the gates in `docs/implementation-plan.md`. See `docs/container-deployment.md` for current operating limits and the target production contract.
