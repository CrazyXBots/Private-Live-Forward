# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

from os import environ 

class Config:
    API_ID = int(environ.get("API_ID", ""))
    API_HASH = environ.get("API_HASH", "")
    BOT_TOKEN = environ.get("BOT_TOKEN", "") 
    BOT_SESSION = environ.get("BOT_SESSION", "vjbot") 
    DATABASE_URI = environ.get("DATABASE_URI", "")
    DATABASE_NAME = environ.get("DATABASE_NAME", "vj-forward-bot")
    BOT_OWNER = int(environ.get("BOT_OWNER", ""))

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

class temp(object): 
    lock = {}          # {user_id: {task_id: True/False}}
    CANCEL = {}        # {user_id: {task_id: True/False}}
    PAUSE = {}         # {user_id: {task_id: True/False}}
    forwardings = 0
    BANNED_USERS = []
    IS_FRWD_CHAT = []  # list of (user_id, task_id, dest_chat_id) tuples

    # ── Multi-task helpers ───────────────────────────────────
    @classmethod
    def init_user(cls, user_id):
        if user_id not in cls.lock:   cls.lock[user_id]   = {}
        if user_id not in cls.CANCEL: cls.CANCEL[user_id] = {}
        if user_id not in cls.PAUSE:  cls.PAUSE[user_id]  = {}

    @classmethod
    def set_task(cls, user_id, task_id, active=True):
        cls.init_user(user_id)
        cls.lock[user_id][task_id]   = active
        cls.CANCEL[user_id][task_id] = False
        cls.PAUSE[user_id][task_id]  = False

    @classmethod
    def cancel_task(cls, user_id, task_id):
        cls.init_user(user_id)
        cls.CANCEL[user_id][task_id] = True
        cls.lock[user_id][task_id]   = False

    @classmethod
    def pause_task(cls, user_id, task_id):
        cls.init_user(user_id)
        cls.PAUSE[user_id][task_id] = True

    @classmethod
    def resume_task(cls, user_id, task_id):
        cls.init_user(user_id)
        cls.PAUSE[user_id][task_id] = False

    @classmethod
    def is_cancelled(cls, user_id, task_id):
        return cls.CANCEL.get(user_id, {}).get(task_id, False)

    @classmethod
    def is_paused(cls, user_id, task_id):
        return cls.PAUSE.get(user_id, {}).get(task_id, False)

    @classmethod
    def is_locked(cls, user_id, task_id):
        return cls.lock.get(user_id, {}).get(task_id, False)

    @classmethod
    def active_task_count(cls, user_id):
        return sum(1 for v in cls.lock.get(user_id, {}).values() if v)

    @classmethod
    def clear_task(cls, user_id, task_id):
        for d in (cls.lock, cls.CANCEL, cls.PAUSE):
            d.get(user_id, {}).pop(task_id, None)
        cls.IS_FRWD_CHAT[:] = [
            x for x in cls.IS_FRWD_CHAT
            if not (x[0] == user_id and x[1] == task_id)
        ]

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
