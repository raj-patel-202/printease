import asyncio
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).parent.parent))

from sqlalchemy import select
from models.database import AsyncSessionLocal
from models.models import Admin
from authentication.auth import hash_password

async def main():
    email = input("Enter admin email: ").strip()
    password = input("Enter admin password: ").strip()

    if not email or not password:
        print("Email and password are required.")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Admin).where(Admin.email == email))
        existing_admin = result.scalars().first()

        if existing_admin:
            print("An admin with this email already exists.")
            return

        new_admin = Admin(
            email=email,
            password_hash=hash_password(password)
        )
        db.add(new_admin)
        await db.commit()

        print(f"Admin '{email}' successfully created!")

if __name__ == "__main__":
    asyncio.run(main())
