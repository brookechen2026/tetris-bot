# 修改后的calculateScore函数，仅接受board作为参数
import math
from datetime import datetime


def calculateScore(self, board):
    t1 = datetime.now()  # 记录开始计算时间
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
    stdY = math.sqrt(sum([y ** 2 for y in roofY]) / len(roofY) - (sum(roofY) / len(roofY)) ** 2) if roofY else 0
    # 计算高度差标准差
    stdDY = math.sqrt(sum([d ** 2 for d in roofDy]) / len(roofDy) - (sum(roofDy) / len(roofDy)) ** 2) if roofDy else 0
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