#!/bin/bash
# Run only the live end-to-end tests that use the Real LLM.

# Check if .env exists
if [ ! -f .env ]; then
    echo "Error: .env file not found. Please copy .env.example to .env and add your API keys."
    exit 1
fi

echo "Running Live E2E Tests with Real LLM..."
pytest tests/e2e -v -s
