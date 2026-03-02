import os
os.environ["SDL_AUDIODRIVER"] = "dummy"  # trygg på macOS

import sys
import random
from pathlib import Path
import pygame

pygame.init()

# --- Vindauge ---
WIDTH, HEIGHT = 800, 600
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Gruvespelet")

font = pygame.font.SysFont(None, 44)
small_font = pygame.font.SysFont(None, 28)
tiny_font = pygame.font.SysFont(None, 22)

# --- Reglar ---
MIN_TAP = 7  # kan ikkje tape før dette talet trekk

# --- Assets ---
import sys
from pathlib import Path

def resource_path(*parts: str) -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base.joinpath(*parts)

ASSETS = resource_path("assets")

KATASTROFEKORT = [
    ("Slange", "slange.png"),
    ("Atom", "atomskyeksplosjon.png"),
    ("Flaggermus", "flaggermus.png"),
    ("Banditt", "banditt.png"),
]

POENGKORT = [
    ("Blå diamant", "bla_diamant.png"),
    ("Grøn diamant", "gron_diamant.png"),
    ("Raud diamant", "raud_diamant.png"),
]


def load_image(filename: str, size: tuple[int, int]) -> pygame.Surface | None:
    path = ASSETS / filename
    try:
        img = pygame.image.load(str(path)).convert_alpha()
        return pygame.transform.smoothscale(img, size)
    except FileNotFoundError:
        print(f"[MANGAR] Fann ikkje bilete: {path}")
        return None
    except pygame.error as e:
        print(f"[FEIL] Klarte ikkje laste bilete {path}: {e}")
        return None


CARD_SIZE = (230, 300)
LOG_SIZE = (56, 72)

card_img: dict[tuple[str, str], pygame.Surface | None] = {}
log_img: dict[tuple[str, str], pygame.Surface | None] = {}

for card in (KATASTROFEKORT + POENGKORT):
    card_img[card] = load_image(card[1], CARD_SIZE)
    log_img[card] = load_image(card[1], LOG_SIZE)


