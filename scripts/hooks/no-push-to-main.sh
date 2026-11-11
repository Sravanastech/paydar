#!/usr/bin/env sh
# Blocks pushes to main from this machine; changes reach main only via GitHub pull requests.
case "${PRE_COMMIT_REMOTE_BRANCH:-}" in
  refs/heads/main|main) echo "Direct push to main is blocked. Open a pull request instead." >&2; exit 1 ;;
esac
exit 0
