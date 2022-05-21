import random
import string

from django.conf import settings

words = {}

with open(settings.BASE_DIR / "tictactoe" / "util" / "words.txt") as f:
    words = set(f.read().lower().splitlines())


def generate_random_palette(amount: int) -> list:
    """Generates a palette 1xAmount or 1x26 max

    Args:
        amount (int): Length of the generated word palette

    Returns:
        list: Returns a list of shuffled ascii_uppercase letters
    """
    return random.sample(string.ascii_uppercase, amount)


def check_if_word(word: str) -> bool:
    """Checks if given word is indeed an actual word

    Args:
        word (str): Word to check

    Returns:
        bool: True or False depending if 'word' is in the words set
    """

    return word in words
