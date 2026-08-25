#!/usr/bin/env bash
set -euo pipefail

refspec="${1:-HEAD:main}"
if [[ "${refspec}" != "HEAD:main" ]]; then
  echo "Only HEAD:main is allowed by push_protected_main.sh; got ${refspec}." >&2
  exit 2
fi

repository="${GITHUB_REPOSITORY:-}"
if [[ ! "${repository}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]]; then
  echo "GITHUB_REPOSITORY is missing or invalid: ${repository:-<empty>}" >&2
  exit 2
fi

if [[ -z "${MAIN_PUSH_DEPLOY_KEY:-}" ]]; then
  echo "::warning title=Protected-main deploy key not configured::Using the existing authenticated origin. This fallback is valid only before the main ruleset is activated."
  git push origin "${refspec}"
  exit 0
fi

base_tmp="${RUNNER_TEMP:-${TMPDIR:-/tmp}}"
ssh_dir="$(mktemp -d "${base_tmp%/}/ai-svodki-main-push.XXXXXX")"
trap 'rm -rf "${ssh_dir}"' EXIT
chmod 700 "${ssh_dir}"

key_path="${ssh_dir}/id_ed25519"
known_hosts_path="${ssh_dir}/known_hosts"
printf '%s\n' "${MAIN_PUSH_DEPLOY_KEY}" > "${key_path}"
chmod 600 "${key_path}"

cat > "${known_hosts_path}" <<'EOF'
github.com ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIOMqqnkVzrm0SdG6UOoqKLsabgH5C9okWi0dh2l9GKJl
EOF
chmod 600 "${known_hosts_path}"

export AI_SVODKI_MAIN_PUSH_KEY="${key_path}"
export AI_SVODKI_MAIN_PUSH_KNOWN_HOSTS="${known_hosts_path}"
export GIT_SSH_COMMAND='ssh -i "$AI_SVODKI_MAIN_PUSH_KEY" -o UserKnownHostsFile="$AI_SVODKI_MAIN_PUSH_KNOWN_HOSTS" -o StrictHostKeyChecking=yes -o IdentitiesOnly=yes'

echo "Pushing ${refspec} with the dedicated protected-main deploy key."
git push "git@github.com:${repository}.git" "${refspec}"
