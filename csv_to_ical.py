import csv
import sys

from datetime import datetime, timedelta, time
from enum import Enum
from icalendar import Calendar, Event

# Counting saturday
DAYS_IN_WEEK = 6
# Given that week 0 starts on 16 september
VACATION_STARTING_WEEKS = [
    5,  # Toussaint
    14,  # Noël
]
WEEK_COUNT = 16
GROUP_COUNT = 3
START_DATE = datetime(day=16, month=9, year=2024)

DAY_ABBR_MAP = {
    'Lu': 0,  # Monday
    'Ma': 1,  # Tuesday
    'Me': 2,  # Wednesday
    'Je': 3,  # Thursday
    'Ve': 4,  # Friday
}


class StaticGroup(Enum):
    A = "a"
    B = "b"
    C = "c"


class ChangingGroup(Enum):
    G1 = 0
    G2 = 1
    G3 = 2


# The entrypoint of the program
def main():
    colle_group = _get_user_colle_group()
    static_group = _get_static_group(colle_group)

    lesson_plannings = parse_csv_schedule()
    colle_schedule = parse_collometre(colle_group)
    calendar = get_calendar(
            static_group,
            START_DATE,
            lesson_plannings,
            colle_schedule,
            WEEK_COUNT,
    )

    with open("schedule.ics", 'wb') as f:
        f.write(calendar.to_ical())


def _get_user_colle_group():
    if len(sys.argv) >= 2:
        arg = sys.argv[1]
        try:
            group = int(arg)
            if 1 <= group <= 18:
                return group
        except ValueError:
            pass

    user_input = input("Entrez le numéro de votre groupe de colle : ")
    try:
        group = int(user_input)
    except ValueError:
        print("Veuillez entrer un nombre entier entre 1 et 18.")
        exit(1)

    if 1 <= group <= 18:
        return group

    print("Le numéro groupe doit être compris entre 1 et 18 inclus.")
    exit(1)


def _get_static_group(colle_group):
    static_group_list = [
        StaticGroup.A,
        StaticGroup.B,
        StaticGroup.C
    ]
    return static_group_list[(colle_group + 2) % 3]


# Parses the CSV schedules per group and returns a list of plannings per group
def parse_csv_schedule():
    plannings = [None] * GROUP_COUNT

    for groupe_changeant_index in range(GROUP_COUNT):
        planning = [[] for day in range(DAYS_IN_WEEK)]

        # Open and read the CSV file
        with open(
                rf'{groupe_changeant_index}.csv',
                newline='',
                encoding='utf-8'
        ) as csvfile:
            csvreader = csv.reader(csvfile)
            # Ignore the headers
            _ = next(csvreader)

            for row in csvreader:
                for day in range(0, DAYS_IN_WEEK):
                    event = (row[0], row[day + 1])  # (hour, event)
                    planning[day].append(event)

        cleaned_planning = _group_long_subjects(planning)
        plannings[groupe_changeant_index] = cleaned_planning

    return plannings


def parse_collometre(colle_group):
    colles = []

    with open("collometre.csv", newline='', encoding='utf-8') as csvfile:
        reader = csv.reader(csvfile)

        headers = next(reader)
        current_subject = ""

        for row in reader:
            # If the second colum is empty, it's a subject row
            if not row[1]:
                current_subject = row[0].strip()
                continue

            colleur = row[0].strip()
            colle_time = row[1].strip()
            room = row[2].strip()

            day_abbr, time_range = colle_time.split(' ')

            # Determine if the time range uses 'h' format or not and parse
            # accordingly
            if 'h' in time_range:
                start_time_str, end_time_str = time_range.split('-')
                # e.g. 12h15
                start_time = datetime.strptime(start_time_str, '%Hh%M').time()
                end_time = datetime.strptime(end_time_str, '%Hh%M').time()
            else:
                start_time_str, end_time_str = time_range.split('-')
                # e.g. 12
                start_time = datetime.strptime(start_time_str, '%H').time()
                end_time = datetime.strptime(end_time_str, '%H').time()

            # Iterate over the groups (skipping columns 0, 1, and 2)
            for i, group in enumerate(row[3:], 3):
                # Handle multiple groups separated by '+'
                groups = group.split('+') if group else []

                # Check if one of the groups if the targeted colle group
                for g in groups:
                    g_int = int(g)
                    if colle_group == g_int:
                        break
                # If the targeted colle group is not in groups, continue the
                # bigger loop
                else:
                    continue

                current_week = _apply_week_offsets(i - 3)

                # Calculate the actual event date based on the day abbreviation
                if day_abbr in DAY_ABBR_MAP:
                    day_offset = DAY_ABBR_MAP[day_abbr]
                    event_date = START_DATE + timedelta(
                            days=day_offset,
                            weeks=current_week
                    )
                else:
                    continue  # Skip unknown day abbreviations

                colles.append((
                    current_subject,
                    colleur,
                    (event_date, start_time, end_time),
                    room
                ))

    return colles


