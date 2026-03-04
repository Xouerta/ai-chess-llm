import chess
import pygame
import asyncio
import yaml
import random  # 确保在文件顶部导入
import os
import re
from autogen_agentchat.agents import AssistantAgent
from autogen_ext.models.openai import OpenAIChatCompletionClient

# 初始化pygame
pygame.init()
pygame.display.set_caption("国际象棋 vs 本地AI")
clock = pygame.time.Clock()

# 窗口设置
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 680
BOARD_SIZE = 560
SQUARE_SIZE = BOARD_SIZE // 8
INFO_PANEL_WIDTH = WINDOW_WIDTH - BOARD_SIZE - 20

screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))

# 颜色定义
class Colors:
    LIGHT_SQUARE = (240, 217, 181)
    DARK_SQUARE = (181, 136, 99)
    HIGHLIGHT = (186, 202, 68, 100)
    POSSIBLE_MOVE = (130, 151, 105, 80)
    LAST_MOVE = (170, 162, 58, 60)
    BACKGROUND = (50, 50, 50)
    PANEL_BG = (60, 60, 60)
    TEXT_WHITE = (255, 255, 255)
    TEXT_BLACK = (200, 200, 200)
    
    @staticmethod
    def with_alpha(color, alpha):
        return (*color[:3], alpha)

# 加载字体
try:
    FONT = pygame.font.Font(None, 36)
    SMALL_FONT = pygame.font.Font(None, 24)
    PIECE_FONT = pygame.font.SysFont('segoeuisymbol', 56)
except:
    FONT = pygame.font.Font(None, 36)
    SMALL_FONT = pygame.font.Font(None, 24)
    PIECE_FONT = pygame.font.Font(None, 56)

