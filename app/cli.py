import argparse
import asyncio

from app.auth.api_keys import generate_key
from app.config import get_settings
from app.db.models import APIKey
from app.db.session import SessionLocal


async def create_key(name: str, rpm: int, quota: int) -> None:
    raw, prefix, digest = generate_key()
    async with SessionLocal() as session:
        session.add(
            APIKey(name=name, prefix=prefix, digest=digest, rate_limit_rpm=rpm, monthly_quota=quota)
        )
        await session.commit()
    print(raw)


def main() -> None:
    parser = argparse.ArgumentParser(prog="crawlforge")
    sub = parser.add_subparsers(dest="command", required=True)
    key = sub.add_parser("api-key")
    key_sub = key.add_subparsers(dest="key_command", required=True)
    create = key_sub.add_parser("create")
    create.add_argument("--name", default="local-development")
    create.add_argument("--rpm", type=int, default=get_settings().default_rate_limit_rpm)
    create.add_argument("--quota", type=int, default=get_settings().default_monthly_quota)
    args = parser.parse_args()
    if args.command == "api-key" and args.key_command == "create":
        asyncio.run(create_key(args.name, args.rpm, args.quota))


if __name__ == "__main__":
    main()
