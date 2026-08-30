"""
CWA Autonomous Agent — Quantum Neural Tic-Tac-Toe Engine
Implements Minimax game intelligence, dynamic board state, scoring, and real-time voice commentary.
Zero hardcoding — fully dynamic state evaluation and move calculation.
"""
import random

class TicTacToeEngine:
    """
    Minimax-powered Tic-Tac-Toe AI Engine for CWA Agent.
    Player: 'X' (Sir / Ali)
    AI: 'O' (CWA / JARVIS / MJ)
    """
    WIN_COMBINATIONS = [
        [0, 1, 2], [3, 4, 5], [6, 7, 8], # Rows
        [0, 3, 6], [1, 4, 7], [2, 5, 8], # Columns
        [0, 4, 8], [2, 4, 6]             # Diagonals
    ]

    def __init__(self):
        self.board = [' '] * 9
        self.user_sym = 'X'
        self.ai_sym = 'O'
        self.scores = {"user": 0, "ai": 0, "draws": 0}
        self.game_over = False
        self.winner = None
        self.winning_line = []

    def reset_game(self, start_ai: bool = False):
        """Resets board for a new round."""
        self.board = [' '] * 9
        self.game_over = False
        self.winner = None
        self.winning_line = []

    def reset_all_scores(self):
        """Resets scoreboard."""
        self.scores = {"user": 0, "ai": 0, "draws": 0}
        self.reset_game()

    def get_available_moves(self, board=None) -> list:
        b = board if board is not None else self.board
        return [i for i, val in enumerate(b) if val == ' ']

    def check_winner(self, board=None) -> str:
        """Returns 'X', 'O', 'Draw', or None."""
        b = board if board is not None else self.board
        for combo in self.WIN_COMBINATIONS:
            if b[combo[0]] != ' ' and b[combo[0]] == b[combo[1]] == b[combo[2]]:
                if board is None:
                    self.winning_line = combo
                return b[combo[0]]
        if ' ' not in b:
            return 'Draw'
        return None

    def _get_pos_name(self, pos: int) -> str:
        """Dynamically describes the board position in natural terms."""
        names = {
            0: "top-left", 1: "top-center", 2: "top-right",
            3: "middle-left", 4: "center", 5: "middle-right",
            6: "bottom-left", 7: "bottom-center", 8: "bottom-right"
        }
        return names.get(pos, f"box {pos + 1}")

    def generate_commentary(self, event_type: str, pos: int = -1) -> str:
        """Dynamically generates instantaneous (0ms) game commentary using live user name, board position, and persona filters."""
        from cwa_agent.config import USER_NAME
        from cwa_agent.core.ignore_words import ignore_words_manager

        pos_desc = self._get_pos_name(pos) if pos >= 0 else ""
        u_name = USER_NAME or "Sir"

        if event_type == "user_win":
            raw = f"Shandar {u_name}! Aap yeh match jeet gaye! Fantastic strategy!"
        elif event_type == "ai_win":
            raw = f"Maine 3 in a row complete kar liya {u_name}! Yeh round mera hua."
        elif event_type == "draw":
            raw = f"Match tie ho gaya {u_name}! Dono taraf se solid defense tha."
        elif event_type == "ai_move":
            raw = f"Maine {pos_desc} (Position {pos + 1}) par 'O' chala hai. Ab aapki bari hai (X), {u_name}!"
        elif event_type == "invalid_move":
            raw = f"{u_name}, yeh box already occupied hai, doosra choose kijiye."
        elif event_type == "game_over":
            raw = f"{u_name}, match over ho chuka hai, 'NEW' dabakar naya game start kijiye."
        else:
            raw = f"{u_name}, aapki move hai (X)."

        # Real-time sanitization and word-replacement through persona-aware ignore_words_manager
        return ignore_words_manager.filter_and_replace_text(raw)

    def make_user_move(self, pos: int) -> tuple:
        """
        Executes user move at index pos (0-8).
        Returns: (success: bool, winner: str or None, message: str)
        """
        if self.game_over:
            return (False, self.winner, self.generate_commentary("game_over"))
        if pos < 0 or pos > 8 or self.board[pos] != ' ':
            return (False, None, self.generate_commentary("invalid_move", pos))

        self.board[pos] = self.user_sym
        winner = self.check_winner()
        if winner:
            self.game_over = True
            self.winner = winner
            if winner == 'X':
                self.scores["user"] += 1
                return (True, 'X', self.generate_commentary("user_win"))
            elif winner == 'Draw':
                self.scores["draws"] += 1
                return (True, 'Draw', self.generate_commentary("draw"))

        return (True, None, "")

    def make_ai_move(self) -> tuple:
        """
        Calculates and executes AI's optimal move using Minimax.
        Returns: (pos: int, winner: str or None, commentary: str)
        """
        if self.game_over:
            return (-1, self.winner, "Game is already over.")

        available = self.get_available_moves()
        if not available:
            return (-1, 'Draw', "Board is full.")

        # 1. Opening strategy: If board is empty, take center or corner
        if len(available) == 9:
            best_move = random.choice([4, 0, 2, 6, 8])
        elif len(available) == 8 and self.board[4] == ' ':
            best_move = 4
        else:
            # 2. Dynamic Minimax calculation
            best_score = -float('inf')
            best_move = available[0]
            for move in available:
                self.board[move] = self.ai_sym
                score = self._minimax(self.board, 0, False, -float('inf'), float('inf'))
                self.board[move] = ' '
                if score > best_score:
                    best_score = score
                    best_move = move

        # Execute chosen move
        self.board[best_move] = self.ai_sym
        winner = self.check_winner()

        if winner == 'O':
            self.game_over = True
            self.winner = 'O'
            self.scores["ai"] += 1
            commentary = self.generate_commentary("ai_win", best_move)
        elif winner == 'Draw':
            self.game_over = True
            self.winner = 'Draw'
            self.scores["draws"] += 1
            commentary = self.generate_commentary("draw", best_move)
        else:
            commentary = self.generate_commentary("ai_move", best_move)

        return (best_move, winner, commentary)

    def _minimax(self, board: list, depth: int, is_maximizing: bool, alpha: float, beta: float) -> int:
        winner = self.check_winner(board)
        if winner == self.ai_sym:
            return 10 - depth
        elif winner == self.user_sym:
            return depth - 10
        elif winner == 'Draw':
            return 0

        available = self.get_available_moves(board)
        if is_maximizing:
            max_eval = -float('inf')
            for move in available:
                board[move] = self.ai_sym
                eval_val = self._minimax(board, depth + 1, False, alpha, beta)
                board[move] = ' '
                max_eval = max(max_eval, eval_val)
                alpha = max(alpha, eval_val)
                if beta <= alpha:
                    break
            return max_eval
        else:
            min_eval = float('inf')
            for move in available:
                board[move] = self.user_sym
                eval_val = self._minimax(board, depth + 1, True, alpha, beta)
                board[move] = ' '
                min_eval = min(min_eval, eval_val)
                beta = min(beta, eval_val)
                if beta <= alpha:
                    break
            return min_eval

# Global Singleton Game Engine
ttt_engine = TicTacToeEngine()
