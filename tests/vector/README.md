# Vector integration test environment

`requirements.txt` records the selected direct compatibility baseline; Docker installs the complete resolved `requirements.lock`, including transitive dependencies and setuptools. The Python base is pinned by digest. This is a test-only environment, not a runtime dependency upgrade.

To update the lock, resolve the direct requirements in a disposable container using the same Python base, export `python -m pip freeze --all` (retain setuptools; the base supplies pip), then rebuild and run the smoke locally and in CI. Review the dependency diff. Version pins do not provide artifact hashes or supply-chain attestation.

The test service has no network or project data mount. It uses synthetic embeddings, checks stable-ID repeat/update/retrieval, then abruptly exits and reopens in fresh processes twice. It does not test real embedding quality or power-loss durability. Upstream Pydantic emits an `UnsupportedFieldAttributeWarning` for this compatibility baseline; assertions still run and the warning is not suppressed.
