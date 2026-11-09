# 导入所需库：aiohttp用于Web服务器和WebSocket支持，asyncio用于异步处理，json用于数据序列化，tilestub用于生成新方块
from aiohttp import web, WSMsgType
import asyncio
import json
import tilestub  # 假设该模块用于生成新的俄罗斯方块类型
import uuid  # 新增导入uuid库用于生成唯一游戏ID

# 定义路由表，用于处理HTTP请求路径
routes = web.RouteTableDef()
# 存储所有活跃WebSocket连接的字典，键为连接ID，值为WebSocket响应对象
allws = {}
game = None #Tetris实例

# 定义俄罗斯方块所有形状及其不同旋转状态下的坐标偏移（相对中心块）
# 键为方块类型编号，值为字典，其中键为旋转状态，值为相对坐标列表
SHAPES = {
    1: {  # O型方块，只有一种旋转状态
        0: [(0, 0), (1, 0), (0, -1), (1, -1)]
    },
    2: {  # I型（长条）方块，两种旋转状态
        0: [[0,0],[0,-1],[0,-2],[0,-3]],
        1: [[-1,0],[0,0],[1,0],[2,0]],
    },
    3: {  # T型方块，四种旋转状态
        0: [[-1,-1],[0,-1],[1,-1],[0,0]],
        1: [[-1,-1],[0,-1],[0,-2],[0,0]],
        2: [[-1,0],[0,0],[1,0],[0,-1]],
        3: [[0,0],[0,-1],[0,-2],[1,-1]],
    },
    4: {  # L型方块，四种旋转状态
        0: [[0,-2],[0,-1],[0,0],[1,0]],
        1: [[0,0],[0,-1],[1,-1],[2,-1]],
        2: [[-1,-2],[0,-2],[0,-1],[0,0]],
        3: [[-1,0],[0,0],[1,0],[1,-1]],
    },
    5: {  # J型方块，四种旋转状态
        0: [[-1,0],[0,0],[0,-1],[0,-2]],
        1: [[0,-1],[0,0],[1,0],[2,0]],
        2: [[0,0],[0,-1],[0,-2],[1,-2]],
        3: [[-1,-1],[0,-1],[1,-1],[1,0]],
    },
    6: {  # S型方块，两种旋转状态
        0: [[0,-2],[0,-1],[1,-1],[1,0]],
        1: [[-1,0],[0,0],[0,-1],[1,-1]],
    },
    7: {  # Z型方块，两种旋转状态
        0: [[1,-2],[1,-1],[0,-1],[0,0]],
        1: [[-1,-1],[0,-1],[0,0],[1,0]],
    }
}

# 记录每个方块类型支持的旋转状态总数
MAX_ORIENTATIONS = {s: len(SHAPES[s]) for s in SHAPES}

# 不同方块类型的初始Y坐标（防止某些形状生成时部分方块超出顶部）
INITIAL_Y = {
    1: 1,  # O型
    2: 3,  # I型（较长，需要更低的位置）
    3: 1,  # T型
    4: 2,  # L型
    5: 2,  # J型
    6: 2,  # S型
    7: 2   # Z型
}