class ChessGame:
    def __init__(self, model_client):
        self.board = chess.Board()
        self.model_client = model_client
        self.selected_square = None
        self.possible_moves = []
        self.last_move = None
        self.game_over = False
        self.winner = None
        self.ai_thinking = False
        self.move_history = []
        self.flipped = False  # 是否翻转棋盘（黑方视角）
        
    def get_piece_symbol(self, piece):
        """获取棋子Unicode符号"""
        symbols = {
            (chess.PAWN, True): "♙", (chess.ROOK, True): "♖",
            (chess.KNIGHT, True): "♘", (chess.BISHOP, True): "♗",
            (chess.QUEEN, True): "♕", (chess.KING, True): "♔",
            (chess.PAWN, False): "♟", (chess.ROOK, False): "♜",
            (chess.KNIGHT, False): "♞", (chess.BISHOP, False): "♝",
            (chess.QUEEN, False): "♛", (chess.KING, False): "♚",
        }
        return symbols.get((piece.piece_type, piece.color), "?")
    
    def square_to_coords(self, square):
        """将格子编号转换为屏幕坐标"""
        col = chess.square_file(square)
        row = chess.square_rank(square)
        
        if self.flipped:
            col = 7 - col
            row = 7 - row
        
        x = col * SQUARE_SIZE
        y = (7 - row) * SQUARE_SIZE
        return x, y
    
    def coords_to_square(self, x, y):
        """将屏幕坐标转换为格子编号"""
        if x < 0 or x >= BOARD_SIZE or y < 0 or y >= BOARD_SIZE:
            return None
        
        col = x // SQUARE_SIZE
        row = 7 - (y // SQUARE_SIZE)
        
        if self.flipped:
            col = 7 - col
            row = 7 - row
        
        if 0 <= col < 8 and 0 <= row < 8:
            return chess.square(col, row)
        return None
    
    def draw_board(self, surface):
        """绘制棋盘"""
        # 绘制格子
        for row in range(8):
            for col in range(8):
                x = col * SQUARE_SIZE
                y = row * SQUARE_SIZE
                
                # 格子颜色
                is_light = (row + col) % 2 == 0
                color = Colors.LIGHT_SQUARE if is_light else Colors.DARK_SQUARE
                
                # 绘制格子
                pygame.draw.rect(surface, color, (x, y, SQUARE_SIZE, SQUARE_SIZE))
                
                # 获取当前格子的实际棋盘位置
                board_col = col if not self.flipped else 7 - col
                board_row = 7 - row if not self.flipped else row
                square = chess.square(board_col, board_row)
                
                # 高亮上一步走的格子
                if self.last_move:
                    if square in [self.last_move.from_square, self.last_move.to_square]:
                        highlight = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
                        highlight.set_alpha(60)
                        highlight.fill(Colors.LAST_MOVE[:3])
                        surface.blit(highlight, (x, y))
                
                # 高亮选中的格子
                if square == self.selected_square:
                    highlight = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
                    highlight.set_alpha(80)
                    highlight.fill(Colors.HIGHLIGHT[:3])
                    surface.blit(highlight, (x, y))
                
                # 高亮可行走法
                if square in self.possible_moves:
                    highlight = pygame.Surface((SQUARE_SIZE, SQUARE_SIZE))
                    highlight.set_alpha(60)
                    highlight.fill(Colors.POSSIBLE_MOVE[:3])
                    surface.blit(highlight, (x, y))
                    
                    # 如果是吃子，加个红圈
                    if self.board.piece_at(square):
                        pygame.draw.circle(surface, (255, 100, 100), 
                                         (x + SQUARE_SIZE//2, y + SQUARE_SIZE//2), 
                                         SQUARE_SIZE//3, 3)
                
                # 绘制棋子
                piece = self.board.piece_at(square)
                if piece:
                    text = PIECE_FONT.render(self.get_piece_symbol(piece), True, (0, 0, 0))
                    text_rect = text.get_rect(center=(x + SQUARE_SIZE//2, y + SQUARE_SIZE//2))
                    surface.blit(text, text_rect)
        
        # 绘制坐标标签
        for i in range(8):
            # 文件(a-h)
            file_label = chr(ord('a') + i)
            if self.flipped:
                file_label = chr(ord('h') - i)
            text = SMALL_FONT.render(file_label, True, Colors.TEXT_WHITE)
            surface.blit(text, (i * SQUARE_SIZE + 5, BOARD_SIZE - 25))
            
            # 行号(1-8)
            rank_label = str(i + 1)
            if self.flipped:
                rank_label = str(8 - i)
            text = SMALL_FONT.render(rank_label, True, Colors.TEXT_WHITE)
            surface.blit(text, (5, i * SQUARE_SIZE + 5))
    
    def draw_info_panel(self, surface):
        """绘制信息面板"""
        panel_x = BOARD_SIZE + 10
        panel_width = INFO_PANEL_WIDTH
        
        # 背景
        pygame.draw.rect(surface, Colors.PANEL_BG, 
                        (panel_x, 0, panel_width, WINDOW_HEIGHT))
        
        y_offset = 20
        
        # 标题
        title = FONT.render("info", True, Colors.TEXT_WHITE)
        surface.blit(title, (panel_x + 20, y_offset))
        y_offset += 50
        
        # 当前回合
        turn_text = "Your turn!" if self.board.turn == chess.WHITE else "AIthinking..."
        turn_color = Colors.TEXT_WHITE if self.board.turn == chess.WHITE else (255, 200, 100)
        turn = FONT.render(turn_text, True, turn_color)
        surface.blit(turn, (panel_x + 20, y_offset))
        y_offset += 40
        
        # AI思考动画
        if self.ai_thinking:
            dots = "." * ((pygame.time.get_ticks() // 500) % 4)
            thinking = SMALL_FONT.render(f"AI thinking{dots}", True, (255, 255, 0))
            surface.blit(thinking, (panel_x + 20, y_offset))
            y_offset += 40
        
        # 分隔线
        pygame.draw.line(surface, (100, 100, 100), 
                        (panel_x + 10, y_offset), 
                        (panel_x + panel_width - 10, y_offset), 2)
        y_offset += 20
        
        # 走法历史
        history_title = SMALL_FONT.render("recent steps:", True, Colors.TEXT_WHITE)
        surface.blit(history_title, (panel_x + 20, y_offset))
        y_offset += 30
        
        for i, move in enumerate(self.move_history[-10:]):
            move_text = f"{i+1}. {move}"
            text = SMALL_FONT.render(move_text, True, Colors.TEXT_BLACK)
            surface.blit(text, (panel_x + 30, y_offset))
            y_offset += 25
        
        y_offset = WINDOW_HEIGHT - 120
        
        # 游戏结束信息
        if self.game_over:
            if self.winner == "white":
                result = "you win！"
            elif self.winner == "black":
                result = "AIwin..."
            else:
                result = "draw"
            
            over_text = FONT.render(result, True, (255, 200, 0))
            surface.blit(over_text, (panel_x + 20, y_offset))
            y_offset += 50
        
        # 控制按钮
        flip_btn = SMALL_FONT.render("F - reverse the chess board", True, Colors.TEXT_WHITE)
        surface.blit(flip_btn, (panel_x + 20, y_offset))
        y_offset += 25
        
        reset_btn = SMALL_FONT.render("R - restart", True, Colors.TEXT_WHITE)
        surface.blit(reset_btn, (panel_x + 20, y_offset))
        y_offset += 25
        
        quit_btn = SMALL_FONT.render("ESC - exit", True, Colors.TEXT_WHITE)
        surface.blit(quit_btn, (panel_x + 20, y_offset))
    
    def handle_click(self, pos):
        """处理鼠标点击"""
        if self.game_over or self.ai_thinking:
            return
        
        x, y = pos
        square = self.coords_to_square(x, y)
        
        if square is None:
            return
        
        # 如果点击在棋盘外
        if x >= BOARD_SIZE:
            return
        
        if self.selected_square is None:
            # 选择棋子
            piece = self.board.piece_at(square)
            if piece and piece.color == self.board.turn:
                self.selected_square = square
                # 计算可行走法
                self.possible_moves = [move.to_square for move in self.board.legal_moves 
                                      if move.from_square == square]
        else:
            # 移动棋子
            move = chess.Move(self.selected_square, square)
            
            # 检查升变
            piece = self.board.piece_at(self.selected_square)
            if piece and piece.piece_type == chess.PAWN:
                if chess.square_rank(square) in [0, 7]:
                    # 简单起见，默认升后
                    move = chess.Move(self.selected_square, square, promotion=chess.QUEEN)
            
            if move in self.board.legal_moves:
                self.make_move(move)
            
            self.selected_square = None
            self.possible_moves = []
    
    def make_move(self, move):
        """执行走法"""
        self.board.push(move)
        self.last_move = move
        self.move_history.append(move.uci())
        
        # 检查游戏结束
        self.check_game_over()
        
        # 如果是玩家走的，轮到AI
        if not self.game_over and self.board.turn == chess.BLACK:
            # 启动AI走棋
            asyncio.create_task(self.ai_move())
    
    async def get_ai_move(self):
        """调用Ollama获取AI走法"""
        try:
            agent = AssistantAgent(
                name="chess_ai",
                model_client=self.model_client,
                system_message="你是一个国际象棋AI。你必须只输出一个合法的UCI格式走法，不要输出任何其他内容。",
            )
            
            legal_moves_list = list(self.board.legal_moves)
            legal_moves_str = ", ".join([move.uci() for move in legal_moves_list])
            
            prompt = f"""棋盘(FEN): {self.board.fen()}
你执黑方。
合法的走法有: {legal_moves_str}
请从上述合法走法中选择一个，只输出你选择的走法本身（例如 e7e5），不要输出任何其他文字、不要加标签、不要解释。"""
            
            response = await agent.run(task=prompt)
            last_message = response.messages[-1].content.strip()
            print(f"AI原始回复: {last_message}")
            
            # 清理回复，提取第一个合法的UCI走法
            words = last_message.split()
            for word in words:
                word = word.strip('.,!?<>()[]{}"\'')
                # 检查是否是合法的UCI格式（4或5个字符，全是字母和数字）
                if len(word) in [4, 5] and all(c.isalnum() for c in word):
                    try:
                        # 验证是否是合法的走法
                        move = chess.Move.from_uci(word)
                        if move in self.board.legal_moves:
                            return word
                    except:
                        continue
            
            # 如果没找到合法走法，返回随机走法
            print("AI没有返回合法走法，使用随机走法")
            return random.choice(legal_moves_list).uci()
            
        except Exception as e:
            print(f"get_ai_move出错: {e}")
            # 返回一个随机走法作为后备
            legal_moves_list = list(self.board.legal_moves)
            if legal_moves_list:
                return random.choice(legal_moves_list).uci()
            return None
    
    async def ai_move(self):
        """AI走棋"""
        self.ai_thinking = True
        
        try:
            # 获取AI走法
            ai_move_uci = await self.get_ai_move()
            
            if ai_move_uci:
                ai_move = chess.Move.from_uci(ai_move_uci)
                if ai_move in self.board.legal_moves:
                    self.board.push(ai_move)
                    self.last_move = ai_move
                    self.move_history.append(ai_move.uci())
                    print(f"AI走法: {ai_move_uci}")
                else:
                    # 如果AI输出非法走法，随机选择
                    legal_moves = list(self.board.legal_moves)
                    if legal_moves:
                        ai_move = random.choice(legal_moves)
                        self.board.push(ai_move)
                        self.last_move = ai_move
                        self.move_history.append(ai_move.uci())
                        print(f"AI走法(随机): {ai_move.uci()}")
            else:
                # 没有获取到走法，随机选择
                legal_moves = list(self.board.legal_moves)
                if legal_moves:
                    ai_move = random.choice(legal_moves)
                    self.board.push(ai_move)
                    self.last_move = ai_move
                    self.move_history.append(ai_move.uci())
                    print(f"AI走法(随机): {ai_move.uci()}")
                    
        except Exception as e:
            print(f"AI走棋出错: {e}")
            # 出错时随机走一步
            try:
                legal_moves = list(self.board.legal_moves)
                if legal_moves:
                    ai_move = random.choice(legal_moves)
                    self.board.push(ai_move)
                    self.last_move = ai_move
                    self.move_history.append(ai_move.uci())
                    print(f"AI走法(随机-异常): {ai_move.uci()}")
            except Exception as e2:
                print(f"随机走棋也出错: {e2}")
        
        self.ai_thinking = False
        self.check_game_over()
    
    def check_game_over(self):
        """检查游戏是否结束"""
        if self.board.is_game_over():
            self.game_over = True
            if self.board.is_checkmate():
                self.winner = "white" if self.board.turn == chess.BLACK else "black"
            else:
                self.winner = "draw"
    
    def reset(self):
        """重置游戏"""
        self.board = chess.Board()
        self.selected_square = None
        self.possible_moves = []
        self.last_move = None
        self.game_over = False
        self.winner = None
        self.ai_thinking = False
        self.move_history = []
    
    def draw(self, surface):
        """绘制整个界面"""
        surface.fill(Colors.BACKGROUND)
        
        # 绘制棋盘
        board_surface = pygame.Surface((BOARD_SIZE, BOARD_SIZE))
        self.draw_board(board_surface)
        surface.blit(board_surface, (0, 0))
        
        # 绘制信息面板
        self.draw_info_panel(surface)

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
    game = ChessGame(model_client)
    
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
                    game.reset()
                elif event.key == pygame.K_f:
                    game.flipped = not game.flipped
        
        game.draw(screen)
        pygame.display.flip()
        clock.tick(60)
        
        # 让异步任务有机会运行
        await asyncio.sleep(0)
    
    pygame.quit()

if __name__ == "__main__":
    asyncio.run(main())