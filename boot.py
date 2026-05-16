import os
import sys
import traceback

import uvicorn


def main() -> int:
    port = int(os.getenv("PORT", "8080"))
    print("=== iModel boot ===", flush=True)
    print(f"PORT={port}", flush=True)
    print(f"BOT_TOKEN configured={bool(os.getenv('BOT_TOKEN'))}", flush=True)
    print(f"WEBHOOK_BASE configured={bool(os.getenv('WEBHOOK_BASE'))}", flush=True)
    try:
        uvicorn.run("app:api", host="0.0.0.0", port=port, log_level=os.getenv("LOG_LEVEL", "info"))
        return 0
    except BaseException:
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
