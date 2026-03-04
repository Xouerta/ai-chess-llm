import pygame
import asyncio
import yaml
import random
import numpy as np
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

# 初始化pygame
pygame.init()
pygame.display.set_caption("五子棋 vs 本地AI")
clock = pygame.time.Clock()

# 棋盘设置
BOARD_SIZE = 15  # 15x15 标准五子棋
CELL_SIZE = 40   # 每个格子大小
BOARD_MARGIN = 40  # 边距
BOARD_PX_SIZE = BOARD_SIZE * CELL_SIZE  # 棋盘像素大小
WINDOW_WIDTH = BOARD_PX_SIZE + BOARD_MARGIN * 2 + 200  # 加200给信息面板
WINDOW_HEIGHT = BOARD_PX_SIZE + BOARD_MARGIN * 2

# 颜色定义
class Colors:
    BACKGROUND = (210, 180, 140)  # 木质背景色
    BOARD_LINE = (100, 70, 40)     # 棋盘线
    BLACK_STONE = (30, 30, 30)      # 黑子
    WHITE_STONE = (240, 240, 240)   # 白子
    BLACK_STONE_OUTER = (10, 10, 10)  # 黑子外圈
    WHITE_STONE_OUTER = (200, 200, 200)  # 白子外圈
    LAST_MOVE = (255, 0, 0)          # 最后一步标记
    PANEL_BG = (240, 220, 180)       # 信息面板背景
    TEXT_BLACK = (50, 30, 20)         # 黑色文字
    TEXT_WHITE = (100, 70, 40)        # 白色文字
    BUTTON = (150, 120, 80)           # 按钮颜色
    BUTTON_HOVER = (170, 140, 100)    # 按钮悬停颜色

# 字体
try:
    FONT = pygame.font.Font(None, 36)
    SMALL_FONT = pygame.font.Font(None, 24)
    LARGE_FONT = pygame.font.Font(None, 48)
except:
    FONT = pygame.font.Font(None, 36)
    SMALL_FONT = pygame.font.Font(None, 24)
    LARGE_FONT = pygame.font.Font(None, 48)

