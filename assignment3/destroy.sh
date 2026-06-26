#!/usr/bin/env bash
# One-click teardown: delete all three stacks and their resources.
# Usage: ./destroy.sh
set -euo pipefail

cd "$(dirname "$0")"

export AWS_PROFILE="${AWS_PROFILE:-admin}"
export AWS_DEFAULT_REGION="${AWS_DEFAULT_REGION:-us-east-1}"
export JSII_SILENCE_WARNING_UNTESTED_NODE_VERSION=1

if [ -d .venv ]; then
  export PATH="$PWD/.venv/bin:$PATH"
fi

npx --yes aws-cdk@2 destroy --all --force
echo "All Cs6620A3 stacks destroyed."
