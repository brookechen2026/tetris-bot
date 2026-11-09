import pytest, asyncio
from aiohttp import web
import tilestub

tile_loop = list(range(1,8))
def loop_tiles():
    global tile_loop
    tile_loop.append(tile_loop.pop(0))
    return tile_loop[-1]

tilestub.new_tile = loop_tiles

import tetris

async def timeout_ws(ws, secs) -> None:
    for k in range(secs*10):
        await asyncio.sleep(0.1)
        if ws.closed: return
    await ws.close()

async def game_start_helper(aiohttp_client, shapes, timeout=1):
    global tile_loop
    tile_loop = list(shapes)
    app = web.Application()
    tetris.setup_app(app)
    client = await aiohttp_client(app)
    ws = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws, timeout))
    return ws
    

@pytest.mark.parametrize('shape', range(1,8))
async def test_positions(aiohttp_client, shape):
    other = (shape%7)+1
    ws = await game_start_helper(aiohttp_client, [shape, other])

    msg = await ws.receive_json()

    assert 'event' not in msg

    assert 'board' in msg
    assert msg['board'] == [0]*20, "Starting board state"

    assert 'live' in msg
    assert msg['live'][0] == shape, f"Use new_tile to pick first live shape"
    assert msg['live'][1] == 0, f"Starting orientation for shape {shape}"
    assert msg['live'][2] == 4, f"Starting x coordinate for shape {shape}"
    assert msg['live'][3] == (1,3,1,2,2,2,2)[shape-1], f"Starting y coordinate for shape {shape}"
    assert msg['live'][4] == (18,16,18,17,17,17,17)[shape-1], f"Drop distance for shape {shape}"
    
    assert 'next' in msg
    assert msg['next'] == other, f"Use new_tile to pick first next shape"

async def test_create_task(aiohttp_client):
    import time
    times = []

    times.append(time.time())
    ws = await game_start_helper(aiohttp_client, range(1,8), timeout=3)
    times.append(time.time())
    for k in range(4):
        msg = await ws.receive_json()
        times.append(time.time())

    assert times[1]-times[0] < 0.1, "connecting a websocket should be fast"
    assert times[2]-times[1] < 0.1, "first message should come immediately"
    assert 0.45 < times[3]-times[2] < 0.55, "second message should come after 0.5 seconds"
    assert 0.45 < times[4]-times[3] < 0.55, "third message should come after 1.0 seconds"
    assert 0.45 < times[5]-times[4] < 0.55, "fourth message should come after 1.5 seconds"

async def test_create_several_games(aiohttp_client):
    global tile_loop
    tile_loop = list(range(1,8))
    app = web.Application()
    tetris.setup_app(app)
    client = await aiohttp_client(app)
    
    ws1 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws1, 1))
    r1 = await ws1.receive_json()
    await ws1.send_str('drop'); r1b = await ws1.receive_json()
    
    ws2 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws2, 1))
    r2 = await ws2.receive_json()
    
    ws3 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws3, 1))
    r3 = await ws3.receive_json()

    await ws1.send_str('drop'); r1c = await ws1.receive_json()
    await ws2.send_str('drop'); r2b = await ws2.receive_json()
    
    assert r1['live'][0] == 1
    assert r1b['live'][0] == 2
    assert r1b['board'] == [0]*18 + [36864,36864]
    assert r2['live'][0] == 4
    assert r2['board'] == [0]*20
    assert r3['live'][0] == 6
    assert r3['board'] == [0]*20
    assert r1c['board'] == [0]*14 + [65536,65536,65536,65536,36864,36864]
    assert r2b['board'] == [0]*17 + [131072,131072,147456]
    

async def test_create_task_per_game_1(aiohttp_client):
    import time
    times = []
    
    global tile_loop
    tile_loop = list(range(1,8))
    app = web.Application()
    tetris.setup_app(app)
    client = await aiohttp_client(app)
    
    ws1 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws1, 3))
    r1 = await ws1.receive_json()
    
    ws2 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws2, 3))
    r2 = await ws2.receive_json()
    
    times.append(time.time())
    
    await ws1.receive_json()
    times.append(time.time())
    await ws2.receive_json()
    times.append(time.time())
    await ws2.receive_json()
    times.append(time.time())
    await ws1.receive_json()
    times.append(time.time())
    
    assert 0.45 < times[1]-times[0] < 0.55, "timer for first game"
    assert times[2]-times[1] < 0.1, "both timers concurrent"
    assert 0.45 < times[3]-times[2] < 0.55, "timer for second game"
    assert times[4]-times[3] < 0.1, "both timers concurrent"