class GomokuGame:
    def __init__(self, model_client):
        self.model_client = model_client
        self.board = np.zeros((BOARD_SIZE, BOARD_SIZE), dtype=int)  # 0空 1黑子(玩家) 2白子(AI)
        self.current_player = 1  # 1玩家(黑先) 2AI(白)
        self.game_over = False
        self.winner = None
        self.last_move = None
        self.ai_thinking = False
        self.move_history = []
        
        # 创建窗口
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        
        # 按钮区域
        self.reset_button = pygame.Rect(WINDOW_WIDTH - 180, 50, 150, 40)
        self.pass_button = pygame.Rect(WINDOW_WIDTH - 180, 100, 150, 40)
        
    def board_to_text(self):
        """将棋盘转换为文字描述（用于AI提示）"""
        # 只把最近几步有棋子的位置告诉AI
        if not self.move_history:
            return "棋盘是空的"
        
        # 取最近10步
        recent_moves = self.move_history[-10:]
        moves_desc = []
        for move in recent_moves:
            x, y, player = move
            player_name = "黑棋" if player == 1 else "白棋"
            # 转换坐标 (0-14) 到 (a-o)
            col = chr(ord('a') + x)
            row = str(y + 1)
            moves_desc.append(f"{player_name}落子于{col}{row}")
        
        return "，".join(moves_desc)
    
    async def get_ai_move(self):
        """调用Ollama获取AI走法"""
        try:
            agent = AssistantAgent(
                name="gomoku_ai",
                model_client=self.model_client,
                system_message="""你是一个五子棋AI。请根据当前棋盘局势，选择最佳落子位置。
只输出坐标，格式如 a7 或 h8。不要输出其他任何文字。""",
            )
            
            # 构造提示词
            board_desc = self.board_to_text()
            prompt = f"""当前是五子棋对局，你执白棋。
{board_desc}
请选择一个空白位置落子。输出格式：字母+数字，例如 j8。
只输出坐标，不要输出任何其他内容。"""
            
            response = await agent.run(task=prompt)
            last_message = response.messages[-1].content.strip()
            print(f"AI原始回复: {last_message}")
            
            # 解析坐标
            import re
            # 匹配 a1 到 o15 格式
            match = re.search(r'([a-oA-O])(\d{1,2})', last_message)
            if match:
                col_str = match.group(1).lower()
                row_str = match.group(2)
                
                # 转换坐标
                col = ord(col_str) - ord('a')
                row = int(row_str) - 1
                
                # 检查是否在棋盘内且为空
                if 0 <= col < BOARD_SIZE and 0 <= row < BOARD_SIZE:
                    if self.board[row][col] == 0:
                        return (row, col)
            
            # 如果AI回复无效，找所有空白位置
            print("AI没有返回有效坐标，使用随机走法")
            return self.get_random_move()
            
        except Exception as e:
            print(f"get_ai_move出错: {e}")
            return self.get_random_move()
    
    def get_random_move(self):
        """获取随机空白位置"""
        empty_cells = [(r, c) for r in range(BOARD_SIZE) for c in range(BOARD_SIZE) 
                      if self.board[r][c] == 0]
        if empty_cells:
            return random.choice(empty_cells)
        return None
    
    def check_win(self, row, col, player):
        """检查是否获胜"""
        if player == 0:
            return False
            
        directions = [(1,0), (0,1), (1,1), (1,-1)]  # 四个方向
        
        for dx, dy in directions:
            count = 1
            # 正方向
            for i in range(1, 5):
                nr, nc = row + dx*i, col + dy*i
                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            # 反方向
            for i in range(1, 5):
                nr, nc = row - dx*i, col - dy*i
                if 0 <= nr < BOARD_SIZE and 0 <= nc < BOARD_SIZE and self.board[nr][nc] == player:
                    count += 1
                else:
                    break
            
            if count >= 5:
                return True
        return False
    
    def make_move(self, row, col, player):
        """执行落子"""
        if self.board[row][col] != 0:
            return False
            
        self.board[row][col] = player
        self.last_move = (row, col)
        self.move_history.append((row, col, player))
        
        # 检查胜利
        if self.check_win(row, col, player):
            self.game_over = True
            self.winner = player
        elif len(self.move_history) == BOARD_SIZE * BOARD_SIZE:
            self.game_over = True
            self.winner = 0  # 平局
            
        return True
    
    def handle_click(self, pos):
        """处理鼠标点击"""
        if self.game_over or self.ai_thinking or self.current_player != 1:
            return
        
        x, y = pos
        
        # 检查按钮点击
        if self.reset_button.collidepoint(x, y):
            self.reset_game()
            return
        if self.pass_button.collidepoint(x, y):
            # 玩家弃权，轮到AI
            self.current_player = 2
            asyncio.create_task(self.ai_move())
            return
        
        # 检查棋盘点击
        board_x = x - BOARD_MARGIN
        board_y = y - BOARD_MARGIN
        
        if 0 <= board_x <= BOARD_PX_SIZE and 0 <= board_y <= BOARD_PX_SIZE:
            col = int(board_x // CELL_SIZE)
            row = int(board_y // CELL_SIZE)
            
            if 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE:
                if self.board[row][col] == 0:
                    if self.make_move(row, col, 1):
                        self.current_player = 2
                        if not self.game_over:
                            asyncio.create_task(self.ai_move())
    
    async def ai_move(self):
        """AI走棋"""
        self.ai_thinking = True
        
        try:
            move = await self.get_ai_move()
            if move:
                row, col = move
                if self.make_move(row, col, 2):
                    self.current_player = 1
                    print(f"AI落子: {chr(ord('a')+col)}{row+1}")
            else:
                # 没有空位了
                self.game_over = True
                self.winner = 0
        except Exception as e:
            print(f"AI走棋出错: {e}")
        
        self.ai_thinking = False
    
    def reset_game(self):
        """重置游戏"""
        self.board = np.zeros((BOARD_SIZE, BOARD_SIZE), dtype=int)
        self.current_player = 1
        self.game_over = False
        self.winner = None
        self.last_move = None
        self.move_history = []
    
    def draw_board(self):
        """绘制棋盘"""
        self.screen.fill(Colors.BACKGROUND)
        
        # 绘制棋盘线
        for i in range(BOARD_SIZE):
            start_x = BOARD_MARGIN
            start_y = BOARD_MARGIN + i * CELL_SIZE
            end_x = BOARD_MARGIN + BOARD_PX_SIZE
            end_y = BOARD_MARGIN + i * CELL_SIZE
            pygame.draw.line(self.screen, Colors.BOARD_LINE, (start_x, start_y), (end_x, end_y), 2)
            
            start_x = BOARD_MARGIN + i * CELL_SIZE
            start_y = BOARD_MARGIN
            end_x = BOARD_MARGIN + i * CELL_SIZE
            end_y = BOARD_MARGIN + BOARD_PX_SIZE
            pygame.draw.line(self.screen, Colors.BOARD_LINE, (start_x, start_y), (end_x, end_y), 2)
        
        # 画星位（天元、小目）
        star_points = [(7,7), (3,3), (11,3), (3,11), (11,11)]
        for x, y in star_points:
            cx = BOARD_MARGIN + x * CELL_SIZE
            cy = BOARD_MARGIN + y * CELL_SIZE
            pygame.draw.circle(self.screen, Colors.BOARD_LINE, (cx, cy), 5)
        
        # 绘制棋子
        for row in range(BOARD_SIZE):
            for col in range(BOARD_SIZE):
                if self.board[row][col] != 0:
                    x = BOARD_MARGIN + col * CELL_SIZE
                    y = BOARD_MARGIN + row * CELL_SIZE
                    
                    if self.board[row][col] == 1:  # 黑子
                        pygame.draw.circle(self.screen, Colors.BLACK_STONE_OUTER, (x, y), 17)
                        pygame.draw.circle(self.screen, Colors.BLACK_STONE, (x, y), 15)
                    else:  # 白子
                        pygame.draw.circle(self.screen, Colors.WHITE_STONE_OUTER, (x, y), 17)
                        pygame.draw.circle(self.screen, Colors.WHITE_STONE, (x, y), 15)
                    
                    # 标记最后一步
                    if self.last_move == (row, col):
                        pygame.draw.circle(self.screen, Colors.LAST_MOVE, (x, y), 5)
        
        # 绘制坐标
        for i in range(BOARD_SIZE):
            # 字母坐标 (a-o)
            label = SMALL_FONT.render(chr(ord('a') + i), True, Colors.TEXT_BLACK)
            self.screen.blit(label, (BOARD_MARGIN + i * CELL_SIZE - 8, BOARD_MARGIN - 25))
            
            # 数字坐标 (1-15)
            label = SMALL_FONT.render(str(i + 1), True, Colors.TEXT_BLACK)
            self.screen.blit(label, (BOARD_MARGIN - 25, BOARD_MARGIN + i * CELL_SIZE - 10))
        
        # 绘制信息面板
        panel_x = WINDOW_WIDTH - 190
        panel_y = 10
        panel_width = 180
        panel_height = WINDOW_HEIGHT - 20
        
        pygame.draw.rect(self.screen, Colors.PANEL_BG, (panel_x, panel_y, panel_width, panel_height))
        pygame.draw.rect(self.screen, Colors.BOARD_LINE, (panel_x, panel_y, panel_width, panel_height), 2)
        
        # 标题
        title = FONT.render("对局信息", True, Colors.TEXT_BLACK)
        self.screen.blit(title, (panel_x + 30, panel_y + 10))
        
        # 当前回合
        if not self.game_over:
            turn_text = "你的回合" if self.current_player == 1 else "AI思考中..."
            turn_color = Colors.BLACK_STONE if self.current_player == 1 else Colors.WHITE_STONE_OUTER
            turn = SMALL_FONT.render(turn_text, True, turn_color)
            self.screen.blit(turn, (panel_x + 20, panel_y + 50))
            
            if self.ai_thinking:
                dots = "." * ((pygame.time.get_ticks() // 500) % 4)
                thinking = SMALL_FONT.render(f"AI思考中{dots}", True, Colors.TEXT_WHITE)
                self.screen.blit(thinking, (panel_x + 20, panel_y + 80))
        else:
            # 游戏结束
            if self.winner == 1:
                result = "你赢了！"
            elif self.winner == 2:
                result = "AI赢了..."
            else:
                result = "平局"
            over_text = FONT.render(result, True, Colors.LAST_MOVE)
            self.screen.blit(over_text, (panel_x + 30, panel_y + 50))
        
        # 按钮
        mouse_pos = pygame.mouse.get_pos()
        
        # 重置按钮
        reset_color = Colors.BUTTON_HOVER if self.reset_button.collidepoint(mouse_pos) else Colors.BUTTON
        pygame.draw.rect(self.screen, reset_color, self.reset_button)
        pygame.draw.rect(self.screen, Colors.BOARD_LINE, self.reset_button, 2)
        reset_text = SMALL_FONT.render("重新开始", True, Colors.TEXT_WHITE)
        self.screen.blit(reset_text, (self.reset_button.x + 20, self.reset_button.y + 10))
        
        # 弃权按钮
        pass_color = Colors.BUTTON_HOVER if self.pass_button.collidepoint(mouse_pos) else Colors.BUTTON
        pygame.draw.rect(self.screen, pass_color, self.pass_button)
        pygame.draw.rect(self.screen, Colors.BOARD_LINE, self.pass_button, 2)
        pass_text = SMALL_FONT.render("弃权", True, Colors.TEXT_WHITE)
        self.screen.blit(pass_text, (self.pass_button.x + 50, self.pass_button.y + 10))
        
        # 走法历史
        history_title = SMALL_FONT.render("最近走法:", True, Colors.TEXT_BLACK)
        self.screen.blit(history_title, (panel_x + 20, panel_y + 200))
        
        for i, move in enumerate(self.move_history[-8:]):
            row, col, player = move
            player_name = "黑" if player == 1 else "白"
            move_text = f"{i+1}. {player_name}{chr(ord('a')+col)}{row+1}"
            text = SMALL_FONT.render(move_text, True, Colors.TEXT_BLACK)
            self.screen.blit(text, (panel_x + 30, panel_y + 230 + i * 25))
        
        pygame.display.flip()

async def main():
    # 加载模型配置
    try:
        with open("model_config.yaml", "r") as f:
            model_config = yaml.safe_load(f)
        print("配置加载成功")
    except FileNotFoundError:
        print("找不到 model_config.yaml，使用默认配置")
        model_config = {
            "provider": "autogen_ext.models.openai.OpenAIChatCompletionClient",
            "config": {
                "model": "deepseek-r1:8b",
                "base_url": "http://localhost:11434/v1",
                "api_key": "ollama",
                "model_info": {
                    "vision": False,
                    "function_calling": True,
                    "json_output": False,
                    "family": "unknown"
                }
            }
        }
    
    try:
        model_client = OpenAIChatCompletionClient(**model_config["config"])
        print("模型客户端创建成功")
    except Exception as e:
        print(f"模型客户端创建失败: {e}")
        return
    
    # 创建游戏实例
    game = GomokuGame(model_client)
    
    # 游戏主循环
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            
            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:  # 左键点击
                    game.handle_click(event.pos)
            
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_r:
                    game.reset_game()
        
        game.draw_board()
        clock.tick(60)
        
        # 让异步任务有机会运行
        await asyncio.sleep(0)
    
    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())