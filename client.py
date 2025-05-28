import sys, pygame
from enum import Enum
import socket, select
from collections import deque
import math, random
import copy

START_POS = "rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1"

class Piece(Enum):
    NONE = 0

    PAWN_W = 1
    ROOK_W = 2
    KNIGHT_W = 3
    BISHOP_W = 4
    QUEEN_W = 5
    KING_W = 6

    PAWN_B = 9
    ROOK_B = 10
    KNIGHT_B = 11
    BISHOP_B = 12
    QUEEN_B = 13
    KING_B = 14

class CloseException(Exception):
    pass

class Game:

    def __init__(self, sock: socket.socket) -> None:
        self.sock = sock

        self.board_size = screen_size
        self.cell_size = (self.board_size[0] / 8, self.board_size[1] / 8)

        self.color_dark = (181, 136, 99)
        self.color_light = (240, 217, 181)
        self.color_pos = (100, 109, 64)
        self.color_check = (240, 20, 20, 180)

        self.board: list[list[Piece]] = []

        self.white = False
        self.spectator = False

        self.moved = False

        self.possible_moves = None

        self.en_passant_tgt = None

        self.my_turn = False

        self.checked_me = False
        self.checked_opp = False

        self.sync_board(START_POS)

        self.sprites: list[pygame.Surface | None] = [None for _ in range(15)]

        for file, piece in [("wP", Piece.PAWN_W), ("wR", Piece.ROOK_W), ("wN", Piece.KNIGHT_W), ("wB", Piece.BISHOP_W), ("wQ", Piece.QUEEN_W), ("wK", Piece.KING_W), ("bP", Piece.PAWN_B), ("bR", Piece.ROOK_B), ("bN", Piece.KNIGHT_B), ("bB", Piece.BISHOP_B), ("bQ", Piece.QUEEN_B), ("bK", Piece.KING_B)]:
            svg = pygame.image.load(f"resources/{file}.png")
            img = pygame.transform.scale(svg, self.cell_size).convert_alpha()
            self.sprites[piece.value] = img

        self.prom_select_w = pygame.Surface((2 * self.cell_size[0], 2 * self.cell_size[1]))
        self.prom_select_w.fill((255, 255, 255))
        self.prom_select_w.blit(self.sprites[Piece.QUEEN_W.value], (0, 0))
        self.prom_select_w.blit(self.sprites[Piece.KNIGHT_W.value], (self.cell_size[1], 0))
        self.prom_select_w.blit(self.sprites[Piece.ROOK_W.value], (0, self.cell_size[0]))
        self.prom_select_w.blit(self.sprites[Piece.BISHOP_W.value], (self.cell_size[1], self.cell_size[0]))
        pygame.draw.rect(self.prom_select_w, (0, 0, 0), (0, 0, self.cell_size[0] * 2, self.cell_size[1] * 2), 1)

        self.prom_select_b = pygame.Surface((2 * self.cell_size[0], 2 * self.cell_size[1]))
        self.prom_select_b.fill((255, 255, 255))
        self.prom_select_b.blit(self.sprites[Piece.QUEEN_B.value], (0, 0))
        self.prom_select_b.blit(self.sprites[Piece.KNIGHT_B.value], (self.cell_size[1], 0))
        self.prom_select_b.blit(self.sprites[Piece.ROOK_B.value], (0, self.cell_size[0]))
        self.prom_select_b.blit(self.sprites[Piece.BISHOP_B.value], (self.cell_size[1], self.cell_size[0]))
        pygame.draw.rect(self.prom_select_b, (0, 0, 0), (0, 0, self.cell_size[0] * 2, self.cell_size[1] * 2), 1)

        self.prom_menu_coords = None
        self.prom_move = None

        self.check_circle = pygame.Surface(self.cell_size, pygame.SRCALPHA)
        self.check_circle.fill((0, 0, 0, 0))
        pygame.draw.circle(self.check_circle, self.color_check, (self.cell_size[0] / 2, self.cell_size[1] / 2), self.cell_size[0] / 2)

    def __del__(self):
        self.sock.close()

    def sync_board(self, FEN: str) -> None:
        self.board = []
        rank: list[Piece] = []
        for i, p in enumerate(FEN):
            match p:
                case 'P':
                    rank.append(Piece.PAWN_W)
                case 'R':
                    rank.append(Piece.ROOK_W)
                case 'N':
                    rank.append(Piece.KNIGHT_W)
                case 'B':
                    rank.append(Piece.BISHOP_W)
                case 'Q':
                    rank.append(Piece.QUEEN_W)
                case 'K':
                    rank.append(Piece.KING_W)

                case 'p':
                    rank.append(Piece.PAWN_B)
                case 'r':
                    rank.append(Piece.ROOK_B)
                case 'n':
                    rank.append(Piece.KNIGHT_B)
                case 'b':
                    rank.append(Piece.BISHOP_B)
                case 'q':
                    rank.append(Piece.QUEEN_B)
                case 'k':
                    rank.append(Piece.KING_B)

                case '/':
                    if len(rank) != 8:
                        raise Exception("Incorrect FEN string", FEN)

                    self.board.append(rank.copy())
                    rank.clear()

                case ' ':
                    if len(rank) != 8:
                        raise Exception("Incorrect FEN string", FEN)

                    self.board.append(rank.copy())
                    break

                case _:
                    rank.extend([Piece.NONE for _ in range(int(p))])

    def start(self) -> None:
        init_msg = self.read_socket()

        if init_msg == "wbs":
            resp = random.choice("wb")
            self.white = (resp == "w")
            self.write_socket(resp)

        elif init_msg == "ws":
            self.white = True
            self.write_socket("w")

        elif init_msg == "bs":
            self.white = False
            self.write_socket("b")

        else:
            self.spectator = True
            self.white = True
            self.write_socket("s")

        pos = self.read_socket()

        init_msg = self.read_socket()

        if init_msg == "initfail":
            raise Exception("Failed to initialize connection")
        
        if init_msg != "initok":
            raise Exception("Unknown initialization message")

        self.sync_board(pos)

        self.in_progress = True

        to_send = deque([])

        dragging = None

        if self.white and not self.spectator:
            self.my_turn = True

        while self.in_progress:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    raise CloseException()

                if event.type == pygame.MOUSEBUTTONDOWN:
                    if self.prom_menu_coords != None:
                        if event.pos[0] < self.prom_menu_coords[0] or event.pos[0] > self.prom_menu_coords[0] + 2 * self.cell_size[0] or event.pos[1] < self.prom_menu_coords[1] or event.pos[1] > self.prom_menu_coords[1] + 2 * self.cell_size[1]:
                            continue

                        if event.pos[0] < self.prom_menu_coords[0] + self.cell_size[0] and event.pos[1] < self.prom_menu_coords[1] + self.cell_size[1]:
                            prom = Piece.QUEEN_W if self.white else Piece.QUEEN_B
                        elif event.pos[0] > self.prom_menu_coords[0] + self.cell_size[0] and event.pos[1] < self.prom_menu_coords[1] + self.cell_size[1]:
                            prom = Piece.KNIGHT_W if self.white else Piece.KNIGHT_B
                        elif event.pos[0] < self.prom_menu_coords[0] + self.cell_size[0] and event.pos[1] > self.prom_menu_coords[1] + self.cell_size[1]:
                            prom = Piece.ROOK_W if self.white else Piece.ROOK_B
                        elif event.pos[0] > self.prom_menu_coords[0] + self.cell_size[0] and event.pos[1] > self.prom_menu_coords[1] + self.cell_size[1]:
                            prom = Piece.BISHOP_W if self.white else Piece.BISHOP_B

                        orig_x, orig_y, x, y = self.prom_move
                        to_send.append(self.encode_move(orig_x, orig_y, x, y, prom))

                        self.set_piece(y, x, prom)

                        self.prom_menu_coords = None
                        continue
                    if self.moved or not self.my_turn:
                        continue

                    if event.pos[0] > self.board_size[0] or event.pos[1] > self.board_size[1]:
                        continue

                    self.origboard = copy.deepcopy(self.board)

                    x, y = math.floor(event.pos[0] / self.cell_size[0]), math.floor(event.pos[1] / self.cell_size[1])
                    piece = self.get_piece(y, x)

                    if piece == Piece.NONE:
                        continue

                    if (piece.value & 8) == (int(self.white) << 3):
                        continue

                    sprite = self.sprites[piece.value]
                    rect = sprite.get_rect()

                    rect.topleft = event.pos

                    dragging = (piece, rect, (x, y))

                    self.del_piece(y, x)

                    to_send.append("moves " + self.encode_alg(x, y))

                if event.type == pygame.MOUSEBUTTONUP:
                    if dragging is None:
                        continue
                    
                    piece, rect, (orig_x, orig_y)  = dragging

                    dragging = None

                    if event.pos[0] >= self.board_size[0] or event.pos[0] < 0 or event.pos[1] >= self.board_size[1] or event.pos[1] < 0:
                        self.set_piece(orig_y, orig_x, piece)

                    else:
                        x, y = math.floor(event.pos[0] / self.cell_size[0]), math.floor(event.pos[1] / self.cell_size[1])
                        if self.possible_moves != None and (y, x) not in self.possible_moves[1]:
                            (x, y) = (orig_x, orig_y)

                        if x != orig_x or y != orig_y:
                            if piece in [Piece.PAWN_W, Piece.PAWN_B] and y in [0, 7]:
                                menu_x, menu_y = pygame.mouse.get_pos()

                                if menu_x > screen_size[0] / 2:
                                    menu_x -= self.cell_size[0] * 2
                                if menu_y > screen_size[1] / 2:
                                    menu_y -= self.cell_size[0] * 2

                                self.prom_menu_coords = (menu_x, menu_y)
                                self.prom_move = (orig_x, orig_y, x, y)

                            if self.prom_menu_coords == None:
                                to_send.append(self.encode_move(orig_x, orig_y, x, y))
                            self.moved = True
                            self.possible_moves = None

                            if self.translate_coords(y, x) == self.en_passant_tgt:
                                if y == 5:
                                    self.del_piece(4, x)
                                else:
                                    self.del_piece(3, x)

                            self.en_passant_tgt = None

                            if piece in [Piece.PAWN_W, Piece.PAWN_B] and abs(y - orig_y) == 2:
                                self.en_passant_tgt = self.translate_coords(round((y + orig_y)/2), x)

                            if piece in [Piece.KING_W, Piece.KING_B]:
                                if x - orig_x == 2:
                                    self.set_piece(orig_y, orig_x + 1, Piece(Piece.ROOK_W.value | (piece.value & 8)))
                                    self.del_piece(orig_y, 7)
                                elif x - orig_x == -2:
                                    self.set_piece(orig_y, orig_x - 1, Piece(Piece.ROOK_W.value | (piece.value & 8)))
                                    self.del_piece(orig_y, 0)

                        self.set_piece(y, x, piece)
            
            game.draw(screen)

            if dragging is not None:
                piece, rect, _ = dragging
                rect.center = pygame.mouse.get_pos()
                screen.blit(self.sprites[piece.value], rect)

            pygame.display.flip()

            ready_read, ready_write, _ = select.select([self.sock], [self.sock], [], 0.008)
            if len(ready_read) > 0:
                msg = self.read_socket()

                if msg.startswith("ok"):
                    self.checked_opp = False
                    self.checked_me = False
                    self.moved = False
                    self.my_turn = False
                    self.origboard = None
                    self.possible_moves = None
                    if msg[-1] == '+' or msg[-1] == '#':
                        self.checked_opp = True
                elif msg == "no":
                    self.board = self.origboard
                    self.origboard = None
                    self.moved = False
                    self.possible_moves = None
                elif msg.startswith("moves "):
                    moves: list[tuple[int, int]] = []
                    origin = self.decode_alg(msg[6:8])
                    for i in range(9, len(msg), 2):
                        try:
                            moves.append(self.decode_alg(msg[i:i+2]))
                        except:
                            continue
                    self.possible_moves = (origin, moves)
                elif msg.startswith("end "):
                    self.score = msg[4:]
                    print(msg[4:])
                    self.in_progress = False
                    continue
                else:
                    self.move_piece(msg)
                    self.checked_me = False
                    self.checked_opp = False
                    if msg[-1] == '+' or msg[-1] == '#':
                        self.checked_me = True
                    if not self.spectator:
                        self.my_turn = True

            elif len(ready_write) > 0 and len(to_send) > 0:
                self.write_socket(to_send.popleft())

            dt = clock.tick(60) / 1000

        self.sock.close()

    def draw(self, surface: pygame.Surface) -> None:
        surface.fill("darkgreen")

        for i in range(8):
            for j in range(8):
                coords = (j * self.cell_size[1], i * self.cell_size[0])
                pygame.draw.rect(surface, self.color_light if (i + j) % 2 == 0 else self.color_dark, (coords, self.cell_size))

                piece = self.get_piece(i, j)

                if self.possible_moves != None:
                    if (i, j) == self.possible_moves[0]:
                        pygame.draw.rect(screen, self.color_pos, (coords, self.cell_size))
                    elif (i, j) in self.possible_moves[1]:
                        if piece == Piece.NONE and self.translate_coords(i, j) != self.en_passant_tgt:
                            pygame.draw.circle(screen, self.color_pos, (coords[0] + self.cell_size[1] / 2, coords[1] + self.cell_size[0] / 2), self.cell_size[0] / 6)
                        else:
                            pygame.draw.circle(screen, self.color_pos, (coords[0] + self.cell_size[1] / 2, coords[1] + self.cell_size[0] / 2), self.cell_size[0] / 2, round(self.cell_size[0] / 20))

                if piece == Piece.NONE:
                    continue

                if self.checked_me:
                    if piece == Piece(Piece.KING_W.value | ((1-int(self.white)) << 3)):
                        surface.blit(self.check_circle, coords)

                if self.checked_opp:
                    if piece == Piece(Piece.KING_W.value | (int(self.white) << 3)):
                        surface.blit(self.check_circle, coords)

                sprite = self.sprites[piece.value]
                rect = sprite.get_rect()
                rect = rect.move(self.cell_size[0] * j, self.cell_size[1] * i)
                surface.blit(sprite, rect)

        if self.prom_menu_coords != None:
            prom_select = self.prom_select_w if self.white else self.prom_select_b
            surface.blit(prom_select, self.prom_menu_coords)

    def translate_coords(self, y: int, x: int) -> tuple[int, int]:
        return (y, x) if self.white else (7-y, x)

    def get_piece(self, y: int, x: int) -> Piece:
        return self.board[y][x] if self.white else self.board[7-y][x]

    def del_piece(self, y: int, x: int) -> None:
        if not self.white:
            y = 7 - y
        self.board[y][x] = Piece.NONE

    def set_piece(self, y: int, x: int, piece: Piece) -> None:
        if not self.white:
            y = 7 - y
        self.board[y][x] = piece

    def move_piece(self, move: str) -> None:

        if len(move) < 4:
            raise Exception("Incorrect move", move)

        src_r, src_f = self.decode_alg(move[0:2])
        dst_r, dst_f = self.decode_alg(move[2:4])

        if self.get_piece(src_r, src_f) == Piece.NONE:
            raise Exception("Cannot move a NULL piece", move)

        if self.translate_coords(dst_r, dst_f) == self.en_passant_tgt:
            if dst_r == 5:
                self.del_piece(4, dst_f)
            else:
                self.del_piece(3, dst_f)

        self.en_passant_tgt = None

        piece = self.get_piece(src_r, src_f)

        if piece in [Piece.PAWN_W, Piece.PAWN_B] and abs(dst_r - src_r) == 2:
            self.en_passant_tgt = self.translate_coords(round((dst_r + src_r)/2), src_f)

        if piece in [Piece.KING_W, Piece.KING_B]:
            if dst_f - src_f == 2:
                self.set_piece(src_r, src_f + 1, Piece(Piece.ROOK_W.value | (piece.value & 8)))
                self.del_piece(src_r, 7)
            elif dst_f - src_f == -2:
                self.set_piece(src_r, src_f - 1, Piece(Piece.ROOK_W.value | (piece.value & 8)))
                self.del_piece(src_r, 0)

        if len(move) >= 6 and move[4] == '=':
            prom = Piece.NONE
            match move[5]:
                case 'Q':
                    prom = Piece.QUEEN_W
                case 'N':
                    prom = Piece.KNIGHT_W
                case 'R':
                    prom = Piece.ROOK_W
                case 'B':
                    prom = Piece.BISHOP_W

            piece = Piece(prom.value | (piece.value & 8))

        self.set_piece(dst_r, dst_f, piece)
        self.del_piece(src_r, src_f)

    def encode_move(self, orig_x: int, orig_y: int, new_x: int, new_y: int, prom: Piece = Piece.NONE) -> str:
        orig = self.encode_alg(orig_x, orig_y)
        new = self.encode_alg(new_x, new_y)

        prom_str = ""
        match prom:
            case Piece.QUEEN_W | Piece.QUEEN_B:
                prom_str = "=Q"
            case Piece.KNIGHT_W | Piece.KNIGHT_B:
                prom_str = "=N"
            case Piece.ROOK_W | Piece.ROOK_B:
                prom_str = "=R"
            case Piece.BISHOP_W | Piece.BISHOP_B:
                prom_str = "=B"

        return "".join([orig, new, prom_str])

    def decode_alg(self, alg: str) -> tuple[int, int]:
        if len(alg) != 2:
            raise Exception("Incorrect length of algebraic position", alg)

        file = ord(alg[0]) - ord('a')
        rank = (8 - int(alg[1])) if self.white else (int(alg[1]) - 1)

        if file < 0 or file >= 8 or rank < 0 or rank >= 8:
            raise Exception("Incorrect position", alg)

        return (rank, file)

    def encode_alg(self, x: int, y: int) -> str:
        if x >= 8 or x < 0 or y >= 8 or y < 0:
            raise Exception("Incorrect position", x, y)

        file = chr(ord('a') + x)
        rank = str((8 - y) if self.white else (y + 1))

        return "".join([file, rank])

    def read_socket(self) -> str:

        buffer = bytearray(3)
        chunks = memoryview(buffer)
        total_recd = 0

        while total_recd < 3:
            bytes_recd = self.sock.recv_into(chunks[total_recd:], min(3 - total_recd, 3))
            if bytes_recd == 0:
                raise Exception("Socket connection broken")

            total_recd += bytes_recd

        bytes_expect = int(chunks[:total_recd])

        buffer = bytearray(bytes_expect)
        chunks = memoryview(buffer)
        total_recd = 0

        while total_recd < bytes_expect:
            bytes_recd = self.sock.recv_into(chunks[total_recd:], min(bytes_expect - total_recd, bytes_expect))
            if bytes_recd == 0:
                raise Exception("Socket connection broken")

            total_recd += bytes_recd

        return str(chunks[:total_recd], encoding="ascii").strip()

    def write_socket(self, msg: str) -> None:
        msg = msg.strip()
        msg = bytes(f"{str(len(msg)).rjust(3, '0')}{msg}", encoding="ascii")

        to_send = len(msg)
        total_sent = 0
        while total_sent < to_send:
            sent = self.sock.send(msg[total_sent:])

            if sent == 0:
                raise Exception("Socket connection broken")
            
            total_sent += sent


