# Given a CSV file in the following format, creates and edits a santa mapping CSV.
#
# Participant list format:
# - Name: Simple name, all in alphanumeric characters. This name uniquely
# - identifies the person.
#
# - Sub-kink preferences (large, blob, etc.) - That person's preference for a given
# - sub-kink. Values for each column are "yes", "no", and "maybe".
#
# - Sub-kinks present in prompt - Whether this person's prompt contains a sub-kink.
# - Labels for this should be something like "yes/optional/no"
#
# - Year columns (2022, 2023, 2024, 2025 S, 2025, 2026 S): Simple name of the person
# - who the given person has created a gift for. For example, having "yuujinf" in
# - 2022 means that the given person made a gift for yuujinf in 2022.
#
# - Forbidden list: Comma-separated list of other participants' simple names
# - that this person
# - cannot pair with.


import csv
import sys
import os
import argparse
import random
from stat import *

# Put None here to generate a new seed every time.
SEED = None

PREV_SANTAS = [
    "2022",
    "2023",
    "2024",
    "S 2025",
    "2025",
    "S 2026",
]

RECENT_SANTAS = [
    "2025",
    "S 2026",
]

SUBKINKS = [
    "Large",
    "Blob",
    "Male",
    "Teen",
    "Furry",
    "Vore",
]

ENCRYPT_NAMES = False
ENCRYPTION_KEY = "obesefatslobnerd67"

SUBKINK_YES = "Yes"
SUBKINK_PREFER_NOT_TO = "Yes, but prefer not to"
SUBKINK_NO = "No"

PROMPT_SUBKINK_YES = "Yes"
PROMPT_SUBKINK_NO = "No"

# If True, only considers the santas in the RECENT_SANTAS list. Otherwise,
# considers all Santas in the PREV_SANTAS list.
RECENT_SANTAS_ONLY = False

FANCY_NAME_HEADER = "Name"
SIMPLE_NAME_HEADER = "Simple Name"
PROMPT_CHAR_HEADER = "Prompt Char"
PROMPT_CHAR_PREFIX = "Prompt "
DONT_PAIR_WITH_HEADER = "Don't Pair With"
SEPARATOR = ", "

# Use this to cap the number of rows to use.
MAX_ROWS = None

# Minimum length of a cycle. A cycle is a chain of participants who each give a
# gift to each other.
MIN_CYCLE_SIZE = 4

# Max score of a 'valid' pairing. A score of 0 means that for every subkink
# present in the prompt, the sender has their preference at "Yes". This score
# increases by 1 for each time the sender has that subkink at "Yes, but prefer not to".
MAX_SCORE = 0

# When editing, you may permit a higher score than normal to allow the algorithm
# to work.
MAX_EDIT_SCORE = 0

participants = {}

participant_names = []


def alphanum_to_number(c):
    if 'a' <= c and c <= 'z':
        return ord(c) - ord('a')
    elif '0' <= c and c <= '9':
        return ord(c) - ord('0') + 26


def number_to_alphanum(n):
    if 0 <= n and n <= 25:
        return chr(n + ord('a'))
    elif 26 <= n and n <= 35:
        return chr(n - 26 + ord('0'))


def encrypt_name(name, length = 30):
    res = ""
    for i in range(length):
        c = name[i % len(name)]
        n = 0
        if 'a' <= c and c < 'z':
            n = ord(c) - ord('a')
        elif '0' <= c and c < '9':
            n = ord(c) - ord('0') + 26

        offset = alphanum_to_number(ENCRYPTION_KEY[i % len(ENCRYPTION_KEY)])
        res += number_to_alphanum((n + offset) % 36)
    return res

# Graphs are Dict[String, Set]

# Returns true if u is adjacent to v
def has_edge(graph, u, v):
    if u in graph:
        return v in graph[u]
    return False


# Adds the edge to the graph if it doesn't exist
def add_edge(graph, u, v):
    if u not in graph:
        graph[u] = set()

    graph[u].add(v)


# Removes an edge from the graph if it exists
def remove_edge(graph, u, v):
    if u not in graph:
        return

    graph[u].remove(v)


# Gets the set of neighbors of a given vertex.
def neighbors(graph, u):
    if u not in graph:
        return set()

    return graph[u]


