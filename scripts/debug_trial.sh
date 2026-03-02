#!/bin/bash

# Load .env file (ignoring comments)
export $(grep -v '^#' .env | xargs)

# Map Azure secrets to OpenAI variables expected by gh aw / openai python client
export OPENAI_API_KEY="$AZURE_OPENAI_API_KEY"

# Ensure the endpoint ends with /openai/v1 matching the workflow config
# The .env usually has https://...azure.com/
# We need to construct the full base URL
if [[ "$AZURE_OPENAI_ENDPOINT" == */ ]]; then
  export OPENAI_BASE_URL="${AZURE_OPENAI_ENDPOINT}openai/v1"
else
  export OPENAI_BASE_URL="${AZURE_OPENAI_ENDPOINT}/openai/v1"
fi

export OPENAI_API_TYPE="azure"
export OPENAI_API_VERSION="$AZURE_OPENAI_API_VERSION"
export OPENAI_XX_IS_AZURE="true" # Some libs use this

echo "Configured Environment:"
echo "OPENAI_BASE_URL: $OPENAI_BASE_URL"
echo "OPENAI_API_VERSION: $OPENAI_API_VERSION"
# Explicitly set secrets on the trial repository to ensure they are available
echo "Setting secrets on TJKlein/gh-aw-trial..."
gh secret set AZURE_OPENAI_ENDPOINT -R TJKlein/gh-aw-trial --body "$AZURE_OPENAI_ENDPOINT"
gh secret set AZURE_OPENAI_API_KEY -R TJKlein/gh-aw-trial --body "$AZURE_OPENAI_API_KEY"

# Run the trial WITHOUT --use-local-secrets since we set them explicitly on the repo
# This avoids confusion about which secrets take precedence
gh aw trial ./.github/workflows/issue-monster.md -y