def teikn_knapp(text, x, y, w, h, enabled=True):
    rect = pygame.Rect(x, y, w, h)
    bg = (180, 180, 180) if enabled else (120, 120, 120)
    pygame.draw.rect(screen, bg, rect, border_radius=10)

    fg = (0, 0, 0) if enabled else (40, 40, 40)
    label = small_font.render(text, True, fg)
    screen.blit(label, (x + (w - label.get_width()) // 2, y + (h - label.get_height()) // 2))
    return rect


def lag_basisstokk():
    # same basefordeling som originalen (men vi fjernar aldri kort)
    return (KATASTROFEKORT * 2) + (POENGKORT * 5)


# --------- Game state (blir sett når du trykker start) ---------
MAKS_TREKK: int | None = None

basisstokk = []
katastrofe_history = []
poeng_tvang = 0
spel_over = False
sist_kort = None
kort_trekt = 0
katastrofe_counts = {}
tap_katastrofe = None


def restart():
    global basisstokk, katastrofe_history, poeng_tvang, spel_over, sist_kort, kort_trekt
    global katastrofe_counts, tap_katastrofe

    basisstokk = lag_basisstokk()
    random.shuffle(basisstokk)

    katastrofe_history = []
    poeng_tvang = 0
    spel_over = False
    sist_kort = None
    kort_trekt = 0

    katastrofe_counts = {k: 0 for k in KATASTROFEKORT}
    tap_katastrofe = None


def vel_kort_for_trekk():
    """
    Garanterer:
    - ingen tap før MIN_TAP (hindrar 2. like katastrofe før då)
    - tap seinast på MAKS_TREKK (tvingar 2. like katastrofe på/innan då)
    - respekterer poeng_tvang (2 poengkort etter katastrofe)
    """
    assert MAKS_TREKK is not None
    upcoming = kort_trekt + 1

    # tvang: må ta poengkort
    if poeng_tvang > 0:
        return random.choice(POENGKORT)

    har_ein_katastrofe = any(v >= 1 for v in katastrofe_counts.values())

    # Vi må sikre minst éin katastrofe tidleg nok til at den kan kome igjen innan MAKS_TREKK,
    # med 2 tvungne poengkort i mellom.
    siste_forste_kat = MAKS_TREKK - 3
    if (not har_ein_katastrofe) and upcoming >= siste_forste_kat:
        nullar = [k for k, c in katastrofe_counts.items() if c == 0]
        return random.choice(nullar) if nullar else random.choice(KATASTROFEKORT)

    # på MAKS_TREKK: tving fram “andre gong” av ein katastrofe som er sett 1 gong
    if upcoming >= MAKS_TREKK:
        einar = [k for k, c in katastrofe_counts.items() if c == 1]
        if einar:
            return random.choice(einar)
        return random.choice(KATASTROFEKORT)  # fallback

    # før MIN_TAP: hindra 2. like katastrofe
    if upcoming < MIN_TAP:
        trygg_kat = [k for k, c in katastrofe_counts.items() if c == 0]
        kandidat = POENGKORT + trygg_kat
        return random.choice(kandidat)

    # rett før MAKS_TREKK: helst poengkort så vi ikkje låser oss i poeng-tvang på siste trekk
    if upcoming in (MAKS_TREKK - 1, MAKS_TREKK - 2):
        return random.choice(POENGKORT)

    return random.choice(basisstokk)


def trekk_kort():
    global poeng_tvang, katastrofe_history, spel_over, sist_kort, kort_trekt
    global katastrofe_counts, tap_katastrofe

    if spel_over:
        return

    kort = vel_kort_for_trekk()
    sist_kort = kort
    kort_trekt += 1

    if kort in KATASTROFEKORT:
        poeng_tvang = 2
        katastrofe_history.append(kort)

        katastrofe_counts[kort] += 1

        if katastrofe_counts[kort] >= 2 and kort_trekt >= MIN_TAP:
            spel_over = True
            tap_katastrofe = kort
    else:
        if poeng_tvang > 0:
            poeng_tvang -= 1

    # aldri meir enn MAKS_TREKK
    if MAKS_TREKK is not None and kort_trekt >= MAKS_TREKK and not spel_over:
        spel_over = True


# ---------- Startskjerm (Pygame input) ----------
def draw_start_screen(input_str: str, error: str | None):
    screen.fill((30, 30, 60))

    title = font.render("Gruvespelet", True, (240, 240, 240))
    screen.blit(title, (WIDTH // 2 - title.get_width() // 2, 90))

    prompt = small_font.render("Skriv maks tal trekk og trykk Enter:", True, (220, 220, 220))
    screen.blit(prompt, (WIDTH // 2 - prompt.get_width() // 2, 170))

    hint = tiny_font.render(f"(må vere >= {MIN_TAP})", True, (180, 180, 180))
    screen.blit(hint, (WIDTH // 2 - hint.get_width() // 2, 200))

    # input-boks
    box = pygame.Rect(WIDTH // 2 - 120, 240, 240, 54)
    pygame.draw.rect(screen, (200, 200, 200), box, border_radius=10)
    pygame.draw.rect(screen, (80, 80, 80), box, 2, border_radius=10)

    show = input_str if input_str else ""
    value = font.render(show, True, (0, 0, 0))
    screen.blit(value, (box.x + 12, box.y + 10))

    if error:
        err = small_font.render(error, True, (255, 120, 120))
        screen.blit(err, (WIDTH // 2 - err.get_width() // 2, 310))

    start_btn = teikn_knapp("Start spel", WIDTH // 2 - 90, 380, 180, 52, enabled=True)
    return start_btn


def parse_input_to_int(input_str: str) -> int | None:
    if not input_str:
        return None
    try:
        return int(input_str)
    except ValueError:
        return None


# ---------- Main loop ----------
MODE = "menu"  # "menu" eller "game"
input_str = ""
error_msg = None

clock = pygame.time.Clock()
running = True

while running:
    clock.tick(60)

    if MODE == "menu":
        start_rect = draw_start_screen(input_str, error_msg)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            if event.type == pygame.KEYDOWN:
                error_msg = None

                if event.key == pygame.K_RETURN:
                    n = parse_input_to_int(input_str)
                    if n is None:
                        error_msg = "Skriv eit heiltal."
                    elif n < MIN_TAP:
                        error_msg = f"Må vere minst {MIN_TAP}."
                    else:
                        MAKS_TREKK = n
                        restart()
                        MODE = "game"

                elif event.key == pygame.K_BACKSPACE:
                    input_str = input_str[:-1]

                else:
                    # berre tal
                    if event.unicode.isdigit():
                        # litt grense så du ikkje får veldig lange tal
                        if len(input_str) < 4:
                            input_str += event.unicode

            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if start_rect.collidepoint(event.pos):
                    n = parse_input_to_int(input_str)
                    if n is None:
                        error_msg = "Skriv eit heiltal."
                    elif n < MIN_TAP:
                        error_msg = f"Må vere minst {MIN_TAP}."
                    else:
                        MAKS_TREKK = n
                        restart()
                        MODE = "game"

        pygame.display.flip()
        continue

    # ------------- GAME MODE -------------
    screen.fill((30, 30, 60))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if trekk_rect.collidepoint(event.pos) and (not spel_over):
                trekk_kort()

            if spel_over and restart_rect.collidepoint(event.pos):
                restart()

            if spel_over and change_rect.collidepoint(event.pos):
                # tilbake til meny for å velje ny maks
                MODE = "menu"
                input_str = ""
                error_msg = None

    # topptekst: berre teljing
    status = f"Trekte kort: {kort_trekt}"
    status_surf = small_font.render(status, True, (220, 220, 220))
    screen.blit(status_surf, (WIDTH // 2 - status_surf.get_width() // 2, 15))

    # katastrofelogg
    screen.blit(small_font.render("Katastrofar:", True, (255, 200, 200)), (20, 45))
    y = 75
    for k in katastrofe_history:
        img = log_img.get(k)
        if img:
            screen.blit(img, (20, y))
        else:
            pygame.draw.rect(screen, (120, 80, 80), (20, y, LOG_SIZE[0], LOG_SIZE[1]), border_radius=6)

        name, _ = k
        t = small_font.render(name, True, (255, 130, 130))
        screen.blit(t, (20 + LOG_SIZE[0] + 10, y + 20))
        y += LOG_SIZE[1] + 10

    # siste kort
    if sist_kort:
        kort_rect = pygame.Rect(285, 150, CARD_SIZE[0], CARD_SIZE[1])
        img = card_img.get(sist_kort)
        if img:
            screen.blit(img, kort_rect.topleft)
        else:
            pygame.draw.rect(screen, (100, 100, 100), kort_rect, border_radius=12)
            name, _ = sist_kort
            tekst = font.render(name, True, (0, 0, 0))
            screen.blit(tekst, (WIDTH // 2 - tekst.get_width() // 2, 290))
    else:
        info = small_font.render("Trykk 'Trekk kort' for å starte.", True, (220, 220, 220))
        screen.blit(info, (WIDTH // 2 - info.get_width() // 2, 300))

    # game over
    if spel_over:
        go = font.render("GAME OVER", True, (255, 80, 80))
        screen.blit(go, (WIDTH // 2 - go.get_width() // 2, 90))

        if tap_katastrofe:
            msg = small_font.render(f"Du fekk '{tap_katastrofe[0]}' to gongar.", True, (255, 200, 200))
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 125))

        info = tiny_font.render(f"Slutta etter {kort_trekt} trekk (maks {MAKS_TREKK}).", True, (220, 220, 220))
        screen.blit(info, (WIDTH // 2 - info.get_width() // 2, 155))

    # knappar
    trekk_rect = teikn_knapp("Trekk kort", 320, 500, 160, 50, enabled=(not spel_over))

    restart_rect = pygame.Rect(0, 0, 0, 0)
    change_rect = pygame.Rect(0, 0, 0, 0)
    if spel_over:
        restart_rect = teikn_knapp("Start på nytt", 260, 430, 200, 50, enabled=True)
        change_rect = teikn_knapp("Endre maks", 470, 430, 170, 50, enabled=True)

    pygame.display.flip()

pygame.quit()
sys.exit()