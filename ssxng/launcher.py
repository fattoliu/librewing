from __future__ import annotations

import sys

from .instance import AlreadyRunningError, InstanceLock


def main() -> int:
    try:
        with InstanceLock():
            from .app_beta import main as app_main

            return app_main()
    except AlreadyRunningError as exc:
        print(f"ssx-ng-linux: {exc}", file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
