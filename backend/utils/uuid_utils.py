import uuid
import asyncio

class AsyncUUIDPool:
    def __init__(self, pool_size=1000):
        self.pool = asyncio.Queue(maxsize=pool_size)
        self.pool_size = pool_size

    async def _fill_pool(self):
        for _ in range(self.pool_size):
            await self.pool.put(uuid.uuid4())

    async def start(self):
        # 初始化填充池子
        await self._fill_pool()
        # 后台补充
        asyncio.create_task(self._replenish_pool())

    async def _replenish_pool(self):
        while True:
            if self.pool.qsize() < self.pool_size:
                await self.pool.put(uuid.uuid4())
            await asyncio.sleep(0)  # 让出事件循环

    async def get_uuid(self):
        return await self.pool.get()

# 使用
uuid_pool = AsyncUUIDPool(pool_size=1000)

async def get_uuid() -> str:
    return str(await uuid_pool.get_uuid())

async def main():
    await uuid_pool.start()
    for _ in range(5):
        print(await get_uuid())

asyncio.run(main())
import uuid
import asyncio

class AsyncUUIDPool:
    def __init__(self, pool_size=1000):
        self.pool = asyncio.Queue(maxsize=pool_size)
        self.pool_size = pool_size

    async def _fill_pool(self):
        for _ in range(self.pool_size):
            await self.pool.put(uuid.uuid4())

    async def start(self):
        # 初始化填充池子
        await self._fill_pool()
        # 后台补充
        asyncio.create_task(self._replenish_pool())

    async def _replenish_pool(self):
        while True:
            if self.pool.qsize() < self.pool_size:
                await self.pool.put(uuid.uuid4())
            await asyncio.sleep(0)  # 让出事件循环

    async def get_uuid(self):
        return await self.pool.get()

# 使用
uuid_pool = AsyncUUIDPool(pool_size=1000)

async def get_uuid() -> str:
    return str(await uuid_pool.get_uuid())
