import argparse
import json
from pathlib import Path

from sqlalchemy import func, select

from app.core.database import create_all, make_session_factory
from app.domain.models import Group, UsageFact, User
from app.ingest.loader import ingest_all
from app.provisioning import ProvisioningDenied, provision_environments


def bootstrap(database_url: str, starter_kit: Path) -> None:
    create_all(database_url)
    session_factory = make_session_factory(database_url)
    with session_factory() as session:
        ingest_all(session, starter_kit)
        session.commit()

        users = session.scalar(select(func.count()).select_from(User))
        groups = session.scalar(select(func.count()).select_from(Group))
        facts = session.scalar(select(func.count()).select_from(UsageFact))
        print(f"users={users} groups={groups} usage_facts={facts}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Meridian backend bootstrap utilities")
    subcommands = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subcommands.add_parser("bootstrap", help="Create the SQLite database and ingest starter-kit data")
    bootstrap_parser.add_argument("--db-url", default="sqlite:///backend/meridian.db")
    bootstrap_parser.add_argument("--starter-kit", type=Path, default=Path("starter-kit"))

    provision_parser = subcommands.add_parser(
        "provision",
        help="Render and validate environment permissions manifests and MCP host registration configs",
    )
    provision_parser.add_argument("--actor-user-id", required=True)
    provision_parser.add_argument("--db-url", default="sqlite:///backend/meridian.db")
    provision_parser.add_argument("--starter-kit", type=Path, default=Path("starter-kit"))
    provision_parser.add_argument("--output-dir", type=Path, default=Path("provisioning/rendered"))
    provision_parser.add_argument("--environment", choices=["dev", "staging", "prod"], action="append")
    provision_parser.add_argument("--group-id")

    args = parser.parse_args()
    if args.command == "bootstrap":
        bootstrap(args.db_url, args.starter_kit)
    elif args.command == "provision":
        create_all(args.db_url)
        session_factory = make_session_factory(args.db_url)
        with session_factory() as session:
            try:
                results = provision_environments(
                    session,
                    actor_user_id=args.actor_user_id,
                    starter_kit=args.starter_kit,
                    output_dir=args.output_dir,
                    database_url=args.db_url,
                    environments=args.environment,
                    group_id=args.group_id,
                )
            except ProvisioningDenied as exc:
                print(json.dumps(exc.denial.as_dict(), sort_keys=True))
                raise SystemExit(1) from exc

        for result in results:
            print(
                " ".join(
                    [
                        f"environment={result.environment}",
                        f"permissions_manifest={result.permissions_manifest}",
                        f"host_registration={result.host_registration}",
                    ]
                )
            )


if __name__ == "__main__":
    main()