# Given a graph and a flow network, compute the residual graph for the given flow.
# For each edge in the original graph (u, v):
# - The residual capacity from u to v is c(u, v) - f(u, v).
# - The residual capacity from v to u is c(v, u) - f(v, u).
# In particular in this 0-1 flow network situation,
# - If c(u, v) = 1 and f(u, v) is 0, then the residual capacity is 1.
# - If f(u, v) is 1, then the residual capacity from v to u is also 1.
def residual_network(graph, flow):
    res = {}

    for src in graph.keys():
        for tgt in graph[src]:
            if not has_edge(flow, src, tgt):
                add_edge(res, src, tgt)
            else:
                add_edge(res, tgt, src)

    return res


# Given a residual netowrk and source and target vertices, find a random augmenting
# path through the network.
# This uses a randomized DFS to ensure different results every time.
# Returns None if no path exists. If no path exists, then we have obtained
# a maximum flow.
def random_augmenting_path(residual, s, t):
    visited = {}
    frontier = [(s, None)]

    while len(frontier) > 0:
        (top, parent) = frontier.pop()
        if top in visited:
            continue
        visited[top] = parent

        if top == t:
            path = [top]
            while path[-1] in visited and visited[path[-1]] is not None:
                path.append(visited[path[-1]])
            path.reverse()
            return path

        nbhd = list(neighbors(residual, top))
        nbhd.sort()
        random.shuffle(nbhd)

        for nbor in nbhd:
            frontier.append((nbor, top))


    return None


# Runs the Ford Fulkerson algorithm to find the maximum flow through the graph.
# Ford Fulkerson starts with an empty flow network and repeatedly adds augmenting
# paths to the network, which increase the flow each time. Because this is an
# integral flow and max flow is always bounded, this algorithm will always halt.
def random_ford_fulkerson(graph, s, t):
    flow = {}

    while True:
        residual = residual_network(graph, flow)
        path = random_augmenting_path(residual, s, t)

        if path is None:
            return flow


        for i in range(len(path)-1):
            u, v = path[i], path[i+1]

            # Add flow from s to t...
            if not has_edge(flow, u, v):
                add_edge(flow, u, v)

            # and remove flow from t to s
            if has_edge(flow, v, u):
                remove_edge(flow, v, u)


    return None


# Uses randomized Ford Fulkerson to create a derangement of the given
# list of participants.
def flow_derangement(part_names):
    graph = {}

    for part in part_names:
        add_edge(graph, "_SOURCE_", f"{part}_snd")
        add_edge(graph, f"{part}_rec", "_SINK_")
        
        for other_part in part_names:
            if part == other_part:
                continue

            score = pairing_score(part, other_part)
            if score is not None and score <= MAX_SCORE:
                add_edge(graph, f"{part}_snd", f"{other_part}_rec")

    flow = random_ford_fulkerson(graph, "_SOURCE_", "_SINK_")
    if len(neighbors(flow, "_SOURCE_")) != len(part_names):
        return None

    assign = {}

    for part in part_names:
        other_part = next(iter(flow[f"{part}_snd"])).split("_")[0]
        assign[part] = other_part

    return assign


# Given an old assignment and a list of senders to replace,
# attempts to reassign the senders. Each sender's corresponding recipient
# is extracted, and then all the senders and recipients are re-paired with
# each other.
#
# This method may fail in certain scenarios. You may add or remove people
# from the group to get it to work
def edit_assignment(old_assign, senders, recipients):
    graph = {}

    if len(senders) != len(recipients):
        print("Senders and recipients must be 1-to-1")
        return None

    for snd in senders:
        add_edge(graph, "_SOURCE_", f"{snd}_snd")
        
        for rec in recipients:
            if snd == rec:
                continue

            if (snd in old_assign and rec == old_assign[snd]):
                continue

            if snd != rec and \
                    (snd not in old_assign or rec != old_assign[snd]) and \
                    pairing_score(snd, rec) == 0:
                add_edge(graph, f"{snd}_snd", f"{rec}_rec")

    for rec in recipients:
        add_edge(graph, f"{rec}_rec", "_SINK_")

    flow = random_ford_fulkerson(graph, "_SOURCE_", "_SINK_")
    if len(neighbors(flow, "_SOURCE_")) != len(senders):
        return None

    assign = old_assign.copy()

    for sender in senders:
        other_part = next(iter(flow[f"{sender}_snd"])).split("_")[0]
        if sender in old_assign:
            print(f"reassigning {sender} from {old_assign[sender]} to {other_part}")
        else:
            print(f"assigning {sender} to {other_part}")
        assign[sender] = other_part

    return assign


