import asyncio
from httpx import AsyncClient

async def test_register():
    async with AsyncClient(base_url="http://127.0.0.1:8000") as client:
        response = await client.post(
            "/api/auth/register",
            json={
                "name": "Test User",
                "email": "test@abc.com",
                "password": "password123",
                "confirm_password": "password123"
            }
        )
        print("Register Status:", response.status_code)
        print("Register Response:", response.text)

if __name__ == "__main__":
    asyncio.run(test_register())
