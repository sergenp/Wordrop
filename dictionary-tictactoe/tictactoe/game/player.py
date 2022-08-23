import time
from typing import List


class Player:
    def __init__(
        self, name: str, palette: list, steal_amount: int = 5, steal_cooldown: int = 10, **options
    ) -> None:
        self.name = name
        self.palette = palette
        self.can_play = True
        self.steal_timer = time.time()
        self.steal_amount = steal_amount
        self.steal_cooldown = steal_cooldown  # in seconds

    def __eq__(self, __o: object) -> bool:
        return __o.name == self.name

    def to_json(self) -> str:
        return {
            "name": self.name,
            "palette": self.palette,
            "can_play": self.can_play,
            "steal_amount": self.steal_amount,
            "steal_cooldown": self.steal_cooldown,
        }

    def add_to_palette(self, palette: List[str]) -> None:
        self.palette += palette

    def reset_palette(self, palette: List[str] = None) -> None:
        self.palette = palette
        self.can_play = True

    def can_steal(self) -> bool:
        # initial lock timer + cooldown needs to be less than the current time,
        # that means at least cooldown seconds elapsed between last lock
        if can_steal := (
            self.steal_amount > 0 and self.steal_timer + self.steal_cooldown < time.time()
        ):
            self.steal_timer = time.time()
            self.steal_amount -= 1

        return can_steal

    def steal_palette(self, victim: "Player") -> bool:

        if can_steal := self.can_steal():
            self.add_to_palette(victim.palette)
            victim.palette = []
            victim.can_play = False

        return can_steal
