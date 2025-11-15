import asyncio
from pathlib import Path
from microsandbox import PythonSandbox


async def test():
    workspace = Path("./workspace").resolve()
    workspace.mkdir(exist_ok=True)

    async with PythonSandbox.create(
        name="test-volumes", volumes=[(str(workspace), "/workspace")]
    ) as sandbox:
        result = await sandbox.run(
            """
with open("/workspace/test.txt", "w") as f:
    f.write("Hello from sandbox!")
print("File written to /workspace/test.txt")
"""
        )
        print(await result.output())

    # Verify file exists on host
    test_file = workspace / "test.txt"
    if test_file.exists():
        print(f"✅ SUCCESS! File found at {test_file}")
        print(f"   Content: {test_file.read_text()}")
    else:
        print("❌ FAILED - File not found on host")


asyncio.run(test())
