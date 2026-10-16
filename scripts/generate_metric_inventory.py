"""Generate offline pinned SDK getter inventory; never log in or contact Garmin."""
import inspect
import json
from importlib.metadata import version
from pathlib import Path

from garminconnect import Garmin


def main():
    methods = [{"method":name, "signature":str(inspect.signature(getattr(Garmin,name)))}
               for name in sorted(dir(Garmin)) if name.startswith("get_") and callable(getattr(Garmin,name))]
    document = {"sdk":"garminconnect", "version":version("garminconnect"),
                "scope":"Offline public getter signatures; not account availability or connector allowlist",
                "methods":methods}
    target = Path(__file__).resolve().parents[1]/"docs/reference/catalogs/garmin-sdk-read-inventory.json"
    target.write_text(json.dumps(document,indent=2)+"\n",encoding="utf-8")
    print(f"Wrote {len(methods)} offline SDK getter signatures.")


if __name__ == "__main__":
    main()
