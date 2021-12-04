#!/bin/bash

git_root=$(git rev-parse --show-toplevel)

# Configure the repo with all the pertinent hooks so you
# don't have to do it manually.  For more information on how these
# hooks work, please see https://git-scm.com/docs/githooks.
echo Setting up git hooks.
ln -sfnv ${git_root}/hooks/pre-push ${git_root}/.git/hooks/pre-push