# Produces a derangement with a total score of zero.
def zero_score_derangement(part_names):
    attempts = 0
    while True:
        attempts += 1
        curr_arr = flow_derangement(part_names)
        if curr_arr is None:
            print("Impossible!")
            return None
        score = assignment_score(curr_arr)
        if score == 0:
            print(f"finished in {attempts} attempts")
            return curr_arr


def zero_score_edit(old_assign, senders, recipients):
    attempts = 0
    while True:
        attempts += 1
        new_assign = edit_assignment(old_assign, senders, recipients)
        if new_assign is None:
            print("Edit impossible")
            return None

        score = assignment_score(new_assign)
        if score == 0:
            print(f"finished in {attempts} attempts")
            return new_assign
        print("edit failed")


# Returns whether or not the sender (identified by their simple name)
# may give a gift to their recipient, subject to the following conditions:
# - The sender cannot give a gift to someone they have already given
#   a gift to in a previous Santa. If 'RECENT_SANTAS_ONLY' is true, then
#   we only consider the previous two Santas (ASS 2025, SASS 2026).
# - If the 
#
# This will return None if this pairing is completely forbidden, and otherwise
# returns an integer score. This score increases by 1 for each subkink (SUBKINKS)
# the sender would prefer not to draw that is present inside the recipient's prompt.
def pairing_score(snd, rec, debug=False):
    snd_entry = participants[snd]
    rec_entry = participants[rec]

    # If the sender has already given a gift to recipient before,
    # or if the recipient is in the sender's forbidden list,
    # return None
    for santa in snd_entry["prev_santas"].keys():
        if RECENT_SANTAS_ONLY and santa not in RECENT_SANTAS:
            continue

        if rec in snd_entry["prev_santas"][santa]:
            if debug:
                print(f"{snd} already gave a gift to {rec} in {santa}")
            return None

    if rec in snd_entry["forbidden_list"]:
        if debug:
            print(f"{snd} will not give a gift to {rec}")
        return None

    score = 0
    for sub_kink in SUBKINKS:
        # If recipient's prompt has a given subkink (it's marked as 'Yes')
        # then three cases:
        # if sender says Yes, do nothing
        # if sender is a prefer not to, increase score by 1
        # if sender is a No, return None
        if rec_entry["prompt_kinks"][sub_kink] == PROMPT_SUBKINK_YES:
            if snd_entry["sub_kinks"][sub_kink] == SUBKINK_PREFER_NOT_TO:
                score += 1
                if debug:
                    print(f"{rec}'s prompt has {sub_kink} and {snd} would prefer not to draw it")
            elif snd_entry["sub_kinks"][sub_kink] == SUBKINK_NO:
                if debug:
                    print(f"{rec}'s prompt has {sub_kink} and {snd} will not draw it")
                return None

    return score


def assignment_score(assign, debug=False):
    # If there is a cycle of length less than MIN_CYCLE_SIZE,
    # return None
    part_set = set()

    for participant in participant_names:
        if participant in part_set:
            continue

        part_set.add(participant)
        curr = assign[participant]
        part_set.add(curr)
        cycle_len = 1
        while curr != participant:
            curr = assign[curr]
            part_set.add(curr)
            cycle_len += 1

        if cycle_len < MIN_CYCLE_SIZE:
            return None

    total_score = 0
    for snd, rec in assign.items():
        sub_score = pairing_score(snd, rec, debug)
        if sub_score is None:
            return None
        else:
            total_score += sub_score

    return total_score


