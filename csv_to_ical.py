from enum import Enum
import csv
import sys
from datetime import datetime, timedelta, time
from icalendar import Calendar, Event
from collections import defaultdict

DAYS_IN_WEEK = 6  # Si on inclu samedi
# Sachant que la semaine 0 est la semaine du 16/09
VACATION_STARTING_WEEKS = [
        5,  # Toussaint
        14,  # Noël
]


class Groupe_Statique(Enum):
    G_A = "a"
    G_B = "b"
    G_C = "c"


class Groupe_Changeant(Enum):
    G_1 = 0
    G_2 = 1
    G_3 = 2


class Parser():
    def __init__(self):
        # Map of French day abbreviations to day offsets
        self.DAY_MAP = {
            'Lu': 0,  # Monday
            'Ma': 1,  # Tuesday
            'Me': 2,  # Wednesday
            'Je': 3,  # Thursday
            'Ve': 4,  # Friday
        }


        self.plannings = [None, None, None]
        self.colles_planning = None

        self.load_plannings()
        self.load_and_parse_colles()

        print(self.colles_planning)





    def get_planning_by_group(self, group_changeant):
        return self.plannings[group_changeant.value]

    def get_colle(self, date, groupe_id):
        str_date = date.strftime('%d/%m')
        return self.colles_planning.get((str_date, groupe_id), None)

    def load_plannings(self):
        for groupe_changeant_index in range(3):
            planning = [[] for day in range(DAYS_IN_WEEK)]  # planning[day] -> day[event]

            # Open and read the CSV file
            with open(rf'{groupe_changeant_index}.csv', newline='', encoding='utf-8') as csvfile:
                csvreader = csv.reader(csvfile)  # Create a reader object
                header = next(csvreader)   # Get the header (first row)

                # Iterate through the rows
                for row in csvreader:
                    for day in range(0, DAYS_IN_WEEK):
                        event = (row[0], row[day + 1])  # hour, event
                        planning[day].append(event)

            parsed_planning = self.planning_parser(planning)  # on veut enlever les répétitions
            self.plannings[groupe_changeant_index] = parsed_planning

    def load_and_parse_colles(self):
        # POSSIBILITE D'ERREUR SI UN GROUPE A 2 COLLES LE MEME JOUR (pas le cas pour l'instant)
        data = defaultdict(tuple)  # Structure: {(date, group_id): (subject, colleur, horaire, salle)}

        with open("collometre.csv", newline='', encoding='utf-8') as csvfile:
            reader = csv.reader(csvfile)
            headers = next(reader)  # First line contains the dates (week start dates)
            subjects = None  # Keep track of the current subject

            for row in reader:
                if not row[1]:  # If the second column is empty, it's a subject row
                    subjects = row[0].strip()  # Set the subject (Mathématiques, Informatique, etc.)
                    continue

                colleur = row[0].strip()  # The name of the colleur
                horaire = row[1].strip()  # The schedule (e.g., Lu 12-13)
                salle = row[2].strip()    # The exam room

                # Extract the day abbreviation (e.g., 'Lu') and time range (e.g., '12-13')
                day_abbr, time_range = horaire.split(' ')

                # Determine if the time range uses 'h' format or not and parse accordingly
                if 'h' in time_range:
                    start_time_str, end_time_str = time_range.split('-')
                    start_time = datetime.strptime(start_time_str, '%Hh%M').time()  # e.g., 12h15
                    end_time = datetime.strptime(end_time_str, '%Hh%M').time()  # e.g., 13h15
                else:
                    start_time_str, end_time_str = time_range.split('-')
                    start_time = datetime.strptime(start_time_str, '%H').time()  # e.g., 12
                    end_time = datetime.strptime(end_time_str, '%H').time()  # e.g., 13

                for i, group in enumerate(row[3:], 3):  # Iterate over the groups (skipping columns 0, 1, and 2)
                    week_start_str = headers[i].strip()  # Get the corresponding week start date from the headers

                    try:
                        # Parse the week start date (e.g., '16/09') into a datetime object
                        week_start_date = datetime.strptime(week_start_str, '%d/%m')
                    except ValueError:
                        continue  # Skip if the date is invalid

                    # Calculate the actual event date based on the day abbreviation
                    if day_abbr in self.DAY_MAP:
                        day_offset = self.DAY_MAP[day_abbr]
                        event_date = week_start_date + timedelta(days=day_offset)
                        event_date_str = event_date.strftime('%d/%m')
                    else:
                        continue  # Skip unknown day abbreviations

                    groups = group.split('+') if group else []  # Handle multiple groups separated by '+'

                    # Add the data to the subject entry in the dictionary
                    for g in groups:
                        g_id = int(g)  # Convert group ID to integer for sorting
                        # Append the subject, colleur, start and end time, and salle
                        data[(event_date_str, g_id)] = (subjects, colleur, (start_time,end_time), salle)

        self.colles_planning = data

    def planning_parser(self, planning_brut):
        parsed_planning = [[] for day in range(DAYS_IN_WEEK)]

        for day in range(DAYS_IN_WEEK):
            event_starting_time, current_event = planning_brut[day][0]

            for event in planning_brut[day][1:]:
                if event[1] == current_event:
                    continue  # on est dans le meme cours

                event_end_time = self.get_end_time(event[0])
                parsed_event = self.format_starting_time(event_starting_time), event_end_time, current_event

                parsed_planning[day].append(parsed_event)

                event_starting_time, current_event = event

            parsed_event = self.format_starting_time(event_starting_time), self.get_end_time("last_hour"), current_event
            parsed_planning[day].append(parsed_event)

        return parsed_planning

    def get_end_time(self, next_event_starting_time):
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

        return transformation_dict[next_event_starting_time]

    def format_starting_time(self, starting_time):
        return datetime.strptime(starting_time, "%H:%M").time()


