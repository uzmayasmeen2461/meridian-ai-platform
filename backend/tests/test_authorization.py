from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.core.database import Base
from app.domain.authorization import AuthorizationService
from app.domain.capabilities import CapabilityService
from app.domain.models import User
from app.domain.policy import EnvironmentPolicy
from app.ingest.directory import load_directory

STARTER_KIT = Path(__file__).resolve().parents[2] / "starter-kit"

USERS = {
    "clinical_lead": "user_E7691888F28227066DD2FB86",
    "clinical_member": "user_699C48763F6FA2958D2CDB5D",
    "admin": "user_533B58E6F66C98ACB833527A",
}


def _policy(environment: str) -> EnvironmentPolicy:
    return EnvironmentPolicy.from_file(STARTER_KIT / "environments" / f"{environment}.yaml")


def _services(session: Session, environment: str):
    policy = _policy(environment)
    capabilities = CapabilityService(session, policy)
    authorization = AuthorizationService(session, policy, capabilities)
    return capabilities, authorization


def test_dev_member_can_read_any_group(ingested_session):
    _, auth = _services(ingested_session, "dev")

    result = auth.authorize_scope(USERS["clinical_member"], "usage:read", "finance")

    assert result.allowed
    assert result.group.group_id == "finance"


def test_staging_and_prod_members_are_denied_usage(ingested_session):
    for environment in ("staging", "prod"):
        _, auth = _services(ingested_session, environment)

        result = auth.authorize_scope(USERS["clinical_member"], "usage:read", "clinical-operations")

        assert not result.allowed
        assert result.denial.as_dict() == {
            "error": "permission_denied",
            "reason": "Caller role is not allowed for this operation.",
            "required_scope": "usage:read",
        }


def test_staging_and_prod_team_lead_can_read_own_group_only(ingested_session):
    for environment in ("staging", "prod"):
        _, auth = _services(ingested_session, environment)

        own_group = auth.authorize_scope(USERS["clinical_lead"], "usage:read", "clinical-operations")
        other_group = auth.authorize_scope(USERS["clinical_lead"], "usage:read", "finance")

        assert own_group.allowed
        assert not other_group.allowed
        denial = other_group.denial.as_dict()
        assert denial["error"] == "permission_denied"
        assert denial["required_scope"] == "usage:read"
        assert "finance" not in denial["reason"]


def test_dev_and_staging_team_lead_write_allowed_by_yaml(ingested_session):
    for environment in ("dev", "staging"):
        _, auth = _services(ingested_session, environment)

        result = auth.authorize_capability_write(USERS["clinical_lead"], "clinical-operations", "code-execution")

        assert result.allowed


def test_prod_team_lead_write_denied(ingested_session):
    _, auth = _services(ingested_session, "prod")

    result = auth.authorize_capability_write(USERS["clinical_lead"], "clinical-operations", "code-execution")

    assert not result.allowed
    assert result.denial.as_dict()["required_scope"] == "capabilities:write"


def test_prod_admin_can_read_and_write_across_groups(ingested_session):
    _, auth = _services(ingested_session, "prod")

    read = auth.authorize_scope(USERS["admin"], "usage:read", "finance")
    write = auth.authorize_capability_write(USERS["admin"], "finance", "code-execution")

    assert read.allowed
    assert write.allowed


def test_disabled_usage_connector_blocks_mcp_operations(ingested_session):
    _, auth = _services(ingested_session, "prod")

    result = auth.authorize_mcp_operation(USERS["clinical_lead"], "usage:read", "clinical-operations")
    blocked = auth.authorize_mcp_operation(USERS["clinical_lead"], "usage:read", "finance")

    assert result.allowed
    assert not blocked.allowed

    hr_lead = "user_EFD3FFD905F1F3A62F1AE916"
    disabled = auth.authorize_mcp_operation(hr_lead, "usage:read", "hr")
    assert not disabled.allowed
    assert disabled.denial.as_dict() == {
        "error": "permission_denied",
        "reason": "usage-connector is disabled for the caller's group.",
        "required_scope": "usage:read",
    }


