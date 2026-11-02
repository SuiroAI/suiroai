"""Compute the bounded synthetic probe using only local inputs."""

import csv
import json
from pathlib import Path


def main():
    directory = Path(__file__).resolve().parent
    binding = json.loads((directory / "binding.json").read_text(encoding="utf-8"))
    row_count = 0
    group_totals = {}
    total_units = 0
    with (directory / "probe_input.csv").open(encoding="utf-8", newline="") as source:
        for row in csv.DictReader(source):
            units = int(row["units"])
            product = row["product"]
            row_count += 1
            group_totals[product] = group_totals.get(product, 0) + units
            total_units += units
    result = {
        "row_count": row_count,
        "group_totals": group_totals,
        "total_units": total_units,
        "binding": binding,
    }
    (directory / "probe_result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )


if __name__ == "__main__":
    main()
