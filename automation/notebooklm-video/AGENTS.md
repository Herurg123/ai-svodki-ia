# NotebookLM video subproject instructions

This directory is an independently maintained local Windows downstream subproject inside the wider AI-Svodki repository.

The repository-level relationship and CI boundary are canonical in [`../ARCHITECTURE.md`](../ARCHITECTURE.md). This file contains the prescriptive local rules.

- Its scope is the local NotebookLM video workflow: RSS detection, Yandex Browser/Playwright automation, NotebookLM generation, MP4 download, PNG first-frame preview, local state/logging, and restricted FTP delivery to `video`.
- It is not part of the main nightly retrieval/editorial GitHub Actions production.
- Pull requests are routed by the always-on **PR Gate**; video-domain changes call the dedicated **Video CI** in `.github/workflows/video-ci.yml`, while **Main CI** must remain unnecessary for video-only changes.
- Do not re-couple Video CI and Main CI without an explicit architecture change plus matching documentation and contract-test updates.
- Video CI stays offline with respect to NotebookLM, FTP, production APIs, Windows DPAPI, and npm dependency installation. Platform-specific behavior is verified on the target Windows machine.
- Keep `package.json` and committed `package-lock.json` synchronized. Any npm dependency change must update the lockfile in the same pull request and prove a clean `npm ci`; normal setup/deployment entrypoints must use `npm ci`, not `npm install`.
- Do not modify files in this directory as a side effect of tasks about retrieval, editorial policy, RSS/site generation, the main FTP deploy, cleanup, audits, or repository hygiene unless the task explicitly targets that subproject.
- Conversely, a video-subproject task does not authorize changes to unrelated production architecture.
- Keep `README.md` and `DEPLOYMENT.md` current whenever behavior, configuration, dependencies, deployment, recovery, or operator actions change.
- Commit only portable source, safe templates, tests, dependency lockfiles, and documentation. Never commit real runtime configuration, access data, state, logs, downloaded media, browser profiles, or machine-local runtime state.
- Use the committed example configuration files and setup scripts for portable deployment; machine-local files remain outside Git.
- FTP access is hard-confined to remote directory `video`. Changing that boundary requires an explicit architecture decision, not a configuration-only edit.
- All repository changes still follow branch -> pull request -> CI -> diff review -> separate explicit merge approval.
