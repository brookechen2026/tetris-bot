def convert_bits_to_board(bit_rows):
    """将整数列表转换回二维列表（新增方法）"""
    board = [[0 for _ in range(10)] for _ in range(20)]
    for y in range(20):
        row = bit_rows[y]
        for x in range(10):
            shift = (9 - x) * 3
            value = (row >> shift) & 0b111
            board[y][x] = value
    return board

print(convert_bits_to_board([0]*17 + [268435456, 268435456, 269748741]))