def verify_assign(assign):
    part_set = set()

    bad_snds = set()
    bad_recs = set()

    for participant in assign.keys():
        if participant in part_set:
            continue

        part_set.add(participant)
        curr = assign[participant]
        part_set.add(curr)
        cycle_len = 1

        cycle_set = set()
        cycle_set.add(curr)
        is_cycle = True
        while curr != participant:
            if curr not in assign:
                is_cycle = False
                break
            curr = assign[curr]
            part_set.add(curr)
            cycle_set.add(curr)
            cycle_len += 1

        if is_cycle and cycle_len < MIN_CYCLE_SIZE:
            print(f"Short cycle found: {cycle_set}")
            for p in cycle_set:
                bad_snds.add(p)
                bad_recs.add(p)

    for snd, rec in assign.items():
        if snd not in participant_names:
            print(f"{rec} is receiving a gift from an unknown/missing sender {snd}")
            bad_recs.add(rec)
            continue

        if rec not in participant_names:
            print(f"{snd} is sending a gift to an unknown/missing recipient {rec}")
            bad_snds.add(snd)
            continue

        sub_score = pairing_score(snd, rec, True)
        if sub_score is None or sub_score > MAX_SCORE:
            print(f"{snd} should not send a gift to {rec}")
            bad_snds.add(snd)
            bad_recs.add(rec)

    snd_set = set(assign.keys())
    rec_set = set(assign.values())

    for participant in participant_names:
        if participant not in snd_set:
            print(f"{participant} is not sending a gift")
            bad_snds.add(participant)

        if participant not in rec_set:
            print(f"{participant} is not receiving a gift")
            bad_recs.add(participant)

    if len(bad_snds) == 0 and len(bad_recs) == 0:
        print("No errors.")
        return (bad_snds, bad_recs)

    if len(bad_snds) != len(bad_recs):
        print("Somehow, there's an imbalance in invalid senders/recipients. You need to generate a new assignment or fix the error")
        return None

    return (bad_snds, bad_recs)


def print_assignment(assign):
    for snd, rec in assign.items():
        sn = snd
        rc = rec
        if ENCRYPT_NAMES:
            sn = encrypt_name(snd)
            rc = encrypt_name(rec)
        print(f"{sn:>30} > {rc}")


def save_assignment(path, assign):
    with open(path, 'w', newline='', encoding="utf8") as file:
        fieldnames = ['Sender', 'Recipient']
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        senders = list(assign.keys())
        senders.sort()
        for snd in senders:
            writer.writerow({
                'Sender': snd,
                'Recipient': assign[snd],
            })


def load_assignment(path):
    assign = {}
    recs = set()
    with open(path, newline='', encoding="utf8") as file:
        reader = csv.DictReader(file)
        for i, row in enumerate(reader):
            if row["Sender"] not in participants:
                print(f"Unknown sender '{row["Sender"]}'")
                continue

            if row["Recipient"] not in participants:
                print(f"Unknown recipient '{row["Recipient"]}'")
                continue

            if row["Sender"] in assign:
                print(f"{row["Sender"]} is giving multiple gifts: assignment is invalid")
                return (None, None)

            assign[row["Sender"]] = row["Recipient"]
            
            if row["Recipient"] in recs:
                print(f"{row["Recipient"]} is receiving multiple gifts: assignment is invalid")
                return (None, None)
            recs.add(row["Recipient"])

    verification = verify_assign(assign)

    return (assign, verification)


def print_table(tbl):
    column_widths = [0, 0]
    for row in tbl:
        for i, cell in enumerate(row):
            column_widths[i] = max(column_widths[i], len(cell))


    for row in tbl:
        print("\t".join(c.ljust(column_widths[i]) for i, c in enumerate(row)))


