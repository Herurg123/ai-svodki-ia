# NotebookLM video subproject instructions

This directory is an independently maintained local Windows downstream subproject inside the wider AI-Svodki repository.

- Its scope is the local NotebookLM video workflow: RSS detection, Yandex Browser/Playwright automation, NotebookLM generation, MP4 download, PNG first-frame preview, local state/logging, and restricted FTP delivery to `video`.
- It is not part of the main nightly retrieval/editorial GitHub Actions production.
- Do not modify files in this directory as a side effect of tasks about retrieval, editorial policy, RSS/site generation, the main FTP deploy, cleanup, audits, or repository hygiene unless the task explicitly targets this subproject.
- Conversely, a video-subproject task does not authorize changes to unrelated production architecture.
- Keep `README.md` and `DEPLOYMENT.md` current whenever behavior, configuration, dependencies, deployment, recovery, or operator actions change.
- Commit only portable source, safe templates, tests, and documentation. Never commit real `config.json`, `ftp-access.json`, `state.json`, logs, downloaded media, browser profiles, or machine-local runtime state.
- Use `config.example.json` and `ftp-access.example.json` for portable configuration examples; use the provided setup/configuration scripts to create machine-local files.
- All repository changes still follow branch -> pull request -> CI -> diff review -> separate explicit merge approval.
