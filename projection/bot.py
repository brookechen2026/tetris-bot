import math

from aiohttp import web, WSMsgType
import aiohttp, asyncio

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

# 模拟俄罗斯方块
class MockTetris:
    """俄罗斯方块游戏核心逻辑类，管理游戏状态和规则"""
    def __init__(self):
        self.board = [[0 for _ in range(10)] for _ in range(20)]  # 初始化游戏区域
        self.cashBoard = [[0 for _ in range(10)] for _ in range(20)] # 游戏区域缓存

    def calculateCellPlace(self, cell_info):
        best_dx = 0
        best_angle = 0
        max_score = -float('inf')

        choice_cells = []
        # 尝试所有旋转角度
        for angle in range(len(SHAPES[cell_info[0]])):
            cells = self._get_tetromino_cells(cell_info[2],cell_info[3],cell_info[0],angle)
            # 尝试所有方向
            for dx in range(-6,7):
                cells_shifted = [(x + dx, y) for x, y in cells]
                if not self._check_collision(cells_shifted):
                    max_drop = self._calculate_max_drop(cells_shifted)
                    final_cells = [(x, y + max_drop) for (x, y) in cells_shifted]

                    # 创建临时棋盘
                    cash_board = [row.copy() for row in self.board]
                    for x, y in final_cells:
                        if 0 <= y < 20 and 0 <= x < 10:
                            cash_board[y][x] = 1  # 假设用1表示有方块

                    score = self.calculateScore(cash_board)
                    # 选择得分最高的dx，若得分相同则取较小的dx（更左的位置）
                    if score > max_score or (score == max_score and dx < best_dx):
                        max_score = score
                        best_dx = dx
                        best_angle = angle
                        choice_cells = final_cells.copy()
        for x, y in choice_cells:
            if 0 <= y < 20 and 0 <= x < 10:
                self.board[y][x] = 1  # 假设用1表示有方块

        return best_dx,best_angle

    def _get_tetromino_cells(self,live_x,live_y,live_shape,live_orientation):
        """获取当前方块所有单元格的绝对坐标"""
        return [
            (live_x + dx, live_y + dy)
            for dx, dy in SHAPES[live_shape][live_orientation]
        ]
    def _calculate_max_drop(self,cells):
        """计算当前方块可以立即下落的行数"""
        drop = 0
        while True:
            test = [(x, y + drop + 1) for x, y in cells]  # 测试下落drop+1行
            if self._check_collision(test):
                break
            drop += 1
        return drop

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

    def calculateScore(self,board):
        width = 10  # board为10列
        height = 20  # board为20行

        fullLines, nearFullLines = 0, 0
        roofY = [0] * width  # 各列的堆叠高度（从底部计算）
        holeCandidates = [0] * width  # 候选空洞数（需下方有方块确认）
        holeConfirm = [0] * width  # 已确认的空洞数
        vHoles, vBlocks = 0, 0  # 垂直方向空洞和方块统计

        # 从底部到顶部遍历每一行
        for y in range(height - 1, -1, -1):
            hasHole = False
            hasBlock = False
            for x in range(width):
                if board[y][x] == 0:  # 当前位置为空
                    hasHole = True
                    holeCandidates[x] += 1
                else:  # 当前位置有方块
                    hasBlock = True
                    # 更新该列的堆叠高度（记录最顶部的方块位置）
                    roofY[x] = height - y
                    # 若存在候选空洞，则确认并累加
                    if holeCandidates[x] > 0:
                        holeConfirm[x] += holeCandidates[x]
                        holeCandidates[x] = 0
                    # 统计位于空洞上方的方块
                    if holeConfirm[x] > 0:
                        vBlocks += 1
            # 若当前行无方块，提前结束遍历
            if not hasBlock:
                break
            # 统计完全填满的行
            if not hasHole and hasBlock:
                fullLines += 1

        # 计算垂直空洞的惩罚项（使用幂函数加权）
        vHoles = sum([x** 0.7 for x in holeConfirm])
        # 计算最大高度（减去消除的行数）
        maxHeight = max(roofY) - fullLines if roofY else 0

        # 计算相邻列高度差
        roofDy = [roofY[i] - roofY[i + 1] for i in range(len(roofY) - 1)]
        # 计算高度标准差
        stdY = math.sqrt(sum([y ** 2 for y in roofY]) / len(roofY) - (sum(roofY) / len(roofY)) ** 2) if len(roofY) else 0
        # 计算高度差标准差
        stdDY = math.sqrt(sum([d ** 2 for d in roofDy]) / len(roofDy) - (sum(roofDy) / len(roofDy)) ** 2) if len(roofDy) else 0
        # 计算高度差绝对值和及最大高度差
        absDy = sum(abs(d) for d in roofDy)
        maxDy = max(roofY) - min(roofY) if roofY else 0

        # 综合各项指标计算得分
        score = (
            fullLines * 1.8
            - vHoles * 1.0
            - vBlocks * 0.5
            - maxHeight ** 1.5 * 0.02
            - stdY * 0.0  # 此系数为0，可省略
            - stdDY * 0.01
            - absDy * 0.2
            - maxDy * 0.3
        )

        return score


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