async def test_create_task_per_game_2(aiohttp_client):
    import time
    times = []
    
    global tile_loop
    tile_loop = list(range(1,8))
    app = web.Application()
    tetris.setup_app(app)
    client = await aiohttp_client(app)
    
    ws1 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws1, 3))
    r1 = await ws1.receive_json()
    
    await asyncio.sleep(0.25)
    
    ws2 = await client.ws_connect("/ws")
    asyncio.create_task(timeout_ws(ws1, 3))
    r2 = await ws2.receive_json()
    
    times.append(time.time())
    
    await ws1.receive_json()
    times.append(time.time())
    await ws2.receive_json()
    times.append(time.time())
    await ws1.receive_json()
    times.append(time.time())
    await ws2.receive_json()
    times.append(time.time())
    
    assert 0.2 < times[1]-times[0] < 0.3, "timer for first game runs during sleep"
    assert 0.2 < times[2]-times[1] < 0.3, "timer for second game runs during first"
    assert 0.2 < times[3]-times[2] < 0.3, "timer for first game runs during second"

    
async def test_keys_2(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2]) # only I
    await ws.receive_json() # ignore board setup
    
    await ws.send_str("left")
    r1 = await ws.receive_json()
    await ws.send_str("down")
    r2 = await ws.receive_json()
    await ws.send_str("ccw")
    r3 = await ws.receive_json()
    await ws.send_str("right")
    r4 = await ws.receive_json()
    await ws.send_str("cw")
    r5 = await ws.receive_json()
    await ws.send_str("drop")
    r6 = await ws.receive_json()

    assert r1['live'] == [2,0, 3,3, 16]
    assert r2['live'] == [2,0, 3,4, 15]
    assert r3['live'] == [2,1, 3,4, 15]
    assert r4['live'] == [2,1, 4,4, 15]
    assert r5['live'] == [2,0, 4,4, 15]
    assert r6['live'] == [2,0, 4,3, 12]
    assert r6['board'] == [0]*16+[65536]*4
    
async def test_keys_5(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [5]) # only J
    r0 = await ws.receive_json()
    
    await ws.send_str("left")
    r1 = await ws.receive_json()
    await ws.send_str("left")
    r2 = await ws.receive_json()
    await ws.send_str("down")
    r3 = await ws.receive_json()
    await ws.send_str("ccw")
    r4 = await ws.receive_json()
    await ws.send_str("right")
    r5 = await ws.receive_json()
    await ws.send_str("cw")
    r6 = await ws.receive_json()
    await ws.send_str("drop")
    r7 = await ws.receive_json()
    await ws.send_str("drop")
    r8 = await ws.receive_json()

    assert r3['live'] == [5,0, 2,3, 16]
    assert r4['live'] == [5,3, 2,3, 16]
    assert r5['live'] == [5,3, 3,3, 16]
    assert r6['live'] == [5,0, 3,3, 16]
    assert r7['live'] == [5,0, 4,2, 14]
    assert r7['board'] == [0]*17 + [1310720, 1310720, 11796480]
    assert r8['live'] == [5,0, 4,2, 11]
    assert r8['board'] == [0]*14 + [163840, 163840, 1474560, 1310720, 1310720, 11796480]
    
async def test_clear_rows_1(aiohttp_client):
    """Create the following board:
        OO
        OO
    OOOOOOOOOO
    OOOOOOOOOO
    """
    ws = await game_start_helper(aiohttp_client, [1]) # only box
    r = await ws.receive_json()
    
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()

    assert r['board'] == [0]*18 + [36864,36864]
    assert r['live'] == [1,0, 4,1, 16]
    