def test_rest_capability_write_can_reenable_disabled_usage_connector(ingested_session):
    capabilities, auth = _services(ingested_session, "prod")
    admin = ingested_session.get(User, USERS["admin"])

    write = auth.authorize_capability_write(USERS["admin"], "hr", "usage-connector")
    assert write.allowed

    state = capabilities.set_override("hr", "usage-connector", True, admin)
    assert state.enabled
    assert state.updated_by == USERS["admin"]

    hr_lead = "user_EFD3FFD905F1F3A62F1AE916"
    allowed = auth.authorize_mcp_operation(hr_lead, "usage:read", "hr")
    assert allowed.allowed


def test_capability_overrides_persist_after_restart(tmp_path):
    db_path = tmp_path / "auth.db"
    engine = create_engine(f"sqlite:///{db_path}")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        load_directory(session, STARTER_KIT)
        session.commit()
        capabilities, _ = _services(session, "prod")
        admin = session.get(User, USERS["admin"])
        default = capabilities.get_state("finance", "usage-connector")
        assert not default.enabled
        capabilities.set_override("finance", "usage-connector", True, admin)
        session.commit()

    with Session(engine) as restarted:
        capabilities, _ = _services(restarted, "prod")
        state = capabilities.get_state("finance", "usage-connector")

        assert state.enabled
        assert state.source == "override"
        assert state.updated_by == USERS["admin"]
        assert state.updated_at is not None


def test_environment_specific_capability_defaults(ingested_session):
    dev_capabilities, _ = _services(ingested_session, "dev")
    staging_capabilities, _ = _services(ingested_session, "staging")
    prod_capabilities, _ = _services(ingested_session, "prod")

    assert dev_capabilities.get_state("finance", "code-execution").enabled
    assert not staging_capabilities.get_state("finance", "code-execution").enabled
    assert prod_capabilities.get_state("clinical-operations", "usage-connector").enabled
    assert prod_capabilities.get_state("it-platform", "usage-connector").enabled
    assert not prod_capabilities.get_state("finance", "usage-connector").enabled


def test_invalid_identities_groups_and_capabilities_fail_closed(ingested_session):
    capabilities, auth = _services(ingested_session, "prod")

    missing = auth.authorize_scope(None, "usage:read", "clinical-operations")
    unknown_user = auth.authorize_scope("not-a-user", "usage:read", "clinical-operations")
    unknown_group = auth.authorize_scope(USERS["admin"], "usage:read", "not-a-group")
    unknown_capability = auth.authorize_capability_write(USERS["admin"], "finance", "not-a-cap")

    assert not missing.allowed
    assert not unknown_user.allowed
    assert not unknown_group.allowed
    assert not unknown_capability.allowed
    assert unknown_capability.denial.as_dict() == {
        "error": "permission_denied",
        "reason": "Unknown capability.",
        "required_scope": "capabilities:write",
    }

    try:
        capabilities.get_state("finance", "not-a-cap")
    except ValueError as exc:
        assert "Unknown capability" in str(exc)


def test_unknown_role_denied_by_default(ingested_session):
    user = ingested_session.get(User, USERS["clinical_member"])
    user.role = "mystery_role"
    ingested_session.commit()
    _, auth = _services(ingested_session, "dev")

    result = auth.authorize_scope(user.user_id, "usage:read", "clinical-operations")

    assert not result.allowed
    assert result.denial.as_dict()["error"] == "permission_denied"


def test_denials_contain_no_protected_data(ingested_session):
    _, auth = _services(ingested_session, "prod")

    denial = auth.authorize_scope(USERS["clinical_lead"], "usage:read", "finance").denial.as_dict()

    assert denial == {
        "error": "permission_denied",
        "reason": "Caller may not access the requested group.",
        "required_scope": "usage:read",
    }
    assert "finance" not in str(denial)
    assert "user_" not in str(denial)
    assert "@meridianls.example" not in str(denial)
