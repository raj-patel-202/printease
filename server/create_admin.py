import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import select
from models.database import AsyncSessionLocal
from models.models import Admin
from authentication.auth import hash_password

async def create_admin():
    print("=== Create Admin Account ===")
    email = input("Enter admin email: ").strip()
    if not email:
        print("Email cannot be empty.")
        return

    password = input("Enter admin password: ").strip()
    if not password:
        print("Password cannot be empty.")
        return

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Admin).where(Admin.email == email))
        if result.scalar_one_or_none():
            print(f"Error: Admin with email '{email}' already exists!")
            return

        hashed = hash_password(password)
        new_admin = Admin(email=email, password_hash=hashed)
        
        try:
            session.add(new_admin)
            await session.commit()
            print(f"Success! Admin account created for '{email}'.")
            print("You can now log in at /admin/login")
        except Exception as e:
            await session.rollback()
            print(f"Failed to create admin: {e}")

if __name__ == "__main__":
    asyncio.run(create_admin())
