"""User management service for Phase 6."""

from datetime import UTC, datetime

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from mcp_server.models.database import AuditLog, MagicLink, Store, Tenant
from mcp_server.models.database import Session as SessionModel
from mcp_server.utils.logging import logger


class UserService:
    """Service for managing users (tenants) - for master key holder admin."""

    def __init__(self, db: Session):
        self.db = db

    async def list_users(
        self, limit: int = 100, offset: int = 0, search: str | None = None
    ):
        """
        List all users with statistics.

        Args:
            limit: Number of users to return
            offset: Offset for pagination
            search: Search by email

        Returns:
            List of users with statistics
        """
        query = self.db.query(Tenant)

        # Search filter
        if search:
            query = query.filter(Tenant.email.ilike(f"%{search}%"))

        # Order by created date (newest first)
        query = query.order_by(desc(Tenant.created_at))

        # Pagination
        users = query.limit(limit).offset(offset).all()

        # Get statistics for each user
        result = []
        for user in users:
            # Count stores
            store_count = (
                self.db.query(func.count(Store.id))
                .filter(Store.tenant_id == user.id)
                .scalar()
            )

            result.append(
                {
                    "id": user.id,
                    "email": user.email,
                    "email_verified": user.email_verified,
                    "created_at": user.created_at,
                    "last_login": user.last_login,
                    "last_activity": user.last_activity,
                    "store_count": store_count,
                }
            )

        return result

    async def get_user(self, user_id: str):
        """
        Get user details with statistics.

        Args:
            user_id: Tenant ID

        Returns:
            User details with statistics or None
        """
        user = self.db.query(Tenant).filter(Tenant.id == user_id).first()
        if not user:
            return None

        # Get stores
        stores = self.db.query(Store).filter(Store.tenant_id == user_id).all()

        # Get audit log count
        audit_count = (
            self.db.query(func.count(AuditLog.id))
            .filter(AuditLog.tenant_id == user_id)
            .scalar()
        )

        # Get session count
        session_count = (
            self.db.query(func.count(SessionModel.id))
            .filter(SessionModel.tenant_id == user_id)
            .scalar()
        )

        return {
            "id": user.id,
            "email": user.email,
            "email_verified": user.email_verified,
            "created_at": user.created_at,
            "updated_at": user.updated_at,
            "last_login": user.last_login,
            "last_activity": user.last_activity,
            "store_count": len(stores),
            "stores": stores,
            "audit_log_count": audit_count,
            "session_count": session_count,
        }

    async def delete_user(self, user_id: str, deleted_by: str) -> bool:
        """
        Delete user and ALL their data (cascade delete).

        Deletes:
        - User's stores
        - User's audit logs
        - User's sessions
        - User's magic links
        - User's master key metadata
        - The user tenant record

        Args:
            user_id: Tenant ID to delete
            deleted_by: ID of user performing deletion (for audit)

        Returns:
            True if deleted, False if not found
        """
        user = self.db.query(Tenant).filter(Tenant.id == user_id).first()
        if not user:
            return False

        # Get counts for logging
        store_count = (
            self.db.query(func.count(Store.id))
            .filter(Store.tenant_id == user_id)
            .scalar()
        )
        audit_count = (
            self.db.query(func.count(AuditLog.id))
            .filter(AuditLog.tenant_id == user_id)
            .scalar()
        )

        logger.info(
            "Deleting user and all data",
            user_id=user_id,
            email=user.email,
            store_count=store_count,
            audit_count=audit_count,
            deleted_by=deleted_by,
        )

        # Delete in order (respect foreign keys)
        # 1. Delete stores (CASCADE will handle audit logs via FK)
        self.db.query(Store).filter(Store.tenant_id == user_id).delete()

        # 2. Delete audit logs
        self.db.query(AuditLog).filter(AuditLog.tenant_id == user_id).delete()

        # 3. Delete sessions
        self.db.query(SessionModel).filter(SessionModel.tenant_id == user_id).delete()

        # 4. Delete magic links
        self.db.query(MagicLink).filter(MagicLink.tenant_id == user_id).delete()

        # 5. Delete master key metadata
        from mcp_server.models.database import MasterKeyMetadata

        self.db.query(MasterKeyMetadata).filter(
            MasterKeyMetadata.tenant_id == user_id
        ).delete()

        # 6. Finally, delete the user
        self.db.delete(user)
        self.db.commit()

        logger.info(
            "User deleted successfully",
            user_id=user_id,
            email=user.email,
            deleted_by=deleted_by,
        )

        return True

    async def update_last_login(self, user_id: str) -> None:
        """
        Update user's last login timestamp.

        Args:
            user_id: Tenant ID
        """
        user = self.db.query(Tenant).filter(Tenant.id == user_id).first()
        if user:
            user.last_login = datetime.now(UTC)  # type: ignore[assignment]
            user.last_activity = datetime.now(UTC)  # type: ignore[assignment]
            self.db.commit()

    async def update_last_activity(self, user_id: str) -> None:
        """
        Update user's last activity timestamp.

        Args:
            user_id: Tenant ID
        """
        user = self.db.query(Tenant).filter(Tenant.id == user_id).first()
        if user:
            user.last_activity = datetime.now(UTC)  # type: ignore[assignment]
            self.db.commit()

    async def get_user_count(self) -> int:
        """Get total number of users."""
        return self.db.query(func.count(Tenant.id)).scalar()
