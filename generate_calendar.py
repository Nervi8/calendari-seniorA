import re
import hashlib
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pdfplumber
from icalendar import Calendar, Event


PDF_FILE = "calendari.pdf"
OUTPUT_FILE = "calendar.ics"

CALENDAR_NAME = "Partits Bàsquet"
TEAM_ID = "88834"

LOCAL_TZ = ZoneInfo("Europe/Madrid")

# Duración que aparecerá reservada en el calendario
GAME_DURATION_MINUTES = 120


def clean_text(text):
    if not text:
        return ""

    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)

    return text.strip()


def extract_lines_from_pdf(pdf_file):
    lines = []

    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            text = page.extract_text()

            if not text:
                continue

            for line in text.splitlines():
                line = clean_text(line)

                if line:
                    lines.append(line)

    return lines


def parse_datetime(line):
    """
    Detecta formatos como:

    27/09/2026 18:00
    27/09/26 18:00
    """

    pattern = r"(\d{1,2}/\d{1,2}/(?:\d{2}|\d{4}))\s+(\d{1,2}:\d{2})"

    match = re.search(pattern, line)

    if not match:
        return None

    date_text = match.group(1)
    time_text = match.group(2)

    for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%y %H:%M"):
        try:
            dt = datetime.strptime(
                f"{date_text} {time_text}",
                fmt
            )

            return dt.replace(tzinfo=LOCAL_TZ)

        except ValueError:
            pass

    return None


def remove_datetime(line):
    pattern = r"\d{1,2}/\d{1,2}/(?:\d{2}|\d{4})\s+\d{1,2}:\d{2}"

    return clean_text(
        re.sub(pattern, "", line, count=1)
    )


def make_uid(description):
    """
    IMPORTANTE:
    No usamos la fecha ni la hora para generar el UID.

    Así, si FCBQ mueve un partido de sábado a domingo,
    el calendario puede interpretarlo como el mismo evento
    actualizado en lugar de generar otro partido.
    """

    normalized = clean_text(description).lower()

    digest = hashlib.sha256(
        f"{TEAM_ID}-{normalized}".encode("utf-8")
    ).hexdigest()[:24]

    return f"{digest}@basquet-calendar-{TEAM_ID}"


def parse_games(lines):
    games = []

    current_game = None

    ignored_phrases = [
        "Calendari Global Equip",
        "Data i hora",
        "Partit",
        "Categoria",
        "Pàgina",
    ]

    for line in lines:

        if any(
            line.startswith(text)
            for text in ignored_phrases
        ):
            continue

        dt = parse_datetime(line)

        if dt:
            if current_game:
                games.append(current_game)

            current_game = {
                "datetime": dt,
                "text": remove_datetime(line),
            }

        elif current_game:
            current_game["text"] += " " + line

    if current_game:
        games.append(current_game)

    return games


def create_calendar(games):

    cal = Calendar()

    cal.add("prodid", "-//Basquet Calendar 88834//ES")
    cal.add("version", "2.0")
    cal.add("calscale", "GREGORIAN")
    cal.add("method", "PUBLISH")

    cal.add("x-wr-calname", CALENDAR_NAME)
    cal.add("x-wr-timezone", "Europe/Madrid")

    for game in games:

        dt_start = game["datetime"]
        dt_end = dt_start + timedelta(
            minutes=GAME_DURATION_MINUTES
        )

        description = clean_text(game["text"])

        event = Event()

        event.add(
            "uid",
            make_uid(description)
        )

        event.add(
            "summary",
            f"🏀 {description}"
        )

        event.add(
            "dtstart",
            dt_start
        )

        event.add(
            "dtend",
            dt_end
        )

        event.add(
            "dtstamp",
            datetime.now(timezone.utc)
        )

        event.add(
            "description",
            (
                "Calendari oficial FCBQ\n"
                f"Equip: {TEAM_ID}\n"
                "Font: Bàsquet Català"
            )
        )

        event.add(
            "url",
            f"https://www.basquetcatala.cat/"
            f"partits/calendari_equip_global/pdf/{TEAM_ID}"
        )

        cal.add_component(event)

    Path(OUTPUT_FILE).write_bytes(
        cal.to_ical()
    )


def main():

    if not Path(PDF_FILE).exists():
        raise FileNotFoundError(
            f"No existe {PDF_FILE}"
        )

    lines = extract_lines_from_pdf(PDF_FILE)

    print("\n--- Texto detectado ---\n")

    for line in lines:
        print(line)

    games = parse_games(lines)

    print(
        f"\nPartidos detectados: {len(games)}"
    )

    for game in games:
        print(
            game["datetime"],
            game["text"]
        )

    create_calendar(games)

    print(
        f"\nCalendario generado: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()
