import random
import string


def generate_random_palette(amount: int) -> list:
    """Generates a palatte 1xAmount or 1x26 max

    Args:
        amount (int): Length of the generated word palatte

    Returns:
        list: Returns a list of shuffled ascii_uppercase letters
    """
    lst = list(string.ascii_uppercase)
    random.shuffle(lst)
    return lst[:amount]
