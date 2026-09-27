"""One-shot fetch of the Digiflazz price list, saved to JSON.

Digiflazz rate-limits price-list requests to once every 5 minutes, so this
script makes exactly one call and exits — do not loop or retry it.

Run from api/: python -m scripts.fetch_price_list [output_path]
Default output_path: price_list.json (in the current working directory)
"""
import json
import sys

from digiflazz import Digiflazz

if __name__ == "__main__":
    output_path = sys.argv[1] if len(sys.argv) > 1 else "price_list.json"

    digiflazz = Digiflazz()
    price_list = digiflazz.get_price_list()

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([item.model_dump() for item in price_list], f, ensure_ascii=False, indent=2)

    print(f"Saved {len(price_list)} products to {output_path}")
