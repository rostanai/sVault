"""M1 model smoke tests — mappers configure & relationships resolve (no live DB)."""
from sqlalchemy.orm import configure_mappers


def test_models_configure_mappers():
    import app.db.models  # noqa: F401

    # Raises if any relationship/FK/back_populates is misconfigured.
    configure_mappers()


def test_tablenames_match_schema():
    from app.db.models import Invitation, Organization, Profile, Tenant

    assert Tenant.__tablename__ == "tenants"
    assert Organization.__tablename__ == "organizations"
    assert Profile.__tablename__ == "profiles"
    assert Invitation.__tablename__ == "invitations"


def test_org_tree_self_reference():
    from app.db.models import Organization

    # Self-referential parent/children relationship is wired.
    rels = Organization.__mapper__.relationships.keys()
    assert "parent" in rels and "children" in rels
