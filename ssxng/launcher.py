from __future__ import annotations

import sys

from .instance import AlreadyRunningError, InstanceLock
from .lifecycle import cleanup_managed_orphan_ss_local


def main() -> int:
    try:
        with InstanceLock():
            # If the previous GUI died unexpectedly, ss-local can be reparented
            # to PID 1 and keep 1080 occupied. Reclaim only the exact same-user
            # ss-local process launched with our runtime config before starting.
            cleanup_managed_orphan_ss_local()

            from .app_beta import main as app_main

            return app_main()
    except AlreadyRunningError as exc:
        print(f"ssx-ng-linux: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
