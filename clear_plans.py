import asyncio
from study_bot.database.schema import get_conn

async def main():
    conn = await get_conn()
    await conn.execute("DELETE FROM study_plans")
    await conn.commit()
    await conn.close()
    print("Done - plans cleared")

asyncio.run(main())