pygame.init()
pygame.font.init()

screen_size = width, height = 800, 800
screen = pygame.display.set_mode(screen_size)
clock = pygame.time.Clock()
running = True
dt = 0

try:
    host = sys.argv[1]
except IndexError:
    host = "127.0.0.1"

try:
    port = int(sys.argv[2])
except IndexError:
    port = 40000

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect((host, port))

game = Game(sock)

try:
    game.start()
except CloseException:
    running = False

if running:
    timer = 1.0
    game_over_font = pygame.font.SysFont("Inconsolata", 50)
    game_over_msg = "Game Over!"

    if game.spectator:
        if game.score == '1-0':
            game_over_msg = "White Won!"
        elif game.score == '0-1':
            game_over_msg = "Black Won!"
        elif game.score == '1/2-1/2':
            game_over_msg = "Draw!"
    else:
        if game.score == '1-0':
            game_over_msg = "You Won!" if game.white else "You Lost!"
        elif game.score == '0-1':
            game_over_msg = "You Lost!" if game.white else "You Won!"
        elif game.score == '1/2-1/2':
            game_over_msg = "Draw!"
    

    game_over = game_over_font.render(game_over_msg, True, (255, 255, 255), (0, 0, 0))

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT or event.type == pygame.KEYDOWN:
            running = False

    game.draw(screen)
    if timer <= 0:
        go_rect = game_over.get_rect()
        screen.blit(game_over, (width / 2 - go_rect.width / 2, height / 2 - go_rect.height / 2))

    pygame.display.flip()

    dt = clock.tick(60) / 1000
    if timer > 0:
        timer -= dt

pygame.quit()
