from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import ProviderIdentity, User
from app.services.auth.google_oauth_client import GoogleIdentity


class GoogleIdentityLinkError(Exception):
    def __init__(self, error_code: str):
        self.error_code = error_code
        super().__init__(error_code)


class GoogleIdentityLinkService:
    """Resolves a verified Google identity to an existing local user."""

    provider = "google"

    def __init__(self, db: Session):
        self.db = db

    def resolve_user(self, identity: GoogleIdentity) -> User:
        if not identity.email_verified:
            raise GoogleIdentityLinkError("unverified_email")

        provider_identity = (
            self.db.query(ProviderIdentity)
            .filter(
                ProviderIdentity.provider == self.provider,
                ProviderIdentity.provider_user_id == identity.sub,
            )
            .first()
        )
        if provider_identity:
            return provider_identity.user

        user = self.db.query(User).filter(User.email == identity.email).first()
        if user:
            return self._bind_identity(user, identity)

        user = User(
            email=identity.email,
            hashed_password=None,
            full_name=identity.name,
        )
        self.db.add(user)
        self.db.flush()
        return self._bind_identity(user, identity)

    def _bind_identity(self, user: User, identity: GoogleIdentity) -> User:
        existing_google_identity = (
            self.db.query(ProviderIdentity)
            .filter(
                ProviderIdentity.provider == self.provider,
                ProviderIdentity.user_id == user.id,
            )
            .first()
        )
        if (
            existing_google_identity
            and existing_google_identity.provider_user_id != identity.sub
        ):
            raise GoogleIdentityLinkError("account_conflict")

        self.db.add(
            ProviderIdentity(
                provider=self.provider,
                provider_user_id=identity.sub,
                user_id=user.id,
                provider_email=identity.email,
                provider_email_verified=identity.email_verified,
            )
        )
        self.db.commit()
        self.db.refresh(user)
        return user