async def test_clear_rows_25(aiohttp_client):
    """Create the following board:
    I
    I
    IJJJJJJJJJ
    I  J  J  J
    """
    ws = await game_start_helper(aiohttp_client, [5,5,5,2]) # J J J I
    r = await ws.receive_json()
    
    await ws.send_str("ccw"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("ccw"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    # print(r['board'])
    assert r['board'] == [0]*17 + [268435456, 268435456, 269748741]
    assert r['live'] == [5, 0, 4, 2, 16]
    
async def test_clear_rows_25_nonadjacent(aiohttp_client):
    """Create the following board:
    IJJJJJJJJJ
    I  J  J  J
    IJJJJJJJJJ
    I  J  J  J
    """
    ws = await game_start_helper(aiohttp_client, [5,5,5,5,5,5,2,2]) # J J J J J J I I
    r = await ws.receive_json()
    
    await ws.send_str("ccw"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("ccw"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("ccw"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("ccw"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()

    assert r['board'] == [0]*18 + [269748741, 269748741]
    assert r['live'] == [2, 0, 4, 3, 16]
    

async def test_various_downs(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2], timeout=2) # I only
    r = await ws.receive_json()
    assert 'board' in r
    assert r['live'][3] == 3
    
    r = await ws.receive_json() # tick
    assert 'board' not in r
    assert r['live'][3] == 4

    for k in range(15):
        await ws.send_str("down"); r = await ws.receive_json()
    assert 'board' not in r
    assert r['live'][3] == 19
    
    r = await ws.receive_json() # tick
    assert 'board' in r
    assert r['live'][3] == 3

    for k in range(13): # last of these would overlap two Is
        await ws.send_str("down"); r = await ws.receive_json()
    assert 'board' in r
    assert r['live'][3] == 3

async def test_game_over_7(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [7]) # Z only
    r = await ws.receive_json()
    for k in range(9):
        await ws.send_str("drop")
        r = await ws.receive_json()
        assert ('event' in r) == (k == 8)

async def test_game_over_2(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2]) # I only
    r = await ws.receive_json()
    for k in range(5):
        await ws.send_str("drop")
        r = await ws.receive_json()
        assert ('event' in r) == (k == 4)


async def test_edges(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2], timeout=2) # I only
    r = await ws.receive_json()

    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r["live"][2:4] == [9,3]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r["live"][2:4] == [9,4] # no response so tick occurred
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r["live"][2:4] == [7,4]
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r["live"][2:4] == [7,4]
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    await ws.send_str("left"); r = await ws.receive_json()
    assert r["live"][2:4] == [0,4]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r["live"][2:4] == [0,5] # no response so tick occurred
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r["live"][2:4] == [1,5]
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r["live"][2:4] == [1,5]


async def test_overlap(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2], timeout=3) # I only
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()

    await ws.send_str("right"); r = await ws.receive_json()
    for k in range(10): await ws.send_str("down"); r = await ws.receive_json()
    assert r["live"][2:4] == [5,13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r["live"][2:4] == [5,14]
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r["live"][2:4] == [5,15]
    await ws.send_str("drop"); r = await ws.receive_json()

    await ws.send_str("left"); r = await ws.receive_json()
    for k in range(10): await ws.send_str("down"); r = await ws.receive_json()
    assert r["live"][2:4] == [3,13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r["live"][2:4] == [3,14]
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r["live"][2:4] == [3,15]


async def test_bottom_outline_1(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,1])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I
    
    assert r['live'] == [1,0, 4,1, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [1,0, 3,1, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [1,0, 2,1, 18]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [1,0, 5,1, 18]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("drop"); r = await ws.receive_json()

async def test_bottom_outline_2(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,2])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I
    
    assert r['live'] == [2,0, 4,3, 12]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [2,0, 3,3, 16]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [2,0, 5,3, 16]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [2,1, 6,3, 16]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [2,1, 5,3, 12]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [2,1, 4,3, 12]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [2,1, 3,3, 12]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [2,1, 2,3, 12]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [2,1, 1,3, 16]

async def test_bottom_outline_3(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,3])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I

    assert r['live'] == [3,0, 4,1, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,0, 3,1, 15]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,0, 2,1, 18]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [3,0, 5,1, 15]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [3,0, 6,1, 18]
    
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [3,1, 6,2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,1, 5,2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,1, 4,2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,1, 3,2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [3,2, 3,2, 13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [3,2, 4,2, 13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [3,2, 5,2, 13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [3,2, 6,2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [3,3, 6,2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,3, 5,2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,3, 4,2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,3, 3,2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [3,3, 2,2, 17]

async def test_bottom_outline_4(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,4])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I

    assert r['live'] == [4, 0, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 0, 3, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 0, 2, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [4, 0, 5, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [4, 0, 6, 2, 17]
    
    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [4, 1, 6, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 1, 5, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 1, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 1, 3, 2, 14]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [4, 2, 3, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [4, 2, 4, 2, 13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [4, 2, 5, 2, 15]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [4, 2, 6, 2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [4, 3, 6, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 3, 5, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 3, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 3, 3, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [4, 3, 2, 2, 17]

async def test_bottom_outline_5(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,5])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I
    
    assert r['live'] == [5, 0, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 0, 3, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 0, 5, 2, 13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 0, 6, 2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [5, 1, 6, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 1, 5, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 1, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 1, 3, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 1, 2, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 1, 1, 2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [5, 2, 1, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 2, 2, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 2, 3, 2, 15]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 2, 4, 2, 13]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 2, 5, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [5, 2, 6, 2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [5, 3, 6, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 3, 5, 2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 3, 4, 2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 3, 3, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [5, 3, 2, 2, 17]

async def test_bottom_outline_6(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,6])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I
    
    assert r['live'] == [6, 0, 4, 2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [6, 0, 3, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [6, 0, 2, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [6, 0, 5, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [6, 0, 6, 2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [6, 1, 6, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [6, 1, 5, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [6, 1, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [6, 1, 3, 2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [6, 1, 2, 2, 17]

async def test_bottom_outline_7(aiohttp_client):
    ws = await game_start_helper(aiohttp_client, [2,7])
    r = await ws.receive_json()

    await ws.send_str("drop"); r = await ws.receive_json() # place I
    
    assert r['live'] == [7, 0, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [7, 0, 3, 2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [7, 0, 2, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [7, 0, 5, 2, 17]
    await ws.send_str("right"); r = await ws.receive_json()
    assert r['live'] == [7, 0, 6, 2, 17]

    await ws.send_str("cw"); r = await ws.receive_json()
    assert r['live'] == [7, 1, 6, 2, 17]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [7, 1, 5, 2, 14]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [7, 1, 4, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [7, 1, 3, 2, 13]
    await ws.send_str("left"); r = await ws.receive_json()
    assert r['live'] == [7, 1, 2, 2, 17]

