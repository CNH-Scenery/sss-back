import argparse


def main() -> int:
    parser = argparse.ArgumentParser(description="CoinTwin backend worker")
    parser.add_argument("--once", action="store_true", help="Run a single startup check and exit")
    args = parser.parse_args()

    if args.once:
        print("backend-worker ready")
        return 0

    print("backend-worker ready")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
