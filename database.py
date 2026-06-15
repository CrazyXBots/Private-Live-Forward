import motor.motor_asyncio
from config import Config

class Db:

    def __init__(self, uri, database_name):
        self._client = motor.motor_asyncio.AsyncIOMotorClient(uri)
        self.db = self._client[database_name]
        self.bot = self.db.bots
        self.userbot = self.db.userbot 
        self.col = self.db.users
        self.nfy = self.db.notify
        self.chl = self.db.channels 

    def new_user(self, id, name):
        return dict(
            id = id,
            name = name,
            ban_status=dict(
                is_banned=False,
                ban_reason="",
            ),
        )

    async def add_user(self, id, name):
        user = self.new_user(id, name)
        await self.col.insert_one(user)

    async def is_user_exist(self, id):
        user = await self.col.find_one({'id':int(id)})
        return bool(user)

    async def total_users_count(self):
        count = await self.col.count_documents({})
        return count

    async def total_users_bots_count(self):
        bcount = await self.bot.count_documents({})
        count = await self.col.count_documents({})
        return count, bcount

    async def remove_ban(self, id):
        ban_status = dict(
            is_banned=False,
            ban_reason=''
        )
        await self.col.update_one({'id': id}, {'$set': {'ban_status': ban_status}})

    async def ban_user(self, user_id, ban_reason="No Reason"):
        ban_status = dict(
            is_banned=True,
            ban_reason=ban_reason
        )
        await self.col.update_one({'id': user_id}, {'$set': {'ban_status': ban_status}})

    async def get_ban_status(self, id):
        default = dict(
            is_banned=False,
            ban_reason=''
        )
        user = await self.col.find_one({'id':int(id)})
        if not user:
            return default
        return user.get('ban_status', default)

    async def get_all_users(self):
        return self.col.find({})

    async def delete_user(self, user_id):
        await self.col.delete_many({'id': int(user_id)})

    async def get_banned(self):
        users = self.col.find({'ban_status.is_banned': True})
        b_users = [user['id'] async for user in users]
        return b_users

    async def update_configs(self, id, configs):
        await self.col.update_one({'id': int(id)}, {'$set': {'configs': configs}})

    async def get_configs(self, id):
        default = {
            'caption': None,
            'duplicate': True,
            'forward_tag': False,
            'min_size': 0,
            'max_size': 0,
            'extension': None,
            'keywords': None,
            'protect': None,
            'button': None,
            'db_uri': None,
            'filters': {
               'poll': True,
               'text': True,
               'audio': True,
               'voice': True,
               'video': True,
               'photo': True,
               'document': True,
               'animation': True,
               'sticker': True
            }
        }
        user = await self.col.find_one({'id':int(id)})
        if user:
            return user.get('configs', default)
        return default 

    async def add_bot(self, datas):
       if not await self.is_bot_exist(datas['user_id']):
          await self.bot.insert_one(datas)

    async def remove_bot(self, user_id):
       await self.bot.delete_many({'user_id': int(user_id)})

    async def get_bot(self, user_id: int):
       bot = await self.bot.find_one({'user_id': user_id})
       return bot if bot else None

    async def is_bot_exist(self, user_id):
       bot = await self.bot.find_one({'user_id': user_id})
       return bool(bot)
   
    async def add_userbot(self, datas):
       if not await self.is_userbot_exist(datas['user_id']):
          await self.userbot.insert_one(datas)

    async def remove_userbot(self, user_id):
       await self.userbot.delete_many({'user_id': int(user_id)})

    async def get_userbot(self, user_id: int):
       bot = await self.userbot.find_one({'user_id': user_id})
       return bot if bot else None

    async def is_userbot_exist(self, user_id):
       bot = await self.userbot.find_one({'user_id': user_id})
       return bool(bot)
    
    async def in_channel(self, user_id: int, chat_id: int) -> bool:
       channel = await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})
       return bool(channel)

    async def add_channel(self, user_id: int, chat_id: int, title, username):
       channel = await self.in_channel(user_id, chat_id)
       if channel:
         return False
       return await self.chl.insert_one({"user_id": user_id, "chat_id": chat_id, "title": title, "username": username})

    async def remove_channel(self, user_id: int, chat_id: int):
       channel = await self.in_channel(user_id, chat_id )
       if not channel:
         return False
       return await self.chl.delete_many({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_channel_details(self, user_id: int, chat_id: int):
       return await self.chl.find_one({"user_id": int(user_id), "chat_id": int(chat_id)})

    async def get_user_channels(self, user_id: int):
       channels = self.chl.find({"user_id": int(user_id)})
       return [channel async for channel in channels]

    async def get_filters(self, user_id):
       filters = []
       filter = (await self.get_configs(user_id))['filters']
       for k, v in filter.items():
          if v == False:
            filters.append(str(k))
       return filters

    async def add_frwd(self, user_id):
       return await self.nfy.insert_one({'user_id': int(user_id)})

    async def rmve_frwd(self, user_id=0, all=False):
       data = {} if all else {'user_id': int(user_id)}
       return await self.nfy.delete_many(data)

    async def get_all_frwd(self):
       return self.nfy.find({})
  
    async def forwad_count(self):
        c = await self.nfy.count_documents({})
        return c
        
    async def is_forwad_exit(self, user):
        u = await self.nfy.find_one({'user_id': user})
        return bool(u)
        
    async def get_forward_details(self, user_id):
        defult = {
            'chat_id': None,
            'forward_id': None,
            'toid': None,
            'last_id': None,
            'limit': None,
            'msg_id': None,
            'start_time': None,
            'fetched': 0,
            'offset': 0,
            'deleted': 0,
            'total': 0,
            'duplicate': 0,
            'skip': 0,
            'filtered' :0
        }
        user = await self.nfy.find_one({'user_id': int(user_id)})
        if user:
            return user.get('details', defult)
        return defult
   
    async def update_forward(self, user_id, details):
        await self.nfy.update_one({'user_id': user_id}, {'$set': {'details': details}})

# ================= MULTI-TASK FORWARD ================= #
#
#  Each user has a list of forward tasks stored in tasks[]:
#  {
#    "task_id":  str,   # unique e.g. "7298415492-0"
#    "active":   bool,
#    "msg_id":   int,   # progress message ID in user chat
#    "chat_id":  int,   # source channel
#    "toid":     int,   # destination channel
#    "skip":     int,
#    "limit":    int,
#    "fetched":  int,
#    "offset":   int,
#    "deleted":  int,
#    "total":    int,
#    "duplicate":int,
#    "filtered": int,
#    "start_time": float,
#    "forward_id": str,
#  }
# ====================================================== #

    async def get_all_tasks(self, user_id: int) -> list:
        user = await self.col.find_one({"id": int(user_id)})
        if not user:
            return []
        return user.get("fwd_tasks", [])

    async def get_task(self, user_id: int, task_id: str) -> dict | None:
        tasks = await self.get_all_tasks(user_id)
        for t in tasks:
            if t.get("task_id") == task_id:
                return t
        return None

    async def _save_tasks(self, user_id: int, tasks: list):
        await self.col.update_one(
            {"id": int(user_id)},
            {"$set": {"fwd_tasks": tasks}},
            upsert=True
        )

    async def add_task(self, user_id: int, task_data: dict):
        tasks = await self.get_all_tasks(user_id)
        # Remove old entry if exists (restart case)
        tasks = [t for t in tasks if t.get("task_id") != task_data["task_id"]]
        tasks.append(task_data)
        await self._save_tasks(user_id, tasks)

    async def update_task(self, user_id: int, task_id: str, details: dict):
        tasks = await self.get_all_tasks(user_id)
        for t in tasks:
            if t.get("task_id") == task_id:
                t.update(details)
                break
        await self._save_tasks(user_id, tasks)

    async def remove_task(self, user_id: int, task_id: str):
        tasks = await self.get_all_tasks(user_id)
        tasks = [t for t in tasks if t.get("task_id") != task_id]
        await self._save_tasks(user_id, tasks)

    async def remove_all_tasks(self, user_id: int):
        await self._save_tasks(user_id, [])

    async def get_all_active_task_users(self) -> list:
        cursor = self.col.find(
            {"fwd_tasks": {"$elemMatch": {"active": True}}},
            {"id": 1, "_id": 0}
        )
        return [doc["id"] async for doc in cursor]

# ================= SPEED CONTROL ================= #

    async def set_speed(self, user_id: int, speed: int):
        await self.col.update_one(
            {"id": int(user_id)},
            {"$set": {"speed": speed}},
            upsert=True
        )

    async def get_speed(self, user_id: int):
        user = await self.col.find_one({"id": int(user_id)})
        if not user:
            return 20
        return user.get("speed", 20)

# ================= PREMIUM ================= #

    async def set_premium(self, user_id: int, status: bool):
        await self.col.update_one(
            {"id": int(user_id)},
            {"$set": {"is_premium": status}},
            upsert=True
        )

    async def is_premium_user(self, user_id: int) -> bool:
        user = await self.col.find_one({"id": int(user_id)})
        if not user:
            return False
        return user.get("is_premium", False)

# ================= LIVE FORWARD (multi-connection) ================= #
#
#  Each user has a list of "connections" stored in live_connections[]:
#    {
#      "index":        int,   # 0–9
#      "active":       bool,
#      "source_id":    int | None,
#      "source_title": str | None,
#      "dest_id":      int | None,
#      "dest_title":   str | None,
#    }
# ================================================================== #

    async def get_live_connections(self, user_id: int) -> list:
        """Return all live-forward connections for a user."""
        user = await self.col.find_one({"id": int(user_id)})
        if not user:
            return []
        return user.get("live_connections", [])

    async def get_live_connection(self, user_id: int, idx: int) -> dict | None:
        """Return a single connection by index, or None."""
        conns = await self.get_live_connections(user_id)
        for c in conns:
            if c.get("index") == idx:
                return c
        return None

    async def add_live_connection(self, user_id: int) -> int:
        """Append a blank connection and return its index."""
        conns = await self.get_live_connections(user_id)
        # Find the next available index (fill gaps from deletions)
        used  = {c["index"] for c in conns}
        idx   = next(i for i in range(10) if i not in used)
        conns.append({
            "index":        idx,
            "active":       False,
            "mode":         "auto",   # "auto" | "bot" | "user"
            "source_id":    None,
            "source_title": None,
            "dest_id":      None,
            "dest_title":   None,
        })
        await self.col.update_one(
            {"id": int(user_id)},
            {"$set": {"live_connections": conns}},
            upsert=True
        )
        return idx

    async def set_live_connection_mode(self, user_id: int, idx: int, mode: str):
        """Set mode for a connection: 'auto', 'bot', or 'user'."""
        conns = await self.get_live_connections(user_id)
        for c in conns:
            if c["index"] == idx:
                c["mode"] = mode
                break
        await self._save_live_connections(user_id, conns)

    async def _save_live_connections(self, user_id: int, conns: list):
        await self.col.update_one(
            {"id": int(user_id)},
            {"$set": {"live_connections": conns}},
            upsert=True
        )

    async def set_live_connection_source(self, user_id: int, idx: int,
                                          chat_id: int, title: str):
        conns = await self.get_live_connections(user_id)
        for c in conns:
            if c["index"] == idx:
                c["source_id"]    = chat_id
                c["source_title"] = title
                break
        await self._save_live_connections(user_id, conns)

    async def set_live_connection_dest(self, user_id: int, idx: int,
                                        chat_id: int, title: str):
        conns = await self.get_live_connections(user_id)
        for c in conns:
            if c["index"] == idx:
                c["dest_id"]    = chat_id
                c["dest_title"] = title
                break
        await self._save_live_connections(user_id, conns)

    async def set_live_connection_active(self, user_id: int, idx: int, active: bool):
        conns = await self.get_live_connections(user_id)
        for c in conns:
            if c["index"] == idx:
                c["active"] = active
                break
        await self._save_live_connections(user_id, conns)

    async def delete_live_connection(self, user_id: int, idx: int):
        conns = await self.get_live_connections(user_id)
        conns = [c for c in conns if c["index"] != idx]
        await self._save_live_connections(user_id, conns)

    async def get_all_active_live_users(self) -> list:
        """Return user_ids who have at least one active live-forward connection."""
        # Use $elemMatch with explicit True boolean — avoids type mismatch issues
        cursor = self.col.find(
            {"live_connections": {"$elemMatch": {"active": True}}},
            {"id": 1, "_id": 0}
        )
        users = [doc["id"] async for doc in cursor]
        return users

# ================================================ #

db = Db(Config.DATABASE_URI, Config.DATABASE_NAME)
