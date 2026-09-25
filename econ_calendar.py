#!/usr/bin/env python3
"""Build an Apple-Calendar-ready .ics feed of USD economic events that move ES / NQ.

Source: Forex Factory weekly calendar JSON (free, no key).
Output: docs/es-nq-econ.ics (served by GitHub Pages).
"""
import hashlib
import json
import os
import urllib.request
from datetime import datetime, timedelta, timezone

FEEDS = [
    "https://nfs.faireconomy.media/ff_calendar_thisweek.json",
    "https://nfs.faireconomy.media/ff_calendar_nextweek.json",  # not always published
]
COUNTRIES = {"USD"}                          # ES / NQ react to US data
IMPACTS = {"High", "Medium", "Holiday"}      # medium + high impact, plus bank holidays
ALERTS_MIN = {"High": [30, 5], "Medium": [5]}  # minutes before the release
EVENT_LEN = timedelta(minutes=15)
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs", "es-nq-econ.ics")
ICON = {"High": "\U0001F534", "Medium": "\U0001F7E0", "Holiday": "\U0001F3E6"}


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "es-nq-econ-calendar/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r)
    except Exception as e:  # next-week feed is often missing; don't fail the run
        print(f"skip {url}: {e}")
        return []


def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def fold(line):
    """RFC 5545: lines max 75 octets."""
    b = line.encode()
    out = []
    while len(b) > 75:
        cut = 75 if not out else 74
        while (b[cut] & 0xC0) == 0x80:  # don't split a UTF-8 char
            cut -= 1
        out.append(b[:cut].decode())
        b = b[cut:]
    out.append(b.decode())
    return "\r\n ".join(out)


def utc(dt):
    return dt.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def build(events):
    lines = [
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//es-nq-econ//EN", "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH", "X-WR-CALNAME:ES/NQ Economic Calendar",
        "X-WR-CALDESC:USD high/medium impact events (Forex Factory)",
        "REFRESH-INTERVAL;VALUE=DURATION:PT1H", "X-PUBLISHED-TTL:PT1H",
    ]
    seen = set()
    for e in sorted(events, key=lambda x: x["date"]):
        if e.get("country") not in COUNTRIES or e.get("impact") not in IMPACTS:
            continue
        start = datetime.fromisoformat(e["date"])
        uid = hashlib.sha1(f'{e["country"]}|{e["title"]}|{e["date"]}'.encode()).hexdigest()
        if uid in seen:
            continue
        seen.add(uid)
        impact = e["impact"]
        title = f'{ICON[impact]} {e["title"]}'
        desc = f"Impact: {impact}"
        if e.get("forecast"):
            desc += f"\nForecast: {e['forecast']}"
        if e.get("previous"):
            desc += f"\nPrevious: {e['previous']}"
        lines += ["BEGIN:VEVENT", f"UID:{uid}@es-nq-econ", f"DTSTAMP:{utc(start)}"]  # stable DTSTAMP: unchanged data = unchanged file
        if impact == "Holiday":
            d = start.date()
            lines += [f"DTSTART;VALUE=DATE:{d:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{d + timedelta(days=1):%Y%m%d}",
                      "TRANSP:TRANSPARENT"]
        else:
            lines += [f"DTSTART:{utc(start)}", f"DTEND:{utc(start + EVENT_LEN)}"]
        lines += [fold(f"SUMMARY:{esc(title)}"), fold(f"DESCRIPTION:{esc(desc)}"),
                  f"CATEGORIES:{impact}"]
        for m in ALERTS_MIN.get(impact, []):
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", fold(f"DESCRIPTION:{esc(title)} in {m} min"),
                      f"TRIGGER:-PT{m}M", "END:VALARM"]
        lines.append("END:VEVENT")
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n", len(seen)


def main():
    events = []
    for url in FEEDS:
        events += fetch(url)
    if not events:
        raise SystemExit("No data fetched - keeping the previous calendar file.")
    ics, n = build(events)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="") as f:
        f.write(ics)
    print(f"wrote {n} events -> {OUT}")


if __name__ == "__main__":
    main()