if __name__ == "__main__":
    random.seed(SEED)

    parser = argparse.ArgumentParser(
                    prog='Santa Shuffler',
                    description='Shuffler algorithm for a Secret Santa')

    parser.add_argument('participant_csv')
    args = parser.parse_args()

    with open(args.participant_csv, newline='', encoding="utf8") as file:
        reader = csv.DictReader(file)
        for i, row in enumerate(reader):
            if (MAX_ROWS is not None) and i >= MAX_ROWS:
                break

            entry = {
                "fancy_name": row[FANCY_NAME_HEADER],
                "simple_name": row[SIMPLE_NAME_HEADER],
                "prev_santas": {},
                "sub_kinks": {},
                "prompt_char": row[PROMPT_CHAR_HEADER],
                "prompt_kinks": {},
                "forbidden_list": [],
            }

            if row[DONT_PAIR_WITH_HEADER] != "":
                entry["forbidden_list"] = row[DONT_PAIR_WITH_HEADER].split(SEPARATOR)

            for prev_santa in PREV_SANTAS:
                if row[prev_santa] != "":
                    prev_recipients = row[prev_santa].split(", ")
                    entry["prev_santas"][prev_santa] = prev_recipients

            for j, sub_kink in enumerate(SUBKINKS):
                entry["sub_kinks"][sub_kink] = row[sub_kink]
                entry["prompt_kinks"][sub_kink] = row[f"{PROMPT_CHAR_PREFIX}{sub_kink}"]


            participants[entry["simple_name"]] = entry

    participant_names = list(participants.keys())

    part_set = set(participants.keys())
    excluded_set = set()
    for part_name, part in participants.items():
        for santa in part["prev_santas"].values():
            for other_part in santa:
                if other_part not in part_set:
                    excluded_set.add(other_part)

    if len(excluded_set) != 0:
        print("The following simple names are not in the participant list. This means they either participated in a past event and are not returning this year, or some data was inserted incorrectly. Check over this list carefully for any inconsistencies.")
        ls = sorted(list(excluded_set))
        for name in ls:
            print(name)

    sortedParts = sorted(participant_names)

    participant_names = sortedParts

    print("Write 'help' to get the list of commands.")

    current_assignment = None
    receive_map = None

    mode = None

    edit_target_snds = set()
    edit_target_recs = set()

    invalid_snds = set()
    invalid_recs = set()

    staging_edit = None

    while True:
        prompt = "next command: "
        if mode == "edit":
            prompt = "next_command (edit): "

        command = input(prompt).split()
        
        if command[0] == "help":
            print_table([
                ["help", "Print this help screen"],

                ["load_assign (path)", "Loads the assignment csv file located at the given path"],
                ["save_assign(path)", "Saves the assignment csv file to the given path"],
                ["participants", "Print list of participants"],
                ["info (participant)", "Print the participant, their gift recipient, and their gift sender"],
                ["make_assign", "Generate a new santa assignment"],
                ["edit", "Enter 'edit mode', where you can stage and prepare an edit"],
                ["show_assign", "Show the current santa assignment"],
                ["exit", "Closes the script"],
            ])

            print("\nEdit mode:")
            print_table([
                ["add (part_1) (part_2) ...", "Mark each participant for editing"],
                ["rem (part_1) (part_2) ...", "Unmark each participant for editing"],
                ["show_edit", "Show all participants who have been marked for editing"],
                ["cancel", "Cancels the edit"],
                ["make_edit", "Initiates the edit. Fails if the list of participants to edit is empty."],
                ["commit", "Saves the edit. Must create an edit first with make_edit command."],
            ])

        elif command[0] == "exit":
            break

        elif command[0] == "participants":
            for part in participant_names:
                print(part)

        elif command[0] == "load_assign":
            path = None
            if len(command[1:]) == 0:
                path = input("Please provide a path (leave blank to load 'output.csv'): ").strip()
            else:
                path = command[1]

            if path == "":
                path = "output.csv"

            resp = input(f"Load path {path}? (Y/n) ").strip().lower()
            if resp == "" or resp[0] == "y":
                current_assignment, v = load_assignment(path)

                if current_assignment is None or v is None:
                    print("Assignment is invalid")
                    continue

                invalid_snds, invalid_recs = v 
            else:
                continue

        elif command[0] == "save_assign":
            if current_assignment is None:
                print("No assignment loaded (generate one with 'make_assign')")
                continue

            path = None
            if len(command[1:]) == 0:
                path = input("Please provide a path (leave blank to save to 'output.csv'): ").strip()
            else:
                path = command[1]

            if path == "":
                path = "output.csv"

            resp = input(f"Save to path {path}? (Y/n) ").strip().lower()
            if resp == "" or resp[0] == "y":
                save_assignment(path, current_assignment)
            else:
                continue

        elif command[0] == "info":
            if len(command[1:]) == 0:
                print("Must provide at least one participant")
                continue

            for part in command[1:]:
                if part not in participants:
                   print(f"Participant '{part}' not found")
                   continue

                part_entry = participants[part]
                print(f"{part_entry["fancy_name"]} ({part_entry["simple_name"]})")

                if current_assignment:
                    print(f"Giving a gift to {current_assignment[part]}")
                    print(f"Receiving a gift from {receive_map[part]}")

                print("")
                for santa_name, santees in part_entry["prev_santas"].items():
                    print(f"{santa_name}:\t{SEPARATOR.join(santees)}")

                print("")
                for sub_kink in SUBKINKS:
                    print(f"{sub_kink}:\t{part_entry["sub_kinks"][sub_kink]}")

                print("")
                for sub_kink in SUBKINKS:
                    print(f"Prompt {sub_kink}:\t{part_entry["prompt_kinks"][sub_kink]}")

                print("")
                print(f"Forbidden Recipients: {SEPARATOR.join(part_entry["forbidden_list"])}")
                print("")

        elif command[0] == "make_assign":
            current_assignment = zero_score_derangement(participant_names)
            receive_map = {}
            for snd, rec in current_assignment.items():
                receive_map[rec] = snd

        elif command[0] == "show_assign":
            if current_assignment is None:
                print("No assignment loaded (generate one with 'make_assign')")
                continue

            print_assignment(current_assignment)

        elif command[0] == "edit":
            if current_assignment == None:
                print("No assignment loaded")
                continue

            mode = "edit"
            edit_target_snds = set()
            edit_target_recs = set()

        elif mode == "edit" and command[0] == "add":
            if len(command[1:]) == 0:
                print("Must specify at least one participant")

            staging_edit = set()
            for part in command[1:]:
                if part not in participants:
                    print(f"Participant '{part}' not found")
                    continue

                if part in invalid_snds:
                    print(f"{part} already marked as invalid")
                    continue

                rec = current_assignment[part]

                if rec in invalid_recs:
                    print(f"{rec} already marked as invalid")
                    continue

                edit_target_snds.add(part)
                edit_target_recs.add(rec)
                print(f"Added pairing '{part} > {current_assignment[part]}' for editing")


        elif mode == "edit" and command[0] == "add_random":
            if len(command[1:]) >= 1 and not command[1].isdigit():
                print("Invalid count")
                continue
            
            count = None
            if len(command[1:]) == 0:
                count = 1
            else:
                count = int(command[1])

            valid_parts = []
            for p in participant_names:
                if p in edit_target_snds or p in invalid_snds:
                    continue

                if p in current_assignment:
                    rec = current_assignment[p]
                    if rec in edit_target_recs or rec in invalid_recs:
                        continue
                else:
                    continue
                valid_parts.append(p)

            if count > len(valid_parts):
                print("Attempted to add more participants than is possible")
                continue

            samp = random.sample(valid_parts, count)
            for s in samp:
                edit_target_snds.add(s)
                edit_target_recs.add(current_assignment[s])
                print(f"Added pairing '{s} > {current_assignment[s]}' for editing")

        elif mode == "edit" and command[0] == "rem":
            if len(command[1:]) == 0:
                print("Must specify at least one participant")

            staging_edit = set()
            for part in command[1:]:
                if part not in participants:
                    print(f"Participant '{part}' not found")
                    continue

                if part not in edit_target_snds:
                    print(f"Participant {part} not designated for editing")
                    continue

                rec = current_assignment[part]
                edit_target_snds.remove(part)
                edit_target_recs.remove(rec)
                print(f"Removed pairing '{part} > {current_assignment[part]}' for editing")
            pass

        elif mode == "edit" and command[0] == "show_edit":
            print("The following participants are selected for editing:")
            snds, recs = list(edit_target_snds.union(invalid_snds)), list(edit_target_recs.union(invalid_recs))
            snds.sort()
            recs.sort()
            tbl = [[snds[i], recs[i]] for i in range(len(snds))]

            tbl.insert(0, ["Senders", "Recipients"])
            print_table(tbl)


        elif mode == "edit" and command[0] == "cancel":
            mode = None
            pass

        elif mode == "edit" and command[0] == "make_edit":
            snds = list(edit_target_snds.union(invalid_snds))
            recs = list(edit_target_recs.union(invalid_recs))

            if len(snds) == 0 or len(recs) == 0:
                print("No edit targets")
                continue

            staging_edit = zero_score_edit(current_assignment, snds, recs)
            if staging_edit is None:
                print("Making an edit with the currently selected participants is impossible. Please add or remove additional participants to make the edit possible.")
            else:
                print("Created staging edit.")

        elif mode == "edit" and command[0] == "commit":
            if staging_edit is None:
                print("No currently staged edit.")
                continue
            
            current_assignment = staging_edit
            receive_map = {}
            for snd, rec in current_assignment.items():
                receive_map[rec] = snd
            print("Committed staged edit.")
            mode = None

        else:
            print("Unrecognized command")
