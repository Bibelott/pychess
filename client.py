import sys, pygame
from enum import Enum
import socket, select

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

class Game:

    def __init__(self, FEN: str = START_POS) -> None:
        self.board: list[list[Piece]] = []

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

        self.sprites: list[pygame.Surface] = [None for _ in range(15)]

        for file, piece in [("wP", Piece.PAWN_W), ("wR", Piece.ROOK_W), ("wN", Piece.KNIGHT_W), ("wB", Piece.BISHOP_W), ("wQ", Piece.QUEEN_W), ("wK", Piece.KING_W), ("bP", Piece.PAWN_B), ("bR", Piece.ROOK_B), ("bN", Piece.KNIGHT_B), ("bB", Piece.BISHOP_B), ("bQ", Piece.QUEEN_B), ("bK", Piece.KING_B)]:
            svg = pygame.image.load(f"resources/{file}.png")
            img = pygame.transform.scale(svg, cell_size).convert_alpha()
            self.sprites[piece.value] = img


    def draw(self, surface: pygame.Surface) -> None:

        for i in range(8):
            for j in range(8):
                piece = self.board[i][j]

                if piece == Piece.NONE:
                    continue

                sprite = self.sprites[piece.value]
                rect = sprite.get_rect()
                rect = rect.move(cell_size[0] * j, cell_size[1] * i)
                screen.blit(sprite, rect)

    def move_piece(self, move: str) -> None:

        if len(move) != 4:
            raise Exception("Incorrect move", move)

        src_r, src_f = self.decode_alg(move[0:2])
        dst_r, dst_f = self.decode_alg(move[2:4])

        if self.board[src_r][src_f] == Piece.NONE:
            raise Exception("Cannot move a NULL piece", move)

        self.board[dst_r][dst_f] = self.board[src_r][src_f]
        self.board[src_r][src_f] = Piece.NONE

    @staticmethod
    def decode_alg(alg: str) -> (int, int):
        if len(alg) != 2:
            raise Exception("Incorrect length of algebraic position", alg)

        file = ord(alg[0]) - ord('a')
        rank = 8 - int(alg[1])

        if file < 0 or file >= 8 or rank < 0 or rank >= 8:
            raise Exception("Incorrect position", alg)

        return (rank, file)

def read(socket) -> str:

    buffer = bytearray(3)
    chunks = memoryview(buffer)
    total_recd = 0

    while total_recd < 3:
        bytes_recd = sock.recv_into(chunks[total_recd:], min(3 - total_recd, 3))
        if bytes_recd == 0:
            raise Exception("Socket connection broken")

        total_recd += bytes_recd

    bytes_expect = int(chunks[:total_recd])

    buffer = bytearray(bytes_expect)
    chunks = memoryview(buffer)
    total_recd = 0

    while total_recd < bytes_expect:
        bytes_recd = sock.recv_into(chunks[total_recd:], min(bytes_expect - total_recd, bytes_expect))
        if bytes_recd == 0:
            raise Exception("Socket connection broken")

        total_recd += bytes_recd

    return str(chunks[:total_recd], encoding="ascii").strip()


pygame.init()

screen_size = width, height = 800, 800
screen = pygame.display.set_mode(screen_size)
clock = pygame.time.Clock()
running = True
dt = 0

board_size = screen_size
cell_size = (board_size[0] / 8, board_size[1] / 8)

color_dark = (181, 136, 99)
color_light = (240, 217, 181)

game = Game()
# game = Game("8/pp2bp2/2k5/3p4/P4pQ1/1K6/RP1r4/2r5 w - - 8 40")

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(("127.0.0.1", 42069))

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

    screen.fill("darkgreen")

    for i in range(8):
        for j in range(8):
            pygame.draw.rect(screen, color_light if (i + j) % 2 == 0 else color_dark, ((j * cell_size[1], i * cell_size[0]), cell_size))

    game.draw(screen)

    pygame.display.flip()

    ready_read, _, _ = select.select([sock], [], [], 0.008)
    if len(ready_read) > 0:
        move = read(sock)

        game.move_piece(move)

    dt = clock.tick(60) / 1000

sock.close()
pygame.quit()