"""用于覆盖 test_google_identity_link_service.py 对应的回归测试。"""

from __future__ import annotations

import pytest
from collections.abc import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.infra.database import Base
from app.models import ProviderIdentity, User
from app.services.auth.google_identity_link_service import (
    GoogleIdentityLinkError,
    GoogleIdentityLinkService,
)
from app.services.auth.google_oauth_client import GoogleIdentity


@pytest.fixture()
def db() -> Generator[Session, None, None]:
    """用于处理数据库。"""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


def _google_identity(
    *,
    sub: str = "google-sub-123",
    email: str = "user@example.com",
    email_verified: bool = True,
    name: str | None = "Google User",
) -> GoogleIdentity:
    """用于处理Googleidentity。"""
    return GoogleIdentity(
        sub=sub,
        email=email,
        email_verified=email_verified,
        name=name,
    )


def test_existing_google_identity_returns_bound_local_user(db: Session):
    """用于验证existingGoogleidentityreturnsboundlocal用户。"""
    user = User(
        email="bound@example.com",
        hashed_password=None,
        full_name="Bound User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        ProviderIdentity(
            provider="google",
            provider_user_id="google-sub-123",
            user_id=user.id,
            provider_email="bound@example.com",
            provider_email_verified=True,
        )
    )
    db.commit()

    resolved_user = GoogleIdentityLinkService(db).resolve_user(
        _google_identity(email="bound@example.com")
    )

    assert resolved_user.id == user.id
    assert resolved_user.email == "bound@example.com"


def test_verified_google_email_binds_existing_local_user(db: Session):
    """用于验证verifiedGoogleemailbindsexistinglocal用户。"""
    user = User(
        email="existing@example.com",
        hashed_password="hashed-local-password",
        full_name="Existing User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    resolved_user = GoogleIdentityLinkService(db).resolve_user(
        _google_identity(sub="new-google-sub", email="existing@example.com")
    )

    assert resolved_user.id == user.id
    provider_identity = db.query(ProviderIdentity).one()
    assert provider_identity.user_id == user.id
    assert provider_identity.provider == "google"
    assert provider_identity.provider_user_id == "new-google-sub"
    assert provider_identity.provider_email == "existing@example.com"
    assert provider_identity.provider_email_verified is True


def test_verified_google_email_creates_google_only_user(db: Session):
    """用于验证verifiedGoogleemailcreatesGoogleonly用户。"""
    resolved_user = GoogleIdentityLinkService(db).resolve_user(
        _google_identity(
            sub="fresh-google-sub",
            email="fresh@example.com",
            name="Fresh Google User",
        )
    )

    assert resolved_user.email == "fresh@example.com"
    assert resolved_user.full_name == "Fresh Google User"
    assert resolved_user.hashed_password is None

    provider_identity = db.query(ProviderIdentity).one()
    assert provider_identity.user_id == resolved_user.id
    assert provider_identity.provider == "google"
    assert provider_identity.provider_user_id == "fresh-google-sub"


def test_unverified_google_email_is_rejected_without_creating_records(db: Session):
    """用于验证unverifiedGoogleemailisrejectedwithoutcreatingrecords。"""
    with pytest.raises(GoogleIdentityLinkError) as exc_info:
        GoogleIdentityLinkService(db).resolve_user(
            _google_identity(
                sub="unverified-google-sub",
                email="unverified@example.com",
                email_verified=False,
            )
        )

    assert exc_info.value.error_code == "unverified_email"
    assert db.query(User).count() == 0
    assert db.query(ProviderIdentity).count() == 0


def test_unverified_google_email_is_rejected_even_when_sub_is_bound(db: Session):
    """用于验证unverifiedGoogleemailisrejectedevenwhensubisbound。"""
    user = User(
        email="bound-unverified@example.com",
        hashed_password=None,
        full_name="Bound Unverified",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        ProviderIdentity(
            provider="google",
            provider_user_id="bound-unverified-sub",
            user_id=user.id,
            provider_email="bound-unverified@example.com",
            provider_email_verified=True,
        )
    )
    db.commit()

    with pytest.raises(GoogleIdentityLinkError) as exc_info:
        GoogleIdentityLinkService(db).resolve_user(
            _google_identity(
                sub="bound-unverified-sub",
                email="bound-unverified@example.com",
                email_verified=False,
            )
        )

    assert exc_info.value.error_code == "unverified_email"
    assert db.query(User).count() == 1
    assert db.query(ProviderIdentity).count() == 1


def test_existing_google_identity_for_email_rejects_different_google_sub(
    db: Session,
):
    """用于验证existingGoogleidentityforemailrejectsdifferentGooglesub。"""
    user = User(
        email="conflict@example.com",
        hashed_password="hashed-local-password",
        full_name="Conflict User",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    db.add(
        ProviderIdentity(
            provider="google",
            provider_user_id="old-google-sub",
            user_id=user.id,
            provider_email="conflict@example.com",
            provider_email_verified=True,
        )
    )
    db.commit()

    with pytest.raises(GoogleIdentityLinkError) as exc_info:
        GoogleIdentityLinkService(db).resolve_user(
            _google_identity(
                sub="new-google-sub",
                email="conflict@example.com",
            )
        )

    assert exc_info.value.error_code == "account_conflict"
    assert db.query(ProviderIdentity).count() == 1


def test_existing_google_sub_does_not_rebind_to_email_matched_user(db: Session):
    """用于验证existingGooglesubdoesnotrebindtoemailmatched用户。"""
    bound_user = User(
        email="bound-owner@example.com",
        hashed_password=None,
        full_name="Bound Owner",
    )
    email_matched_user = User(
        email="current-email@example.com",
        hashed_password="hashed-local-password",
        full_name="Email Matched",
    )
    db.add_all([bound_user, email_matched_user])
    db.commit()
    db.refresh(bound_user)
    db.refresh(email_matched_user)
    db.add(
        ProviderIdentity(
            provider="google",
            provider_user_id="stable-google-sub",
            user_id=bound_user.id,
            provider_email="bound-owner@example.com",
            provider_email_verified=True,
        )
    )
    db.commit()

    resolved_user = GoogleIdentityLinkService(db).resolve_user(
        _google_identity(
            sub="stable-google-sub",
            email="current-email@example.com",
        )
    )

    assert resolved_user.id == bound_user.id
    provider_identity = db.query(ProviderIdentity).one()
    assert provider_identity.user_id == bound_user.id
    assert provider_identity.user_id != email_matched_user.id
