from pydantic_monty import Monty

code = """
import sys
print("sys.modules keys:", list(sys.modules.keys()))
import types

# Mock module
m = types.ModuleType("my_module")
m.x = 10
sys.modules["my_module"] = m

# Now try importing
from my_module import x
print("Imported x:", x)
"""

try:
    print("Running Monty sys.modules test...")
    m = Monty(code)
    m.run()
    print("Success!")
except Exception as e:
    print(f"Failed: {e}")