def get_calendar(
        static_group,
        start_date,
        lesson_plannings,
        colle_planning,
        week_count
):
    calendar = Calendar()

    current_week = 0
    # To take vacation into account
    week_offset = 0

    while current_week < week_count:
        lesson_events = _get_week_events(
                lesson_plannings[
                    # We do not add `week_offset` because vacation don't count in
                    # the changing group pattern
                    _get_changing_group(static_group, current_week)
                ],
                start_date,
                current_week + week_offset,
        )

        for event in lesson_events:
            calendar.add_component(event)

        week_offset += _get_next_week_offset(current_week + week_offset)
        current_week += 1

    colle_events = _get_colle_events(colle_planning)
    for event in colle_events:
        calendar.add_component(event)

    return calendar


def _apply_week_offsets(current):
    current_with_offsets = current

    for starting_vacation_week in sorted(VACATION_STARTING_WEEKS):
        if current_with_offsets >= starting_vacation_week:
            current_with_offsets += 2

    return current_with_offsets


# Gives the actual changing group given the current week
def _get_changing_group(static_group, current_week):
    static_to_changin_group_map = {
        StaticGroup.A: ChangingGroup.G1,
        StaticGroup.B: ChangingGroup.G2,
        StaticGroup.C: ChangingGroup.G3,
    }
    return (static_to_changin_group_map[static_group].value - current_week) % 3


# Returns a list of all current week events
def _get_week_events(planning, start_date, current_week):
    events = []

    for day_index, day_schedule in enumerate(planning):
        event_date = start_date + timedelta(days=day_index, weeks=current_week)

        day_events = _get_day_lessons_events(event_date, day_schedule)

        events += day_events

    return events


# Returns colle events from a colle schedule
def _get_colle_events(colle_schedule):
    events = []

    for colle in colle_schedule:
        # Unpack `colle` object
        subject, colleur, start_end_time, room = colle
        event_date, start_time, end_time = start_end_time

        event = Event()
        event.add('summary', "[Colle] " + subject)
        event.add('dtstart', datetime.combine(event_date, start_time))
        event.add('dtend', datetime.combine(event_date, end_time))
        event.add('dtstamp', datetime.now())

        if room != "":
            event.add('location', room)

        events.append(event)

    return events


# Returns the day's lessons events
def _get_day_lessons_events(event_date, day_schedule):
    events = []

    for start_time, end_time, header in day_schedule:
        # Skip events without a name
        if header:
            # Combine date with time
            start_datetime = datetime.combine(event_date, start_time)
            end_datetime = datetime.combine(event_date, end_time)

            headers = header.split('@')
            summary = headers[0]
            location = headers[1]

            event = Event()
            event.add('summary', summary)
            event.add('dtstart', start_datetime)
            event.add('dtend', end_datetime)
            event.add('location', location)
            event.add('dtstamp', datetime.now())

            events.append(event)

    return events


# Returns 2 if the two next weeks are vacation, else 0
def _get_next_week_offset(current_week):
    if current_week + 1 in VACATION_STARTING_WEEKS:
        return 2

    return 0


# Groups longer lessons in a single event
def _group_long_subjects(planning_brut):
    parsed_planning = [[] for day in range(DAYS_IN_WEEK)]

    for day in range(DAYS_IN_WEEK):
        event_starting_time, current_event = planning_brut[day][0]

        for event in planning_brut[day][1:]:
            if event[1] == current_event:
                continue  # on est dans le meme cours

            event_end_time = _get_end_time(event[0])
            parsed_event = (
                    _format_starting_time(event_starting_time),
                    event_end_time,
                    current_event
            )

            parsed_planning[day].append(parsed_event)

            event_starting_time, current_event = event

        parsed_event = (
                _format_starting_time(event_starting_time),
                _get_end_time("last_hour"),
                current_event
        )
        parsed_planning[day].append(parsed_event)

    return parsed_planning


def _get_end_time(time_str):
    transformation_dict = {
        "08:30": time(8, 30),
        "09:00": time(8, 55),
        "10:15": time(9, 55),
        "11:45": time(11, 45),
        "12:15": time(12, 10),
        "13:15": time(13, 10),
        "13:45": time(13, 45),
        "14:15": time(14, 10),
        "14:45": time(14, 45),
        "15:15": time(15, 10),
        "16:20": time(16, 10),
        "16:50": time(16, 45),
        "17:20": time(17, 15),
        "17:50": time(17, 45),
        "last_hour": time(18, 15)
    }

    return transformation_dict[time_str]


def _format_starting_time(starting_time):
    return datetime.strptime(starting_time, "%H:%M").time()


if __name__ == '__main__':
    main()
