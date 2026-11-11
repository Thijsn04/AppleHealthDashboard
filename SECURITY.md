# Security policy

## Supported versions

Security fixes are applied to the current `master` branch while the project is pre-1.0.

## Reporting a vulnerability

Please do not open a public issue for a suspected vulnerability involving health data, local file handling, archive extraction, authentication, or data exposure.

Email the repository owner through the contact method listed on the GitHub profile with:

- A clear description of the issue.
- Reproduction steps using synthetic data only.
- The affected version or commit.
- Any suggested mitigation.

We will acknowledge reports, investigate privately, and coordinate a fix before public disclosure.

## Security boundaries

- The analyzer is designed for local use on a trusted device.
- The supported CLI binds to loopback. It is not a multi-user or internet-facing service.
- Apple Health exports, local databases, logs, and imported metadata can contain highly sensitive data.
- Archive input is untrusted input. Import code must validate file type, size, compression ratio, paths, and XML structure.
- Any future AI integration must show users exactly what leaves the device and require explicit per-feature consent.

## Ongoing hardening work

The import pipeline will continue to add migration, recovery, and hostile-archive coverage. See [docs/ROADMAP.md](docs/ROADMAP.md).
