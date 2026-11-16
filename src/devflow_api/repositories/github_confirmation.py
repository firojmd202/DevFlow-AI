"""Atomic persistence for GitHub write authorizations."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from devflow_api.models.github_confirmation import GitHubConfirmation
from devflow_api.repositories.base import BaseRepository
from devflow_core.exceptions import ConfirmationAlreadyUsedError, ConfirmationMismatchError


class GitHubConfirmationRepository(BaseRepository[GitHubConfirmation]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(GitHubConfirmation, session)
        self._writers = async_sessionmaker(session.bind, expire_on_commit=False)

    async def get_by_id(self, confirmation_id: str | UUID) -> GitHubConfirmation | None:
        return await self.session.get(
            GitHubConfirmation, str(confirmation_id), populate_existing=True
        )

    async def consume_atomic(
        self,
        confirmation_id: str,
        now: datetime,
        *,
        repo_full_name: str,
        operation: str,
        parameters_hash: str,
        actor_id: str,
        workflow_run_id: int | None,
    ) -> GitHubConfirmation:
        async with self._writers() as writer:
            try:
                await writer.execute(text("BEGIN IMMEDIATE"))
                row = await writer.scalar(
                    select(GitHubConfirmation).where(GitHubConfirmation.id == confirmation_id)
                )
                if row is None or row.status != "ISSUED" or row.used_at is not None:
                    raise ConfirmationAlreadyUsedError()
                if (
                    row.repo_full_name,
                    row.operation,
                    row.parameters_hash,
                    row.actor_id,
                    row.workflow_run_id,
                ) != (repo_full_name, operation, parameters_hash, actor_id, workflow_run_id):
                    raise ConfirmationMismatchError()
                now = max(now, datetime.now(UTC))
                statement = (
                    update(GitHubConfirmation)
                    .where(
                        GitHubConfirmation.id == confirmation_id,
                        GitHubConfirmation.status == "ISSUED",
                        GitHubConfirmation.used_at.is_(None),
                        GitHubConfirmation.expires_at > now,
                    )
                    .values(status="USED", used_at=now)
                    .returning(GitHubConfirmation)
                    .execution_options(populate_existing=True)
                )
                result = (await writer.scalars(statement)).one_or_none()
                if result is None:
                    raise ConfirmationAlreadyUsedError()
                await writer.commit()
            except SQLAlchemyError:
                await writer.rollback()
                raise ConfirmationAlreadyUsedError() from None
            except BaseException:
                await writer.rollback()
                raise
            return result
