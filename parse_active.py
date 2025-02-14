from pathlib import Path

from fips.models import StatusOptions
from fips.parser import FIPSParser


def main():
    """Main entry point."""
    base_dir = Path.cwd()
    status_options = StatusOptions(active=True)
    parser = FIPSParser(base_dir=base_dir, status_options=status_options)

    try:
        results = parser.start_search()
        print(f"\nFound results: {len(results)}")
        print(f"Results saved to: {parser.storage.csv_path}")
        print(f"Detailed information saved to: {parser.storage.patents_dir}")
    finally:
        parser.close()


if __name__ == "__main__":
    main()
