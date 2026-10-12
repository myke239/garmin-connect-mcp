"""Private subprocess entry point. Never expose this as an MCP tool."""

import json
import sys

from .runtime import worker


class Output:
    def send(self, result):
        sys.stdout.write(json.dumps(result))
        sys.stdout.flush()

    def close(self):
        pass


def main():
    try:
        request = json.loads(sys.stdin.read(20000))
        worker(Output(), request["directory"], request["method"], request["args"], request["kwargs"])
    except Exception:
        Output().send((False, "INVALID_REQUEST"))


if __name__ == "__main__":
    main()
