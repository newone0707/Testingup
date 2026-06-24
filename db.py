import os
from motor.motor_asyncio import AsyncIOMotorClient

MONGO_URL = os.environ.get("MONGO_URL", "")

class Database:
    def __init__(self):
        if MONGO_URL:
            self.client = AsyncIOMotorClient(MONGO_URL)
            self.db = self.client["BotDatabase"]
            self.users = self.db["users"]
            self.videos = self.db["videos"]
        else:
            self.client = None
            
    async def add_auth_user(self, user_id):
        if not self.client: return
        await self.users.update_one({"user_id": user_id}, {"$set": {"is_auth": True}}, upsert=True)
        
    async def remove_auth_user(self, user_id):
        if not self.client: return
        await self.users.update_one({"user_id": user_id}, {"$set": {"is_auth": False}}, upsert=True)
        
    async def is_auth_user(self, user_id):
        if not self.client: return False
        user = await self.users.find_one({"user_id": user_id})
        return user.get("is_auth", False) if user else False
        
    async def get_all_auth_users(self):
        if not self.client: return []
        cursor = self.users.find({"is_auth": True})
        return [doc["user_id"] async for doc in cursor]

    async def add_total_user(self, user_id):
        if not self.client: return
        await self.users.update_one({"user_id": user_id}, {"$set": {"is_total": True}}, upsert=True)

    async def is_total_user(self, user_id):
        if not self.client: return False
        user = await self.users.find_one({"user_id": user_id})
        return user.get("is_total", False) if user else False

    async def get_all_total_users(self):
        if not self.client: return []
        cursor = self.users.find({"is_total": True})
        return [doc["user_id"] async for doc in cursor]

    async def save_video(self, url, file_id, file_name):
        if not self.client: return
        await self.videos.update_one(
            {"url": url}, 
            {"$set": {"file_id": file_id, "file_name": file_name}}, 
            upsert=True
        )
        
    async def get_video(self, url):
        if not self.client: return None
        return await self.videos.find_one({"url": url})

db = Database()
