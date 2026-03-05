#!/usr/bin/env python3
"""奥创自动修复脚本 - Python包装器"""
import subprocess
import sys

def main():
    result = subprocess.run(
        ["/root/.openclaw/workspace/ultron/auto-fix.sh"],
        capture_output=True,
        text=True
    )
    print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())