class Tetris:
    """俄罗斯方块游戏核心逻辑类，管理游戏状态和规则"""
    def __init__(self, ws):
        self.ws = ws  # 关联的WebSocket连接
        self.snoopers = []  # 新增观察者列表
        self.board = [[0 for _ in range(10)] for _ in range(20)] # 游戏板，每行用整数表示（每3位存储一个方块类型）
        self.game_over = False  # 游戏结束标志

        self.snoopers = []  # 新增观察者列表
        # 初始化当前和下个方块
        self.live_shape = tilestub.new_tile()  # 当前下落中的方块类型
        self.next_shape = tilestub.new_tile()  # 下一个将出现的方块类型
        self.live_orientation = 0  # 当前旋转状态
        self.live_x = 4  # 当前方块的X坐标（中心点，0-9）
        self.live_y = INITIAL_Y[self.live_shape]  # 初始Y坐标

        self._send_state()  # 发送初始状态给客户端
        self.task = asyncio.create_task(self._tick())  # 创建自动下落的异步任务

    # 新增观察者管理方法
    def add_snooper(self, ws):
        """添加观察者连接"""
        self.snoopers.append(ws)

    def remove_snooper(self, ws):
        """移除观察者连接"""
        if ws in self.snoopers:
            self.snoopers.remove(ws)
    async def _tick(self):
        """定时下落任务，每0.5秒自动下落一次"""
        try:
            while not self.game_over:
                await asyncio.sleep(0.5)
                await self._move_down_internal()  # 执行下落
        except asyncio.CancelledError:
            pass  # 任务被取消时正常退出

    def _convert_board_to_bits(self):
        bit_rows = []
        for y in range(20):
            row = 0
            for x in range(10):
                # 将 self.board[y][x] 的值左移到正确的位置
                shift = (9 - x) * 3
                row |= (self.board[y][x] & 0b111) << shift
            bit_rows.append(row)
        return bit_rows

    def _send_state(self, include_board=True):
        """向客户端发送当前游戏状态"""
        msg = {
            "live": [
                self.live_shape,  # 当前方块类型
                self.live_orientation,  # 当前旋转状态
                self.live_x,  # 当前X坐标
                self.live_y,  # 当前Y坐标
                self._calculate_max_drop()  # 可下落的最大行数（用于快速下落）
            ],
            "next": self.next_shape  # 下一个方块类型
        }
        if include_board:
            msg["board"] = self._convert_board_to_bits()  # 包含完整的棋盘数据
        if self.game_over:
            msg["event"] = "gameover"  # 游戏结束事件
        if not self.ws.closed:
            asyncio.create_task(self.ws.send_str(json.dumps(msg)))  # 异步发送消息

        # 发送给所有观察者
        for snooper in self.snoopers:
            if not snooper.closed:
                asyncio.create_task(snooper.send_str(json.dumps(msg)))

    def _get_tetromino_cells(self):
        """获取当前方块所有单元格的绝对坐标"""
        return [
            (self.live_x + dx, self.live_y + dy)
            for dx, dy in SHAPES[self.live_shape][self.live_orientation]
        ]

    def _check_collision(self, cells):
        """检查给定坐标是否与棋盘或边界发生碰撞"""
        for x, y in cells:
            # 水平边界检查
            if x < 0 or x >= 10 or y >= 20:
                return True
            # 垂直方向只需检查y>=0的情况（允许部分方块在顶部生成）
            if y < 0:
                continue

            if self.board[y][x] != 0:
                return True
        return False

    def _calculate_max_drop(self):
        """计算当前方块可以立即下落的行数"""
        cells = self._get_tetromino_cells()
        drop = 0
        while True:
            test = [(x, y + drop + 1) for x, y in cells]  # 测试下落drop+1行
            if self._check_collision(test):
                break
            drop += 1
        return drop

    async def _move_down_internal(self):
        """处理自动下落逻辑"""
        if self.game_over:
            return
        down = [(x, y + 1) for x, y in self._get_tetromino_cells()]
        if not self._check_collision(down):
            self.live_y += 1  # 无碰撞则下落
            self._send_state(include_board=False)  # 仅更新方块位置，不发送完整棋盘
        else:
            # 碰撞发生，固定方块到棋盘并生成新方块
            self._fix_to_board()
            self._clear_rows()
            self._spawn()
            self._send_state()  # 需要发送完整棋盘更新

    def _fix_to_board(self):
        """将当前方块固定到棋盘上"""
        for x, y in self._get_tetromino_cells():
            if 0 <= y < 20:  # 只处理有效行
                self.board[y][x] = self.live_shape

    def _clear_rows(self):
        """清除填满的行并更新棋盘"""
        new_board = []
        for i,row in enumerate(self.board):
            for x in range(10):
                if row[x] == 0:
                    break
            else:
                for x in range(10):
                    row[x] = 0

                for j in range(i,0,-1):
                    self.board[j],self.board[j-1] = self.board[j-1],self.board[j]


    def _spawn(self):
        """生成新方块并检查游戏是否结束"""
        self.live_shape = self.next_shape
        self.next_shape = tilestub.new_tile()
        self.live_orientation = 0
        self.live_x = 4
        self.live_y = INITIAL_Y[self.live_shape]

        # 检查新方块是否立即发生碰撞（游戏结束条件）
        if self._check_collision(self._get_tetromino_cells()):
            self.game_over = True

    # 以下方法处理用户输入操作
    def move_left(self):
        """向左移动方块，返回是否移动成功"""
        if self.game_over:
            return False
        test = [(x - 1, y) for x, y in self._get_tetromino_cells()]
        if not self._check_collision(test):
            self.live_x -= 1
            self._send_state(include_board=False)
            return True
        return False

    def move_right(self):
        """向右移动方块，返回是否移动成功"""
        if self.game_over:
            return False
        test = [(x + 1, y) for x, y in self._get_tetromino_cells()]
        if not self._check_collision(test):
            self.live_x += 1
            self._send_state(include_board=False)
            return True
        return False

    def move_down(self):
        """手动下落方块，返回是否成功下落"""
        if self.game_over:
            return False
        down = [(x, y + 1) for x, y in self._get_tetromino_cells()]
        if not self._check_collision(down):
            self.live_y += 1
            self._send_state(include_board=False)
            return True
        # 碰撞时固定方块并生成新方块
        self._fix_to_board()
        self._clear_rows()
        self._spawn()
        self._send_state()
        return False

    def drop(self):
        """快速下落到底部"""
        if self.game_over:
            return False
        self.live_y += self._calculate_max_drop()
        self._fix_to_board()
        self._clear_rows()
        self._spawn()
        self._send_state()
        return True

    def rotate(self, clockwise=True):
        """旋转方块，顺时针或逆时针"""
        if self.game_over:
            return False

        old_o, old_x, old_y = self.live_orientation, self.live_x, self.live_y
        # 计算新的旋转状态
        new_o = (old_o + (1 if clockwise else -1)) % MAX_ORIENTATIONS[self.live_shape]

        # 获取新旋转状态的相对坐标并转换为绝对坐标
        new_relative = SHAPES[self.live_shape][new_o]
        absolute_cells = [(old_x + dx, old_y + dy) for dx, dy in new_relative]

        # 调整X坐标防止越界
        min_x = min(x for x, _ in absolute_cells)
        max_x = max(x for x, _ in absolute_cells)
        dx = 0
        if min_x < 0:
            dx = -min_x
        elif max_x >= 10:
            dx = 9 - max_x

        # 调整Y坐标防止越界
        min_y = min(y for _, y in absolute_cells)
        max_y = max(y for _, y in absolute_cells)
        dy = 0
        if min_y < 0:
            dy = -min_y
        elif max_y >= 20:
            dy = 19 - max_y

        # 应用调整后的坐标
        new_x = old_x + dx
        new_y = old_y + dy
        adjusted_cells = [(new_x + dx_rel, new_y + dy_rel) for dx_rel, dy_rel in new_relative]

        # 尝试应用旋转并检查碰撞
        self.live_orientation = new_o
        self.live_x = new_x
        self.live_y = new_y

        if not self._check_collision(adjusted_cells):
            self._send_state(include_board=False)
            return True
        else:  # 如果碰撞则回滚状态
            self.live_orientation = old_o
            self.live_x = old_x
            self.live_y = old_y
            return False

    def cleanup(self):
        """清理资源，取消定时任务"""
        if hasattr(self, "task") and not self.task.done():
            self.task.cancel()


    # 新增观察者管理方法
    def add_snooper(self, ws):
        """添加观察者连接"""
        self.snoopers.append(ws)

