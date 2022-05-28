import time


class Player:
    def __init__(self, name, palette, **options) -> None:
        self.name = name
        self.palette = palette
        self.can_play = True
        self.lock_timer = time.time()
        self.lock_amount = options.get("max_lock_amount", 5)
        self.lock_cooldown = options.get("lock_cooldown", 20)  # in seconds

    def __eq__(self, __o: object) -> bool:
        return __o.name == self.name

    def to_json(self) -> str:
        return {"name": self.name, "palette": self.palette}

    def add_to_palette(self, palette):
        self.palette += palette

    def reset_palette(self, palette=None):
        self.palette = palette
        self.can_play = True

    def can_lock(self) -> bool:
        # initial lock timer + cooldown needs to be less than the current time,
        # that means at least cooldown seconds elapsed between last lock
        if self.lock_amount > 0 and self.lock_timer + self.lock_cooldown < time.time():
            self.lock_timer = time.time()
            self.lock_amount -= 1
            return True
        return False

    def steal_palette(self, victim: "Player") -> bool:
        if self.can_lock():
            self.add_to_palette(victim.palette)
            victim.palette = []
            victim.can_play = False
            return True
        return False
