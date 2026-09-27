# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01

import time as tm
from collections import deque
from database import Db, db
from .test import parse_buttons

STATUS = {}

# Number of recent "fetched" events kept per task to measure *live* speed.
# A rolling window means speed reflects what's happening right now, not the
# lifetime average (which stays artificially low for a long time after a
# FloodWait sleep).
_RATE_WINDOW = 40

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01


def format_duration(seconds) -> str:
    """Render a second count as a short human string, e.g. '1h 4m 12s'.
    Returns '0s' for zero/negative input instead of an empty string."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "—"
    if seconds <= 0:
        return "0s"
    weeks, seconds = divmod(seconds, 7 * 24 * 60 * 60)
    days, seconds = divmod(seconds, 24 * 60 * 60)
    hours, seconds = divmod(seconds, 60 * 60)
    minutes, seconds = divmod(seconds, 60)
    parts = []
    if weeks:   parts.append(f"{weeks}w")
    if days:    parts.append(f"{days}d")
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")
    return " ".join(parts)


class STS:
    def __init__(self, id):
        self.id = id
        self.data = STATUS

    def verify(self):
        return self.data.get(self.id)

    def store(self, From, to,  skip, limit):
        self.data[self.id] = {"FROM": From, 'TO': to, 'total_files': 0, 'skip': skip, 'limit': limit,
                      'fetched': skip, 'filtered': 0, 'deleted': 0, 'duplicate': 0, 'total': limit, 'start': 0,
                      '_ticks': deque(maxlen=_RATE_WINDOW)}
        self.get(full=True)
        return STS(self.id)

    def get(self, value=None, full=False):
        values = self.data.get(self.id)
        if not full:
           return values.get(value)
        for k, v in values.items():
            setattr(self, k, v)
        return self

    def add(self, key=None, value=1, time=False, start_time=None):
        if time:
          return self.data[self.id].update({'start': tm.time() if start_time is None else start_time})
        self.data[self.id].update({key: self.get(key) + value})
        if key == 'fetched':
           self._tick()

    def divide(self, no, by):
       by = 1 if int(by) == 0 else by 
       return int(no) / by

    # ── Live throughput / ETA ────────────────────────────────
    def _tick(self):
        """Record 'now' every time a message is processed, so speed can be
        measured over a recent rolling window instead of the whole task."""
        entry = self.data.get(self.id)
        if entry is None:
            return
        entry.setdefault('_ticks', deque(maxlen=_RATE_WINDOW)).append(tm.time())

    def speed_per_min(self) -> float:
        """Current throughput in messages/min, based on the last few
        processed messages. Returns 0.0 if there isn't enough data yet."""
        entry = self.data.get(self.id)
        if not entry:
            return 0.0
        ticks = entry.get('_ticks')
        if not ticks or len(ticks) < 2:
            return 0.0
        elapsed = ticks[-1] - ticks[0]
        if elapsed <= 0:
            return 0.0
        return (len(ticks) - 1) / elapsed * 60

    def eta_seconds(self):
        """Seconds remaining at current speed, or None if it can't be
        estimated yet (falls back to the lifetime average speed first)."""
        entry = self.data.get(self.id)
        if not entry:
            return None
        remaining = max(entry.get('total', 0) - entry.get('fetched', 0), 0)
        if remaining <= 0:
            return 0
        rate = self.speed_per_min()
        if rate <= 0:
            start = entry.get('start') or 0
            fetched = entry.get('fetched', 0)
            elapsed = tm.time() - start
            if start <= 0 or fetched <= 0 or elapsed <= 0:
                return None
            rate = fetched / elapsed * 60
            if rate <= 0:
                return None
        return int(remaining / rate * 60)

    def eta_string(self) -> str:
        secs = self.eta_seconds()
        return "calculating…" if secs is None else format_duration(secs)

    async def get_data(self, user_id):
        bot = await db.get_bot(user_id)
        if bot is None:
            bot = await db.get_userbot(user_id)
        k, filters = self, await db.get_filters(user_id)
        size, configs = None, await db.get_configs(user_id)
        if configs['duplicate']:
           duplicate = True
        else:
           duplicate = False
        try:
           min = configs['min_size']
           max = configs['max_size']
        except:
           min = 0
           max = 0
        button = parse_buttons(configs['button'] if configs['button'] else '')
        return bot, configs['caption'], configs['forward_tag'], {'filters': filters,
                'keywords': configs['keywords'], 'min_size': min, 'max_size': max, 'extensions': configs['extension'], 'skip_duplicate': duplicate, 'db_uri': configs['db_uri']}, configs['protect'], button

# Don't Remove Credit Tg - @VJ_Botz
# Subscribe YouTube Channel For Amazing Bot https://youtube.com/@Tech_VJ
# Ask Doubt on telegram @KingVJ01
