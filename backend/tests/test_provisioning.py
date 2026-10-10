import hashlib
import json
import sys
from pathlib import Path

import pytest

from app.cli import main as cli_main
from app.core.database import Base, make_engine, make_session_factory
from app.domain.capabilities import CapabilityService
from app.domain.models import Group, User
from app.domain.policy import EnvironmentPolicy
from app.ingest.loader import ingest_all
from app.provisioning import (
    HOST_REGISTRATION,
    PERMISSIONS_MANIFEST,
    ProvisioningDenied,
    ProvisioningError,
    provision_environments,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
STARTER_KIT = REPO_ROOT / "starter-kit"
ADMIN = "user_533B58E6F66C98ACB833527A"
CLINICAL_LEAD = "user_E7691888F28227066DD2FB86"
MEMBER = "user_699C48763F6FA2958D2CDB5D"


@pytest.fixture()
def provisioned_db(tmp_path):
    database_url = f"sqlite:///{tmp_path / 'provision.db'}"
    engine = make_engine(database_url)
    Base.metadata.create_all(engine)
    factory = make_session_factory(database_url)
    with factory() as session:
        ingest_all(session, STARTER_KIT)
        session.commit()
    return database_url, factory


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def tree_hash(path: Path) -> str:
    digest = hashlib.sha256()
    for file_path in sorted(path.rglob("*.json")):
        digest.update(str(file_path.relative_to(path)).encode("utf-8"))
        digest.update(file_path.read_bytes())
    return digest.hexdigest()


def test_admin_provisions_all_environments(provisioned_db, tmp_path):
    database_url, factory = provisioned_db
    with factory() as session:
        results = provision_environments(
            session,
            actor_user_id=ADMIN,
            starter_kit=STARTER_KIT,
            output_dir=tmp_path,
            database_url=database_url,
        )

    assert [result.environment for result in results] == ["dev", "staging", "prod"]
    for environment in ("dev", "staging", "prod"):
        manifest = load_json(tmp_path / environment / PERMISSIONS_MANIFEST)
        registration = load_json(tmp_path / environment / HOST_REGISTRATION)
        assert manifest["environment"] == environment
        assert set(manifest["tools"]) == {"usage_summary", "top_users", "capability_status", "set_capability"}
        assert len(manifest["groups"]) == 6
        assert registration["environment"] == environment
        assert registration["server_name"] == manifest["server_name"]
        assert registration["claude_desktop"]["mcpServers"][manifest["server_name"]]["env"]["MERIDIAN_ENV"] == environment


def test_provisioning_is_repeatable_and_safe_to_rerun(provisioned_db, tmp_path):
    database_url, factory = provisioned_db
    with factory() as session:
        provision_environments(
            session,
            actor_user_id=ADMIN,
            starter_kit=STARTER_KIT,
            output_dir=tmp_path,
            database_url=database_url,
        )
        first_hash = tree_hash(tmp_path)
        provision_environments(
            session,
            actor_user_id=ADMIN,
            starter_kit=STARTER_KIT,
            output_dir=tmp_path,
            database_url=database_url,
        )

    assert tree_hash(tmp_path) == first_hash


def test_invalid_environment_group_and_identity_fail_closed(provisioned_db, tmp_path):
    database_url, factory = provisioned_db
    with factory() as session:
        with pytest.raises(ProvisioningError, match="Unsupported environment"):
            provision_environments(
                session,
                actor_user_id=ADMIN,
                starter_kit=STARTER_KIT,
                output_dir=tmp_path,
                database_url=database_url,
                environments=["qa"],
            )

        with pytest.raises(ProvisioningDenied) as unknown_group:
            provision_environments(
                session,
                actor_user_id=ADMIN,
                starter_kit=STARTER_KIT,
                output_dir=tmp_path,
                database_url=database_url,
                environments=["prod"],
                group_id="unknown-group",
            )
        assert unknown_group.value.denial.as_dict()["reason"] == "Unknown group."

        with pytest.raises(ProvisioningDenied) as unknown_user:
            provision_environments(
                session,
                actor_user_id="not-a-user",
                starter_kit=STARTER_KIT,
                output_dir=tmp_path,
                database_url=database_url,
                environments=["dev"],
            )
        assert unknown_user.value.denial.as_dict()["error"] == "permission_denied"


def test_team_lead_can_provision_own_group_in_dev_but_not_cross_group(provisioned_db, tmp_path):
    database_url, factory = provisioned_db
    with factory() as session:
        provision_environments(
            session,
            actor_user_id=CLINICAL_LEAD,
            starter_kit=STARTER_KIT,
            output_dir=tmp_path,
            database_url=database_url,
            environments=["dev"],
            group_id="clinical-operations",
        )
        manifest = load_json(tmp_path / "dev" / PERMISSIONS_MANIFEST)
        assert [group["group_id"] for group in manifest["groups"]] == ["clinical-operations"]

        with pytest.raises(ProvisioningDenied) as denied:
            provision_environments(
                session,
                actor_user_id=CLINICAL_LEAD,
                starter_kit=STARTER_KIT,
                output_dir=tmp_path,
                database_url=database_url,
                environments=["dev"],
                group_id="finance",
            )

    assert denied.value.denial.as_dict() == {
        "error": "permission_denied",
        "reason": "Caller may not access the requested group.",
        "required_scope": "capabilities:write",
    }


def test_member_cannot_provision(provisioned_db, tmp_path):
    database_url, factory = provisioned_db
    with factory() as session:
        with pytest.raises(ProvisioningDenied) as denied:
            provision_environments(
                session,
                actor_user_id=MEMBER,
                starter_kit=STARTER_KIT,
                output_dir=tmp_path,
                database_url=database_url,
                environments=["dev"],
                group_id="clinical-operations",
            )

    assert denied.value.denial.as_dict() == {
        "error": "permission_denied",
        "reason": "Caller role is not allowed for this operation.",
        "required_scope": "capabilities:write",
    }


def test_capability_overrides_are_rendered_after_restart(provisioned_db, tmp_path):
    database_url, factory = provisioned_db
    policy = EnvironmentPolicy.from_file(STARTER_KIT / "environments" / "prod.yaml")

    with factory() as session:
        group = session.get(Group, "finance")
        assert group is not None
        user = session.get(User, ADMIN)
        assert user is not None
        capabilities = CapabilityService(session, policy)
        capabilities.set_override("finance", "code-execution", True, user)
        session.commit()

    with factory() as restarted_session:
        provision_environments(
            restarted_session,
            actor_user_id=ADMIN,
            starter_kit=STARTER_KIT,
            output_dir=tmp_path,
            database_url=database_url,
            environments=["prod"],
            group_id="finance",
        )

    manifest = load_json(tmp_path / "prod" / PERMISSIONS_MANIFEST)
    capability = next(
        item
        for item in manifest["groups"][0]["capabilities"]
        if item["capability"] == "code-execution"
    )
    assert capability["enabled"] is True
    assert capability["source"] == "override"
    assert capability["updated_by"] == ADMIN


def test_cli_provision_command_renders_and_reports_outputs(provisioned_db, tmp_path, monkeypatch, capsys):
    database_url, _ = provisioned_db
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "meridian-bootstrap",
            "provision",
            "--actor-user-id",
            ADMIN,
            "--db-url",
            database_url,
            "--starter-kit",
            str(STARTER_KIT),
            "--output-dir",
            str(tmp_path),
            "--environment",
            "dev",
        ],
    )

    cli_main()

    output = capsys.readouterr().out
    assert "environment=dev" in output
    assert (tmp_path / "dev" / PERMISSIONS_MANIFEST).exists()
    assert (tmp_path / "dev" / HOST_REGISTRATION).exists()
