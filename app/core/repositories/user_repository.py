from typing import Optional
from sqlalchemy import select, update, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.models.user import User, UserRole


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_by_tg_id(self, tg_id: int) -> Optional[User]:
        stmt = select(User).where(User.tg_id == tg_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, tg_id: int, username: Optional[str] = None) -> User:
        user = User(tg_id=tg_id, username=username)
        self.session.add(user)
        await self.session.commit()
        await self.session.refresh(user)
        return user

    async def update_role(self, tg_id: int, role: UserRole) -> bool:
        stmt = update(User).where(User.tg_id == tg_id).values(role=role)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def update_family_id(self, tg_id: int, family_id: str) -> bool:
        stmt = update(User).where(User.tg_id == tg_id).values(family_id=family_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_partner(self, user: User) -> Optional[User]:
        if not user.family_id:
            return None
        stmt = select(User).where(
            User.family_id == user.family_id,
            User.id != user.id
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def delete_user(self, tg_id: int) -> bool:
        stmt = delete(User).where(User.tg_id == tg_id)
        result = await self.session.execute(stmt)
        await self.session.commit()
        return result.rowcount > 0

    async def get_users_by_family(self, family_id: str) -> list[User]:
        stmt = select(User).where(User.family_id == family_id)
        result = await self.session.execute(stmt)
        return result.scalars().all()