class Manager():
    def __init__(self, groupe_statique_personnel, group_colle):
        self.groupe_statique = groupe_statique_personnel
        self.groupe_changeant = self.get_starting_changing_group(groupe_statique_personnel)
        self.group_colle_id = group_colle

        self.current_week = 0
        self.this_week_planning = PLANNINGS.get_planning_by_group(self.groupe_changeant)

        self.calendar = Calendar()
        self.start_date = datetime(day=16, month=9, year=2024)

    def compute_week(self):
        self.add_week_to_calendar()
        self.next_week()

    def get_starting_changing_group(self, personnal_group):
        starting_week_groupes = {
            Groupe_Statique.G_A: Groupe_Changeant.G_1,
            Groupe_Statique.G_B: Groupe_Changeant.G_2,
            Groupe_Statique.G_C: Groupe_Changeant.G_3,
        }
        return starting_week_groupes[personnal_group]

    def next_week(self):
        new_group_id = (self.groupe_changeant.value - 1) % 3
        self.groupe_changeant = Groupe_Changeant(new_group_id)

        self.this_week_planning = PLANNINGS.get_planning_by_group(self.groupe_changeant)
        
        self.current_week += 1
        if self.current_week in VACATION_STARTING_WEEKS:
            self.current_week += 2

    def add_week_to_calendar(self):
        for day_index, day_schedule in enumerate(self.this_week_planning):
            event_date = self.start_date + timedelta(days=day_index, weeks=self.current_week)

            #Add colle
            if colle_event_object:= PLANNINGS.get_colle(event_date, self.group_colle_id):
                #colle_event_object = (subject, colleur, horaire, salle)
                matiere, colleur, horaire, salle = colle_event_object

                #ToDO add colleur

                # Create an event
                event = Event()
                event.add('summary', "COLLE " + matiere)
                event.add('dtstart', datetime.combine(event_date, horaire[0]))
                event.add('dtend', datetime.combine(event_date, horaire[1]))
                event.add('location', salle)
                event.add('dtstamp', datetime.now())

                # Add the event to the calendar
                self.calendar.add_component(event)

            for start_time, end_time, header in day_schedule:
                if header:  # Skip events without a name
                    # Combine date with time
                    start_datetime = datetime.combine(event_date, start_time)
                    end_datetime = datetime.combine(event_date, end_time)

                    headers = header.split('@')
                    summary = headers[0]
                    location = headers[1]

                    # Create an event
                    event = Event()
                    event.add('summary', summary)
                    event.add('dtstart', start_datetime)
                    event.add('dtend', end_datetime)
                    event.add('location', location)
                    event.add('dtstamp', datetime.now())

                    # Add the event to the calendar
                    self.calendar.add_component(event)

    def save_calendar(self):
        # Save the calendar to an .ics file
        with open('schedule.ics', 'wb') as f:
            f.write(self.calendar.to_ical())


def get_static_group(s):
    if s in ["a", "A"]:
        print("Génération du calendrier pour le groupe A...")
        return Groupe_Statique.G_A
    elif s in ["b", "B"]:
        print("Génération du calendrier pour le groupe B...")
        return Groupe_Statique.G_B
    elif s in ["c", "C"]:
        print("Génération du calendrier pour le groupe C...")
        return Groupe_Statique.G_C
    else:
        print("Groupe incorrect. Valeurs possibles : A, B ou C")
        exit(1)


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    PLANNINGS = Parser()

    static_group = Groupe_Statique.G_A
    if len(sys.argv) >= 2:
        static_group = get_static_group(sys.argv[1])
    else:
        g = input("Veuillez indiquer votre groupe: ")
        static_group = get_static_group(g)

    w = Manager(Groupe_Statique.G_A, 10)

    for week_number in range(16):
        w.compute_week()
    w.save_calendar()
