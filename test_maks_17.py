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

# --- Assets ---
ASSETS = Path(__file__).parent / "assets"

# Kortdata (namn, filnamn)
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


# Last bilete ein gong
CARD_SIZE = (230, 300)
LOG_SIZE = (56, 72)

card_img: dict[tuple[str, str], pygame.Surface | None] = {}
log_img: dict[tuple[str, str], pygame.Surface | None] = {}
for card in (KATASTROFEKORT + POENGKORT):
    card_img[card] = load_image(card[1], CARD_SIZE)
    log_img[card] = load_image(card[1], LOG_SIZE)


def lag_basisstokk():
    # Brukar same "basefordeling" som originalen (men vi fjernar aldri kort)
    return (KATASTROFEKORT * 2) + (POENGKORT * 5)


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

    # tel kor mange gongar kvar katastrofe er trekt
    katastrofe_counts = {k: 0 for k in KATASTROFEKORT}
    tap_katastrofe = None


def vel_kort_for_trekk():
    """
    Vel neste kort slik at:
    - Spelet kan ikkje ende før trekk 7 (hindrar 2. like katastrofe før då)
    - Spelet MÅ ende seinast på trekk 17 (tvingar 2. like katastrofe på/innan då)
    - Respekterer poeng_tvang (2 poengkort etter katastrofe)
    """
    global poeng_tvang, kort_trekt, katastrofe_counts

    upcoming = kort_trekt + 1  # neste trekknummer (1..)

    # Når poeng_tvang: må trekkje poengkort
    if poeng_tvang > 0:
        return random.choice(POENGKORT)

    # Dersom vi ikkje har trekt nokon katastrofe enno, må vi sørge for minst éin før vi kjem for langt.
    # Vi tvingar ein "første katastrofe" innan trekk 14, slik at vi har tid til:
    # trekk 14: katastrofe (første gong)
    # trekk 15-16: poengkort (tvang)
    # trekk 17: same katastrofe igjen (andre gong) => game over
    har_ein_katastrofe = any(v >= 1 for v in katastrofe_counts.values())

    if (not har_ein_katastrofe) and upcoming >= 14:
        # tving ein katastrofe som ikkje er trekt før
        nullar = [k for k, c in katastrofe_counts.items() if c == 0]
        return random.choice(nullar) if nullar else random.choice(KATASTROFEKORT)

    # Om vi er på trekk 17 og ikkje er i poeng-tvang,
    # tving fram at det blir den andre like katastrofa.
    if upcoming >= 17:
        einar = [k for k, c in katastrofe_counts.items() if c == 1]
        if einar:
            return random.choice(einar)  # dette blir 2. like => tap
        # Fallback (burde ikkje skje pga. regelen over som tvingar ein katastrofe før 14)
        return random.choice(KATASTROFEKORT)

    # Før trekk 7: vi må hindre at same katastrofe kjem for 2. gong
    if upcoming < 7:
        # tillat katastrofar berre dersom dei ikkje har kome før (count==0)
        trygg_kat = [k for k, c in katastrofe_counts.items() if c == 0]
        # bland litt: mest poengkort, av og til katastrofe
        kandidat = POENGKORT + trygg_kat
        return random.choice(kandidat)

    # Trekk 15 og 16: om vi enno ikkje har tap, er det lurt å ikkje trekke katastrofe her
    # (ellers får vi poeng-tvang som kan blokkere katastrofe på trekk 17).
    if upcoming in (15, 16):
        return random.choice(POENGKORT)

    # Elles: vanleg trekking (poeng + katastrofe), men vi kan framleis ende når som helst >= 7
    return random.choice(basisstokk)


def trekk_kort():
    global poeng_tvang, katastrofe_history, spel_over, sist_kort, kort_trekt
    global katastrofe_counts, tap_katastrofe

    if spel_over:
        return

    kort = vel_kort_for_trekk()
    sist_kort = kort
    kort_trekt += 1

    # Katastrofe?
    if kort in KATASTROFEKORT:
        poeng_tvang = 2
        katastrofe_history.append(kort)

        katastrofe_counts[kort] += 1

        # Game over berre om vi er på trekk >= 7 (kravet ditt)
        if katastrofe_counts[kort] >= 2 and kort_trekt >= 7:
            spel_over = True
            tap_katastrofe = kort

        # Ekstra sikkerheit: om vi av ein eller annan grunn når 17 utan tap,
        # stoppar vi likevel. (Med logikken over skal dette ikkje skje.)
        if kort_trekt >= 17 and not spel_over:
            spel_over = True
            tap_katastrofe = kort  # best-effort

    else:
        # Poengkort
        if poeng_tvang > 0:
            poeng_tvang -= 1

    # Hard cap: aldri meir enn 17 trekk
    if kort_trekt >= 17 and not spel_over:
        spel_over = True


def teikn_knapp(text, x, y, w, h, enabled=True):
    rect = pygame.Rect(x, y, w, h)
    bg = (180, 180, 180) if enabled else (120, 120, 120)
    pygame.draw.rect(screen, bg, rect, border_radius=8)

    fg = (0, 0, 0) if enabled else (40, 40, 40)
    label = small_font.render(text, True, fg)
    lx = x + (w - label.get_width()) // 2
    ly = y + (h - label.get_height()) // 2
    screen.blit(label, (lx, ly))
    return rect


# --- Start spel ---
restart()

clock = pygame.time.Clock()
running = True

while running:
    clock.tick(60)
    screen.fill((30, 30, 60))

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if trekk_rect.collidepoint(event.pos) and (not spel_over):
                trekk_kort()
            if spel_over and restart_rect.collidepoint(event.pos):
                restart()

    # --- Topptekst: berre teljing, sentrert ---
    status = f"Trekte kort: {kort_trekt}"
    status_surf = small_font.render(status, True, (220, 220, 220))
    screen.blit(status_surf, (WIDTH // 2 - status_surf.get_width() // 2, 15))

    # --- Katastrofelogg (venstre) ---
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

    # --- Siste kort (midten) ---
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

    # --- Game over ---
    if spel_over:
        go = font.render("GAME OVER", True, (255, 80, 80))
        screen.blit(go, (WIDTH // 2 - go.get_width() // 2, 90))

        if tap_katastrofe:
            msg = small_font.render(
                f"Du fekk '{tap_katastrofe[0]}' to gongar.",
                True,
                (255, 200, 200),
            )
            screen.blit(msg, (WIDTH // 2 - msg.get_width() // 2, 125))

    # --- Knappar ---
    trekk_rect = teikn_knapp("Trekk kort", 320, 500, 160, 50, enabled=(not spel_over))

    restart_rect = pygame.Rect(0, 0, 0, 0)
    if spel_over:
        restart_rect = teikn_knapp("Start på nytt", 290, 430, 220, 50, enabled=True)

    pygame.display.flip()

pygame.quit()
sys.exit()