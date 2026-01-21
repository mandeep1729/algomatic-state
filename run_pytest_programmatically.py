
import subprocess
import sys

result = subprocess.run(
    [r"c:\Users\mande\projects\algomatic-state\.venv\Scripts\python.exe", "-m", "pytest", "-v", "--tb=short", "tests/unit/state/"],
    cwd=r"c:\Users\mande\projects\algomatic-state",
    capture_output=True,
    text=True
)

with open("test_output.txt", "w") as f:
    f.write("STDOUT:\n")
    f.write(result.stdout)
    f.write("\n\nSTDERR:\n")
    f.write(result.stderr)
    f.write(f"\n\nReturn code: {result.returncode}")

print("Output written to test_output.txt")
print(f"Return code: {result.returncode}")