# @routes.get('/ws')
# async def ws_handler(request):
#     """处理WebSocket连接"""
#     ws = web.WebSocketResponse()
#     await ws.prepare(request)
#     allws[id(ws)] = ws  # 记录新连接
#     global game
#     game = Tetris(ws)  # 为每个连接创建独立游戏实例

#     async for msg in ws:  # 处理客户端消息
#         if msg.type == WSMsgType.TEXT:
#             cmd = msg.data.strip()
#             # 根据命令调用对应操作方法
#             if cmd == 'left':  game.move_left()
#             if cmd == 'right': game.move_right()
#             if cmd == 'down':  game.move_down()
#             if cmd == 'drop':  game.drop()
#             if cmd == 'cw':    game.rotate(True)   # 顺时针旋转
#             if cmd == 'ccw':   game.rotate(False)  # 逆时针旋转
#         elif msg.type == WSMsgType.ERROR:
#             print(f"WebSocket error: {ws.exception()}")

#     # 连接关闭后的清理操作
#     game.cleanup()
#     del allws[id(ws)]
#     return ws

@routes.get('/ws')
async def ws_handler(request):
    ws = web.WebSocketResponse()
    await ws.prepare(request)
    allws[id(ws)] = ws

    # 为当前连接单独创建一个 Tetris 实例，保存在局部变量 tetris
    tetris = Tetris(ws)

    async for msg in ws:
        if msg.type == WSMsgType.TEXT:
            cmd = msg.data.strip()
            if cmd == 'left':   tetris.move_left()
            elif cmd == 'right':tetris.move_right()
            elif cmd == 'down': tetris.move_down()
            elif cmd == 'drop': tetris.drop()
            elif cmd == 'cw':   tetris.rotate(True)
            elif cmd == 'ccw':  tetris.rotate(False)
        elif msg.type == WSMsgType.ERROR:
            print(f"WebSocket error: {ws.exception()}")

    # 连接关闭时，用同一个实例清理
    tetris.cleanup()
    del allws[id(ws)]
    return ws


@routes.get('/')
async def index(request):
    """返回游戏客户端页面"""
    return web.FileResponse('index.html')


# 新增/snoop端点处理观察者连接
@routes.get('/snoop')
async def snoop_handler(request):

    if not game:
        return web.Response(status=404, text="Game not found")

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # 注册观察者并发送初始状态
    game.add_snooper(ws)
    try:
        # 主动发送完整初始状态
        initial_msg = {
            "live": [
                game.live_shape,
                game.live_orientation,
                game.live_x,
                game.live_y,
                game._calculate_max_drop()
            ],
            "next": game.next_shape,
            "board": game._convert_board_to_bits(),
        }
        if game.game_over:
            initial_msg["event"] = "gameover"
        await ws.send_str(json.dumps(initial_msg))

        # 保持连接开启
        async for msg in ws:
            if msg.type == WSMsgType.ERROR:
                print(f"Snooper error: {ws.exception()}")
    finally:
        game.remove_snooper(ws)

    return ws

async def shutdown(app):
    """应用关闭时清理所有WebSocket连接"""
    for ws in list(allws.values()):
        await ws.close()
    allws.clear()

def setup_app(app):
    """配置aiohttp应用"""
    app.add_routes(routes)  # 添加路由
    app.on_shutdown.append(shutdown)  # 注册关闭钩子

if __name__ == '__main__':
    app = web.Application()
    setup_app(app)
    web.run_app(app, port=10340)  # 启动服务器