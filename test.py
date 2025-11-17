import os
from openai import AzureOpenAI

# Make sure these environment variables are set:
AZURE_OPENAI_ENDPOINT="https://tk-mas28nfr-swedencentral.cognitiveservices.azure.com/"
AZURE_OPENAI_API_KEY="CYamzNccVrS1qFtIr0gBLDn8MkpEk9wlpNZ6mVEOu38CIyTdkgV6JQQJ99BKACfhMk5XJ3w3AAAAACOGo1wb"
AZURE_OPENAI_API_VERSION="2025-01-01-preview"

client = AzureOpenAI(
    api_key=AZURE_OPENAI_API_KEY,
    api_version=AZURE_OPENAI_API_VERSION,
    azure_endpoint=AZURE_OPENAI_ENDPOINT
)

# Try a simple test prompt using your deployment
deployment_name = "gpt-5.1-codex-mini"

response = client.chat.completions.create(
    model=deployment_name,
    messages=[
        {"role": "user", "content": "Write a simple Python function that adds two numbers."}
    ]
)

print("Response:")
print(response.choices[0].message.content)
