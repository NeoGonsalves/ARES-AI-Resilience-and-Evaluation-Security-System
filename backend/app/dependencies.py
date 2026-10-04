from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.models import Organization, Project, User


@dataclass(frozen=True)
class CurrentUser:
    id: str
    organization_id: str
    email: str


def get_current_user(
    db: Session = Depends(get_db),
    x_ares_user_email: str | None = Header(default=None),
) -> CurrentUser:
    """Development identity shim. Replace with OIDC/JWT verification before deployment."""
    settings = get_settings()
    if not x_ares_user_email and not settings.allow_dev_identity:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication is required.")
    email = (x_ares_user_email or "developer@local").strip().lower()
    if not email or len(email) > 320:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid caller identity.")

    organization = db.scalar(select(Organization).where(Organization.name == "Local development"))
    if organization is None:
        organization = Organization(name="Local development")
        db.add(organization)
        db.flush()
    user = db.scalar(select(User).where(User.organization_id == organization.id, User.email == email))
    if user is None:
        user = User(organization_id=organization.id, email=email, display_name=email.split("@")[0])
        db.add(user)
        db.flush()
        default_project = db.scalar(
            select(Project).where(Project.organization_id == organization.id, Project.name == "Default project")
        )
        if default_project is None:
            db.add(
                Project(
                    organization_id=organization.id,
                    created_by_user_id=user.id,
                    name="Default project",
                    description="Local development project",
                )
            )
    db.commit()
    return CurrentUser(id=user.id, organization_id=organization.id, email=user.email)