async def play_games(client, url):
    """Main game connection and play logic."""
    alltasks.add(asyncio.current_task())
    asyncio.current_task().add_done_callback(taskdone)
    # 实例化一个模拟器
    mock = MockTetris()

    try:
        while True:
            await asyncio.sleep(2) # pause between games; feel free to change this
            try: ws = await client.ws_connect(url)
            except:
                print('Game server at', url, 'did not let the bot play')
                return
            wsoftask[asyncio.current_task()] = ws
            print('Starting a new game')
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    data = msg.json() # parse message from server
                    
                    
                    # replace code starting here
                    if 'board' in data:
                        board = convert_bits_to_board(data["board"])

                        for i,row in enumerate(board):
                            for j,val in enumerate(row):
                                if val == 0 and mock.board[i][j] != 0:
                                    print("不一致！,正在更新")
                                    mock.board = [row.copy() for row in board]



                        offset,angle = mock.calculateCellPlace(data["live"])
                        for i in range(angle):
                            await asyncio.sleep(0.1)  # pause to not look AI-like
                            await ws.send_str('cw')

                        if offset < 0:
                            for i in range(abs(offset)):
                                await asyncio.sleep(0.1)  # pause to not look AI-like
                                await ws.send_str('left')
                        else:
                            for i in range(abs(offset)):
                                await asyncio.sleep(0.1)  # pause to not look AI-like
                                await ws.send_str('right')
                        # await asyncio.sleep(0.2)  # pause to not look AI-like
                        await ws.send_str('drop')

                        print(offset,angle)


                    # replace code above here
                    
                    
                elif msg.type == WSMsgType.ERROR:
                    print(f'connection to {url} received {ws.exception()}')
            
    except BaseException as ex:
        print("Game terminated with exception:\n   ", type(ex),'\n   ', ex)


# Written by course staff. Do not edit.
routes = web.RouteTableDef()
alltasks = set() # track tasks we might need to cancel if the server stops
wsoftask = {}    # when a task opens a ws, that is added here

def taskdone(task):
    """Written by course staff. Do not edit.
    Helper method to clean up ws and tasks"""
    alltasks.discard(task)
    if task in wsoftask:
        asyncio.create_task(wsoftask[task].close())
        del wsoftask[task]

@routes.get('/')
async def get_html(request):
    """Written by course staff. Do not edit.
    Returns the HTML user interface"""
    return web.FileResponse("botui.html")

@routes.post('/server')
async def play_on_server(request):
    """Written by course staff. Do not edit.
    Connects the bot to a server"""
    url = await request.text()
    alltasks.add(asyncio.create_task(play_games(request.app['client'], url)))
    return web.Response(status=200, text="OK")

@routes.get('/stopall')
async def get_html(request):
    """Written by course staff. Do not edit.
    Returns the HTML user interface"""
    for task in tuple(alltasks):
        try: task.cancel()
        except: pass
    return web.Response(status=200, text="OK")

@routes.get('/watch.html')
async def watch_html(request):
    """返回监控页面"""
    return web.FileResponse("watch.html")
async def shutdown_ws(app):
    """Cleanup"""
    for task in tuple(alltasks):
        try: task.cancel()
        except: pass

async def startup_client(app):
    """A shared client for better DNS caching"""
    app['client'] = aiohttp.ClientSession()

async def shutdown_client(app):
    """Cleanup"""
    await app['client'].close()


def setup_app(app):
    """Register all the setup and cleanup callbacks"""
    app.on_startup.append(startup_client)
    app.on_shutdown.append(shutdown_ws)
    app.on_shutdown.append(shutdown_client)
    app.add_routes(routes)
    
if __name__ == '__main__': 
    app = web.Application()
    setup_app(app)
    web.run_app(app, host='localhostooo', port=41801) # this function never returns
