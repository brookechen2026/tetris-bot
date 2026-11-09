"""
This file only exists to facilitate replacing it to change how the next tetronimo is picked.
"""

def new_tile():
    """Returns a tetromino shape number, which is between 1 and 7 inclusive"""
    import random
    return random.randrange(1,8)
