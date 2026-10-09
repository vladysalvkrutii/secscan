# Security Policy

## Reporting a vulnerability

This is an educational portfolio project. If you spot a security issue,
please open a GitHub issue or contact the maintainer rather than exploiting it.

## Security practices in this repo

- Container images run as a **non-root** user with a read-only root filesystem
  and all Linux capabilities dropped.
- Images are scanned with **Trivy** in CI; the pipeline fails on CRITICAL
  vulnerabilities.
- Dependencies are kept current via **Dependabot**.
- The scanner only accepts `http`/`https` targets to avoid local-file / scheme
  abuse.
