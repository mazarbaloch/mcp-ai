import asyncio
import shutil
import subprocess
import sys

from app.config import Settings
from app.ollama_client import connect_ollama


async def main():
    print(f"Python: {sys.version.split()[0]}")
    failed = False
    for name in ("uv", "node", "npm", "npx", "ollama"):
        executable = shutil.which(name)
        if not executable:
            print(f"{name}: MISSING")
            failed = True
            continue
        result = await asyncio.to_thread(
            subprocess.run,
            [executable, "--version"],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )
        print((result.stdout or result.stderr).strip())
        failed |= result.returncode != 0
    try:
        async with connect_ollama(Settings.from_env()) as (_, status):
            print(status)
    except Exception as exc:
        print(exc)
        return 1
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
