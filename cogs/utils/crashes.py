from datetime import datetime, timedelta

import aiosqlite
from dateutil.relativedelta import relativedelta


class CrashHandler:
    def __init__(self):
        self.last_crash = None
        self.crashes = []

    async def log_crash(self) -> None:
        self.last_crash = datetime.now()
        self.crashes.append(self.last_crash)

    async def recommend_whitelist(self, current_whitelist: int = 5) -> bool:
        # get time difference of all crashes
        # Initialize a variable to store the total time difference
        if len(self.crashes) < 2:
            return False
        if current_whitelist != 5:
            if current_whitelist == 1:
                return False
            return True
        total_diff = timedelta()

        # Iterate through the array to calculate differences
        for i in range(1, min(4, len(self.crashes))):
            diff = self.crashes[i] - self.crashes[i - 1]
            total_diff += diff

        if total_diff.total_seconds() < 600:
            return True
        return False


async def whitelist_set(mode: int = 5) -> int:
    date_format = "%Y-%m-%d %H:%M:%S"

    if mode == 5:
        with open(
            r"whitelist\whitelist.txt",
            "w",
        ) as f:
            f.write("")
        return 0
    if mode == 4:
        async with aiosqlite.connect("database.sqlite", timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT uid FROM main")
            uids = await cursor.fetchall()
            with open(
                r"whitelist\whitelist.txt",
                "w",
            ) as f:
                for uid in uids:
                    uid = uid[0]
                    f.write(f"{uid}\n")
    elif mode == 3:
        async with aiosqlite.connect("database.sqlite", timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT * FROM main")
            uids = await cursor.fetchall()
            with open(
                r"whitelist\whitelist.txt",
                "w",
            ) as f:
                for uid in uids:
                    last_join = datetime.strptime(uid[8], date_format)
                    first_join = datetime.strptime(uid[7], date_format)
                    if last_join > (
                        datetime.now() - relativedelta(months=1)
                    ) and first_join < (datetime.now() - relativedelta(weeks=1)):
                        f.write(f"{uid[2]}\n")
    elif mode == 2:
        async with aiosqlite.connect("database.sqlite", timeout=10) as db:
            cursor = await db.cursor()
            await cursor.execute("SELECT titanfallID FROM connection")
            uids = await cursor.fetchall()
            with open(
                r"whitelist\whitelist.txt",
                "w",
            ) as f:
                for uid in uids:
                    uid = uid[0]
                    f.write(f"{uid}\n")
    elif mode == 1:
        with open(
            r"whitelist\whitelist.txt",
            "w",
        ) as f:
            f.write("0")
    with open(
        r"whitelist\whitelist.txt",
    ) as f:
        lines = f.readlines()
    return len(lines)
