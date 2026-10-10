import json
from pathlib import Path

from sqlalchemy.orm import Session

from app.domain.models import Group, User


def load_directory(session: Session, starter_kit: Path) -> None:
    groups_path = starter_kit / "data" / "directory" / "groups.json"
    users_path = starter_kit / "data" / "directory" / "users.json"

    groups_payload = json.loads(groups_path.read_text(encoding="utf-8"))
    users_payload = json.loads(users_path.read_text(encoding="utf-8"))

    for row in groups_payload["groups"]:
        group = session.get(Group, row["group_id"]) or Group(group_id=row["group_id"])
        group.name = row["name"]
        group.team_lead_user_id = row["team_lead_user_id"]
        group.claude_rbac_group_id = row["claude_rbac_group_id"]
        group.gcp_project_id = row["gcp_project_id"]
        group.gcp_project_number = row["gcp_project_number"]
        group.cost_centre = row["cost_centre"]
        session.add(group)
    session.flush()

    for row in users_payload["users"]:
        group_ids = row["group_ids"]
        if len(group_ids) != 1:
            raise ValueError(f"Expected exactly one group for {row['user_id']}, got {group_ids}")
        user = session.get(User, row["user_id"]) or User(user_id=row["user_id"])
        user.email = row["email"]
        user.name = row["name"]
        user.role = row["role"]
        user.primary_group_id = group_ids[0]
        user.claude_seat = row["claude_seat"]
        user.gcp_principal = row["gcp_principal"]
        session.add(user)
