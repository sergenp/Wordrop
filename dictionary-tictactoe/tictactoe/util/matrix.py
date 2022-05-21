import random
import string


def create_grid(rows: int, cols: int, letter_chance=5) -> list:
    """Creates a matrix filled with random letters.

    Args:
        rows (int): the number of rows the matrix should have
        cols (int): the number of columns the matrix should have
        letter_chance (int) : chance of a letter appearing in the matrix, 0 no chance(matrix has no letters), 101 max chance (matrix filled with letters)

    Returns:
        M (list): Returned matrix
    """
    M = []
    while len(M) < rows:
        M.append([])
        while len(M[-1]) < cols:
            if random.randint(0, 100) < letter_chance:
                M[-1].append(random.choice(string.ascii_uppercase))
            else:
                M[-1].append("")
    return M


def get_column(column: int, grid: list) -> list:
    """Gets the column as a 1xN list for given NxN matrix

    Args:
        column (int): column number
        matrix (list): matrix
    """
    return [row[column] for row in grid]


def get_cols(grid: list) -> list:
    return zip(*grid)


def get_rows(grid: list) -> list:
    return [[c for c in r] for r in grid]


def get_backward_diagonals(grid: list) -> list:
    b = [None] * (len(grid) - 1)
    grid = [b[i:] + r + b[:i] for i, r in enumerate(get_rows(grid))]
    return [[c for c in r if c is not None] for r in get_cols(grid)]


def get_forward_diagonals(grid: list) -> list:
    b = [None] * (len(grid) - 1)
    grid = [b[:i] + r + b[i:] for i, r in enumerate(get_rows(grid))]
    return [[c for c in r if c is not None] for r in get_cols(grid)]
