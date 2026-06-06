#!/usr/bin/env python3
"""
dataset_english_large.md
========================
Generates ~12 000 balanced English rows for civic_intent_dataset.csv:
  - report   ~3 000  (NYC 311-derived templates, stratified by civic category)
  - question ~3 000  (civic Q&A templates, 9 categories)
  - human    ~3 000  (escalation / want-to-speak templates)
  - spam     ~3 000  (Enron corpus + synthetic scam/ad templates)

Usage:
    python3 build_dataset.md           # rebuild base CSV first
    python3 dataset_english_large.md   # append English expansion
    python3 dataset_english.md         # optionally top up from live sources

Split: deterministic SHA-1 on text (~20% test, ~80% train). No data leakage.
"""

import csv
import hashlib
import itertools
import random
from pathlib import Path

CSV_PATH = Path("civic_intent_dataset.csv")
RNG = random.Random(42)           # seeded for reproducibility

# ── Helpers ───────────────────────────────────────────────────────────────

def sha1_split(text: str) -> str:
    h = int(hashlib.sha1(text.encode("utf-8")).hexdigest(), 16)
    return "test" if h % 5 == 0 else "train"

def row(text, intent, category):
    return {
        "id": f"en-en-large",          # placeholder; renumbered on write
        "text": text,
        "lang": "en",
        "variety": "en",
        "intent": intent,
        "category": category,
        "split": sha1_split(text),
    }

def pick(*items):
    return RNG.choice(items)

def maybe(text, probability=0.5):
    return text if RNG.random() < probability else ""

# ── Shared variation pools ─────────────────────────────────────────────────

STREETS = [
    "Main Street", "Oak Avenue", "Cedar Road", "Elm Street", "Maple Drive",
    "Pine Street", "River Road", "Park Avenue", "Hill Road", "Valley Lane",
    "Church Street", "School Road", "Lake Drive", "Green Street", "Bay Road",
    "Market Street", "Station Road", "Mill Lane", "Forest Avenue", "Spring Street",
    "Lincoln Avenue", "Washington Boulevard", "Jefferson Road", "Adams Street",
    "Monroe Drive", "Sunset Boulevard", "Harbor Road", "Garden Path", "Court Street",
    "Bridge Road", "Canal Street", "Prospect Avenue", "Highland Drive", "Broad Street",
]

LOCATIONS = [
    "in front of my building", "near the intersection", "at the end of the block",
    "outside the school", "near the park", "by the shopping center", "at the corner",
    "opposite the mosque", "next to the pharmacy", "outside the municipal building",
    "near the hospital", "by the bus stop", "at the main junction", "near the market",
    "outside the community center", "by the old fountain", "near the traffic lights",
    "in the residential area", "close to the sports field", "near the playground",
]

DURATIONS = [
    "since yesterday", "for three days now", "for over a week",
    "since last Monday", "for two weeks", "since the last rain",
    "since this morning", "for several days", "since last weekend",
    "for more than a week", "since the storm", "since last month",
    "for days", "for a while now", "since Tuesday",
]

URGENCY = [
    "This is urgent.", "Please send someone as soon as possible.",
    "This needs immediate attention.", "I've been waiting for a response.",
    "This is a safety hazard.", "Please fix this promptly.",
    "This has been ignored for too long.", "Residents are very frustrated.",
    "Please prioritize this.", "This is affecting many residents.",
    "", "", "",   # sometimes no urgency tag
]

# ── REPORT templates (~3 000 rows, stratified) ────────────────────────────

def gen_report_roads() -> list[dict]:
    rows = []
    templates = [
        lambda: f"There is a large pothole on {pick(*STREETS)} {pick(*LOCATIONS)}. {pick(*DURATIONS).capitalize()}. {pick(*URGENCY)}",
        lambda: f"The road surface on {pick(*STREETS)} is severely damaged and needs immediate repair. {pick(*URGENCY)}",
        lambda: f"A traffic signal {pick(*LOCATIONS)} has been broken {pick(*DURATIONS)}. Cars are ignoring it and it's dangerous.",
        lambda: f"There is a traffic light malfunction at the junction of {pick(*STREETS)} and {pick(*STREETS)}. {pick(*URGENCY)}",
        lambda: f"Someone has been parked illegally blocking {pick(*LOCATIONS)} on {pick(*STREETS)} {pick(*DURATIONS)}.",
        lambda: f"An abandoned vehicle has been sitting on {pick(*STREETS)} {pick(*durations)} and nobody has removed it. {pick(*URGENCY)}",
        lambda: f"There is a derelict car blocking part of the road on {pick(*STREETS)}. {pick(*URGENCY)}",
        lambda: f"The road on {pick(*STREETS)} is flooded and vehicles cannot pass after the rain.",
        lambda: f"A large tree branch fell on {pick(*STREETS)} and is blocking traffic. Please clear it.",
        lambda: f"The sidewalk on {pick(*STREETS)} has completely collapsed near {pick(*LOCATIONS)}. {pick(*URGENCY)}",
        lambda: f"Street lighting on {pick(*STREETS)} has been out {pick(*DURATIONS)}. The area is very dark at night.",
        lambda: f"Several streetlights {pick(*LOCATIONS)} are not working. This is a safety concern for pedestrians.",
        lambda: f"The road markings on {pick(*STREETS)} have faded completely and are causing confusion.",
        lambda: f"A section of the road on {pick(*STREETS)} has caved in. {pick(*URGENCY)}",
        lambda: f"I want to report a blocked driveway {pick(*LOCATIONS)} on {pick(*STREETS)}. I cannot access my property.",
        lambda: f"There is a car parked across my driveway entrance on {pick(*STREETS)} {pick(*DURATIONS)}.",
        lambda: f"The guardrail on {pick(*STREETS)} is broken and poses a serious risk to drivers.",
        lambda: f"A manhole cover on {pick(*STREETS)} is broken and creates a hazard for vehicles and pedestrians.",
        lambda: f"The road divider on {pick(*STREETS)} is damaged and needs urgent repair.",
        lambda: f"Vehicles are parking on the pavement on {pick(*STREETS)}, making it impossible for pedestrians to pass.",
        lambda: f"There is serious road damage {pick(*LOCATIONS)} caused by heavy vehicles. {pick(*URGENCY)}",
        lambda: f"The speed bump on {pick(*STREETS)} is completely worn away. Vehicles are speeding through.",
        lambda: f"Road works on {pick(*STREETS)} were abandoned mid-way and the area is now dangerous.",
        lambda: f"I'd like to report potholes on {pick(*STREETS)} that are getting worse. {pick(*URGENCY)}",
        lambda: f"The traffic signal {pick(*LOCATIONS)} is stuck on red and causing a major backup.",
        lambda: f"There is a broken traffic sign on {pick(*STREETS)} — the sign is lying on the pavement.",
        lambda: f"A lamppost on {pick(*STREETS)} is tilting dangerously and could fall.",
        lambda: f"Road flooding on {pick(*STREETS)} is making it dangerous for motorbikes and cyclists.",
    ]
    durations = DURATIONS  # closure
    for _ in range(750):
        t = pick(*templates)
        rows.append(row(t().strip(), "report", "roads"))
    return rows

def gen_report_water() -> list[dict]:
    rows = []
    templates = [
        lambda: f"There has been no water supply in our building on {pick(*STREETS)} {pick(*DURATIONS)}. {pick(*URGENCY)}",
        lambda: f"Water pressure in our area has dropped dramatically {pick(*DURATIONS)}. {pick(*URGENCY)}",
        lambda: f"A water pipe has burst {pick(*LOCATIONS)} on {pick(*STREETS)}. Water is flooding the road.",
        lambda: f"There is a water leak from a municipal pipe {pick(*LOCATIONS)} that has been running {pick(*DURATIONS)}.",
        lambda: f"Our entire neighborhood has been without water since this morning. Please investigate.",
        lambda: f"Water is pouring from a broken pipe {pick(*LOCATIONS)}. It is wasting a huge amount of water.",
        lambda: f"The water supply to our building on {pick(*STREETS)} has been cut without any notice.",
        lambda: f"We have no water pressure on the upper floors of our building. {pick(*URGENCY)}",
        lambda: f"A water main seems to have broken {pick(*LOCATIONS)}. The street is flooding.",
        lambda: f"Water has been seeping into our basement from a broken municipal pipe {pick(*DURATIONS)}.",
        lambda: f"The water meter on {pick(*STREETS)} appears to be faulty. We are being billed for water we didn't use.",
        lambda: f"Sewage water is overflowing {pick(*LOCATIONS)}. This is a public health risk. {pick(*URGENCY)}",
        lambda: f"A blocked drain {pick(*LOCATIONS)} is causing water to pool on the road after every rain.",
        lambda: f"The drainage on {pick(*STREETS)} is completely blocked and causes flooding each time it rains.",
        lambda: f"I want to report a sewage smell coming from the drain {pick(*LOCATIONS)}. {pick(*URGENCY)}",
        lambda: f"Our building's water supply was interrupted and we have young children and elderly residents.",
        lambda: f"There is a visible crack in a water main on {pick(*STREETS)} and water is seeping out.",
        lambda: f"The municipal water tank {pick(*LOCATIONS)} appears to be leaking.",
        lambda: f"Water quality in our area has declined. The water appears discolored and has an unusual smell.",
        lambda: f"Storm water is flooding {pick(*LOCATIONS)} because the drains are all blocked.",
    ]
    for _ in range(350):
        rows.append(row(pick(*templates)().strip(), "report", "water"))
    return rows

def gen_report_electricity() -> list[dict]:
    rows = []
    templates = [
        lambda: f"There has been a power outage in our area {pick(*DURATIONS)}. {pick(*URGENCY)}",
        lambda: f"The electricity has been cut to our street on {pick(*STREETS)} since this morning.",
        lambda: f"A downed power line {pick(*LOCATIONS)} is blocking the road and is extremely dangerous. {pick(*URGENCY)}",
        lambda: f"There are exposed electrical wires hanging {pick(*LOCATIONS)}. This is a major safety hazard.",
        lambda: f"Power keeps cutting out in our building every few hours. The issue has been {pick(*DURATIONS)}.",
        lambda: f"The electricity supply to our block is completely out. We have no idea when it will return.",
        lambda: f"There is a sparking electrical cable {pick(*LOCATIONS)} on {pick(*STREETS)}. {pick(*URGENCY)}",
        lambda: f"Our power has been off {pick(*DURATIONS)} and we have medical equipment that requires electricity.",
        lambda: f"The transformer {pick(*LOCATIONS)} seems to have blown. The whole neighborhood is without power.",
        lambda: f"Street lights on {pick(*STREETS)} have been working during the day and off at night — seems like a wiring problem.",
        lambda: f"A utility pole on {pick(*STREETS)} is leaning badly and could fall on nearby cars.",
        lambda: f"The electrical box {pick(*LOCATIONS)} has been sparking and smoking. Please send someone urgently.",
        lambda: f"Power fluctuations {pick(*DURATIONS)} have already damaged several appliances in our building.",
        lambda: f"The electricity meter for our building seems to have malfunctioned {pick(*DURATIONS)}.",
        lambda: f"Overhead cables on {pick(*STREETS)} are hanging very low and vehicles have been hitting them.",
        lambda: f"We have intermittent power cuts every day this week. The problem is getting worse.",
        lambda: f"An electric pole near {pick(*LOCATIONS)} has fallen and is blocking pedestrian access.",
        lambda: f"The public lighting on {pick(*STREETS)} never comes on at night. {pick(*DURATIONS)}.",
    ]
    for _ in range(350):
        rows.append(row(pick(*templates)().strip(), "report", "electricity"))
    return rows

def gen_report_waste() -> list[dict]:
    rows = []
    templates = [
        lambda: f"The garbage on {pick(*STREETS)} has not been collected {pick(*DURATIONS)}. {pick(*URGENCY)}",
        lambda: f"Trash bins {pick(*LOCATIONS)} are overflowing and the smell is unbearable.",
        lambda: f"Someone has dumped construction waste illegally {pick(*LOCATIONS)} on {pick(*STREETS)}.",
        lambda: f"The recycling point {pick(*LOCATIONS)} has not been emptied {pick(*DURATIONS)}.",
        lambda: f"Large quantities of household waste have been left on {pick(*STREETS)}. {pick(*URGENCY)}",
        lambda: f"There is a pile of rubbish that has been growing {pick(*LOCATIONS)} {pick(*DURATIONS)}.",
        lambda: f"A collection truck missed our street again this week. The waste is piling up.",
        lambda: f"People are dumping their garbage on {pick(*STREETS)} instead of using the designated bins.",
        lambda: f"The waste containers {pick(*LOCATIONS)} are damaged and waste is spilling everywhere.",
        lambda: f"There is uncollected waste on {pick(*STREETS)} attracting rats and insects. {pick(*URGENCY)}",
        lambda: f"Illegal dumping of furniture and appliances {pick(*LOCATIONS)} has been going on {pick(*DURATIONS)}.",
        lambda: f"The public bins on {pick(*STREETS)} are full and nobody has emptied them {pick(*DURATIONS)}.",
        lambda: f"Our waste collection schedule changed without notice and we don't know the new days.",
        lambda: f"There is a bad smell coming from the dumpster {pick(*LOCATIONS)} that is affecting nearby residents.",
        lambda: f"Building waste from a nearby construction site is being dumped on {pick(*STREETS)} illegally.",
        lambda: f"Dead animals have been left on {pick(*STREETS)} and haven't been removed {pick(*DURATIONS)}.",
        lambda: f"The composting bins {pick(*LOCATIONS)} are overflowing and attracting pests.",
        lambda: f"I want to report fly-tipping {pick(*LOCATIONS)}. It's been getting worse each week.",
    ]
    for _ in range(350):
        rows.append(row(pick(*templates)().strip(), "report", "waste"))
    return rows

def gen_report_environment() -> list[dict]:
    rows = []
    templates = [
        lambda: f"A nearby factory has been releasing thick black smoke {pick(*DURATIONS)}. The air quality is terrible.",
        lambda: f"There is severe noise pollution from a construction site {pick(*LOCATIONS)}. It runs day and night.",
        lambda: f"Trees in the park {pick(*LOCATIONS)} are diseased and could fall. {pick(*URGENCY)}",
        lambda: f"Graffiti has appeared on the walls of the public building {pick(*LOCATIONS)}.",
        lambda: f"There is an illegal bonfire being set {pick(*LOCATIONS)} that is causing heavy smoke.",
        lambda: f"A business {pick(*LOCATIONS)} is dumping chemicals that are polluting the drainage channel.",
        lambda: f"The public park {pick(*LOCATIONS)} has not been cleaned in weeks. It is in a terrible state.",
        lambda: f"There is excessive noise from a venue {pick(*LOCATIONS)} late at night every weekend.",
        lambda: f"A tree {pick(*LOCATIONS)} looks like it is about to fall on the road or nearby buildings.",
        lambda: f"The green area on {pick(*STREETS)} has been destroyed by illegal construction.",
        lambda: f"Stray animals are gathering {pick(*LOCATIONS)} and pose a risk to children.",
        lambda: f"There is a strong chemical smell coming from a drain {pick(*LOCATIONS)} {pick(*DURATIONS)}.",
        lambda: f"Vandalism in the community garden {pick(*LOCATIONS)} has destroyed months of work.",
        lambda: f"Industrial wastewater is being discharged into the stream near {pick(*STREETS)}.",
        lambda: f"The noise level from the new bar {pick(*LOCATIONS)} is making it impossible to sleep.",
        lambda: f"Someone is burning waste tires {pick(*LOCATIONS)}, causing toxic fumes.",
        lambda: f"The public toilets {pick(*LOCATIONS)} have been broken and unsanitary {pick(*DURATIONS)}.",
        lambda: f"Asbestos waste has been dumped {pick(*LOCATIONS)}. This is a serious health hazard. {pick(*URGENCY)}",
    ]
    for _ in range(300):
        rows.append(row(pick(*templates)().strip(), "report", "environment"))
    return rows

def gen_report_permits() -> list[dict]:
    rows = []
    templates = [
        lambda: f"There is an unlicensed construction project {pick(*LOCATIONS)} on {pick(*STREETS)} operating without permits.",
        lambda: f"A new restaurant {pick(*LOCATIONS)} appears to be operating without a valid license.",
        lambda: f"A vendor has been selling goods illegally on {pick(*STREETS)} without any permit.",
        lambda: f"Construction work on {pick(*STREETS)} is happening at night in violation of permitted hours.",
        lambda: f"There is an oversized advertising billboard {pick(*LOCATIONS)} that was erected without approval.",
        lambda: f"A building extension {pick(*LOCATIONS)} seems to exceed the permitted dimensions significantly.",
        lambda: f"An outdoor seating area was installed on the pavement without any municipal permission.",
        lambda: f"A mobile food stall on {pick(*STREETS)} has no visible permits and is blocking pedestrians.",
        lambda: f"Major excavation work {pick(*LOCATIONS)} started without any notice or visible permits.",
        lambda: f"A new shop on {pick(*STREETS)} has installed a large sign that blocks the traffic signal.",
        lambda: f"Construction on {pick(*STREETS)} is proceeding despite the building permit being expired.",
        lambda: f"Someone has converted a residential property to commercial use without planning permission.",
    ]
    for _ in range(250):
        rows.append(row(pick(*templates)().strip(), "report", "permits"))
    return rows

def gen_report_general() -> list[dict]:
    rows = []
    templates = [
        lambda: f"I want to report a stray dog that has been aggressive {pick(*LOCATIONS)} on {pick(*STREETS)}.",
        lambda: f"There has been suspicious activity {pick(*LOCATIONS)} that I think the municipality should know about.",
        lambda: f"The public bench {pick(*LOCATIONS)} has been broken {pick(*DURATIONS)} and needs replacement.",
        lambda: f"The playground equipment {pick(*LOCATIONS)} is broken and could injure children. {pick(*URGENCY)}",
        lambda: f"There is a homeless encampment {pick(*LOCATIONS)} that has been growing {pick(*DURATIONS)}.",
        lambda: f"I'm reporting a blocked public walkway {pick(*LOCATIONS)} caused by ongoing works.",
        lambda: f"Vandals have smashed the bus shelter on {pick(*STREETS)}. {pick(*DURATIONS)}.",
        lambda: f"There is heavy flooding in the basement of our building due to a blocked municipal drain.",
        lambda: f"A public water fountain {pick(*LOCATIONS)} has been broken {pick(*DURATIONS)} and needs repair.",
        lambda: f"Several public bins on {pick(*STREETS)} are missing their lids and are attracting pests.",
        lambda: f"The public clock {pick(*LOCATIONS)} has been showing the wrong time {pick(*DURATIONS)}.",
        lambda: f"I want to report damage to the war memorial {pick(*LOCATIONS)} by vandals.",
    ]
    for _ in range(200):
        rows.append(row(pick(*templates)().strip(), "report", "general"))
    return rows

def gen_reports_from_nyc311() -> list[dict]:
    """Generate report rows by processing the NYC 311 file."""
    nyc_path = Path("/tmp/311_data/nyc_311_2025.csv")
    if not nyc_path.exists():
        print("  NYC 311 file not found — skipping NYC-derived rows")
        return []

    import pandas as pd

    COMPLAINT_TEMPLATES = {
        "Blocked Driveway": [
            lambda d, a: f"Someone is blocking my driveway {pick('on my street','near my building','outside my property')}. I cannot access my vehicle.",
            lambda d, a: f"My driveway has been blocked since this morning by an unknown vehicle. Please help.",
            lambda d, a: f"There is a vehicle blocking the driveway entrance. I have been waiting {pick(*DURATIONS)} for it to be moved.",
            lambda d, a: f"I need help with a blocked driveway on my street. The owner of the vehicle cannot be found.",
            lambda d, a: f"A truck is blocking the entrance to our building's parking. {pick(*URGENCY)}",
        ],
        "Illegal Parking": [
            lambda d, a: f"There is a vehicle parked illegally on {a or 'my street'}, blocking traffic.",
            lambda d, a: f"Someone is double-parked on {a or 'the main road'} causing a traffic jam.",
            lambda d, a: f"A car has been illegally parked {pick(*LOCATIONS)} {pick(*DURATIONS)}.",
            lambda d, a: f"Vehicles are parking on the pavement outside {a or 'our building'}, blocking pedestrians.",
            lambda d, a: f"There is illegal parking near a fire hydrant on my street {pick(*DURATIONS)}.",
        ],
        "Noise - Street/Sidewalk": [
            lambda d, a: f"There is excessive noise coming from the street outside {pick(*DURATIONS)}. It's disturbing residents.",
            lambda d, a: f"People are making loud noise on the sidewalk late at night. {pick(*URGENCY)}",
            lambda d, a: f"A group outside is being extremely loud and it's been going on {pick(*DURATIONS)}.",
            lambda d, a: f"Loud music and shouting from the street has been keeping me awake {pick(*DURATIONS)}.",
            lambda d, a: f"Street noise {pick(*LOCATIONS)} is at an unacceptable level. {pick(*URGENCY)}",
        ],
        "Noise - Commercial": [
            lambda d, a: f"A commercial establishment {pick(*LOCATIONS)} is making excessive noise {pick(*DURATIONS)}.",
            lambda d, a: f"The business on my street is running loud equipment through the night.",
            lambda d, a: f"A nearby shop is blasting music that can be heard several streets away.",
            lambda d, a: f"Noise from a commercial unit {pick(*LOCATIONS)} is affecting our quality of life.",
        ],
        "Derelict Vehicle": [
            lambda d, a: f"There is an abandoned vehicle on {a or pick(*STREETS)} {pick(*DURATIONS)}. It needs to be removed.",
            lambda d, a: f"A derelict car has been parked in the same spot for weeks with no tax or registration visible.",
            lambda d, a: f"An old vehicle {pick(*LOCATIONS)} appears to have been abandoned. It's becoming an eyesore.",
            lambda d, a: f"There is a burnt-out car on {a or 'my road'} that has not been removed {pick(*DURATIONS)}.",
        ],
        "Noise - Vehicle": [
            lambda d, a: f"Vehicles are revving engines and making excessive noise {pick(*LOCATIONS)} at night.",
            lambda d, a: f"A vehicle with a broken exhaust has been parked outside my building {pick(*DURATIONS)}.",
            lambda d, a: f"Motorcycles are making excessive noise near the residential area regularly.",
        ],
        "Animal Abuse": [
            lambda d, a: f"I witnessed an animal being mistreated {pick(*LOCATIONS)}. Please send animal welfare.",
            lambda d, a: f"There is a stray animal that appears injured {pick(*LOCATIONS)}. {pick(*URGENCY)}",
            lambda d, a: f"I want to report animal cruelty I observed {pick(*LOCATIONS)}.",
        ],
        "Traffic": [
            lambda d, a: f"There is a major traffic incident {pick(*LOCATIONS)} causing severe congestion.",
            lambda d, a: f"An accident has blocked {a or 'the main road'} and traffic is at a standstill.",
            lambda d, a: f"Traffic management is needed {pick(*LOCATIONS)} — vehicles are ignoring road signs.",
        ],
        "Homeless Encampment": [
            lambda d, a: f"There is a homeless encampment {pick(*LOCATIONS)} that has been growing {pick(*DURATIONS)}.",
            lambda d, a: f"People have set up an informal camp {pick(*LOCATIONS)} and it is causing issues for residents.",
            lambda d, a: f"There is a large informal settlement {pick(*LOCATIONS)} that needs attention from the municipality.",
        ],
        "Graffiti": [
            lambda d, a: f"Graffiti has appeared on {a or 'the wall near my street'} {pick(*DURATIONS)}.",
            lambda d, a: f"The public building {pick(*LOCATIONS)} has been vandalized with spray paint.",
            lambda d, a: f"Graffiti is spreading across several walls {pick(*LOCATIONS)}. {pick(*URGENCY)}",
        ],
        "Vending": [
            lambda d, a: f"An unlicensed street vendor {pick(*LOCATIONS)} is blocking pedestrian access.",
            lambda d, a: f"There is an unauthorized food stall on {a or pick(*STREETS)} with no permits visible.",
        ],
    }

    # Default template for unmapped types
    DEFAULT_TEMPLATES = [
        lambda d, a, ct: f"I want to report a {ct.lower()} issue {pick(*LOCATIONS)}. {pick(*URGENCY)}",
        lambda d, a, ct: f"There is a problem related to {ct.lower()} on {a or pick(*STREETS)} that needs attention.",
        lambda d, a, ct: f"Please send someone to deal with a {ct.lower()} situation {pick(*LOCATIONS)}.",
    ]

    CATEGORY_MAP = {
        "Blocked Driveway": "roads", "Illegal Parking": "roads",
        "Traffic": "roads", "Derelict Vehicle": "roads",
        "Noise - Street/Sidewalk": "environment", "Noise - Commercial": "environment",
        "Noise - Vehicle": "environment", "Noise - Park": "environment",
        "Noise - House of Worship": "environment", "Animal Abuse": "environment",
        "Graffiti": "environment", "Homeless Encampment": "general",
        "Vending": "permits", "Posting Advertisement": "permits",
        "Drinking": "general", "Panhandling": "general",
    }

    print("  Loading NYC 311 CSV...")
    df = pd.read_csv(nyc_path,
                     usecols=["Complaint Type", "Descriptor", "Incident Address"],
                     low_memory=False)
    df = df[df["Descriptor"].notna()]
    df["category"] = df["Complaint Type"].map(CATEGORY_MAP).fillna("general")

    # Stratified sample: target proportional to available rows, capped at ~80/category
    target_per_type = {}
    available = df.groupby("Complaint Type").size()
    total_target = 600
    total_available = available.sum()
    for ct, count in available.items():
        target_per_type[ct] = max(5, int(count / total_available * total_target))

    result_rows = []
    for ct, target in target_per_type.items():
        subset = df[df["Complaint Type"] == ct].sample(
            n=min(target, len(df[df["Complaint Type"] == ct])),
            random_state=42
        )
        templates = COMPLAINT_TEMPLATES.get(ct)
        cat = CATEGORY_MAP.get(ct, "general")
        for _, record in subset.iterrows():
            descriptor = str(record.get("Descriptor", ""))
            address = str(record.get("Incident Address", "")) or pick(*STREETS)
            if templates:
                t = pick(*templates)
                text = t(descriptor, address).strip()
            else:
                t = pick(*DEFAULT_TEMPLATES)
                text = t(descriptor, address, ct).strip()
            result_rows.append(row(text, "report", cat))

    print(f"  NYC 311 derived rows: {len(result_rows)}")
    return result_rows


# ── QUESTION templates (~3 000 rows) ──────────────────────────────────────

def gen_questions() -> list[dict]:
    rows = []

    Q_WATER = [
        "How do I report a water outage in my building?",
        "What is the procedure for requesting a new water connection?",
        "Who do I contact about high water pressure damaging my pipes?",
        "How often is the water quality tested in the municipal supply?",
        "What are the steps to apply for a water meter installation?",
        "How long does it take to restore water supply after an outage?",
        "Can I request a water audit for my building?",
        "What should I do if the water in my area smells unusual?",
        "Who is responsible for replacing old water pipes in the neighborhood?",
        "How do I dispute an unusually high water bill?",
        "Is there a schedule for planned water outages in our district?",
        "What are the regulations for greywater reuse in residential buildings?",
        "How do I apply for a water supply extension to my new property?",
        "Where can I report a water main leak?",
        "What are the water conservation guidelines for this municipality?",
        "How do I find out if my area is affected by water rationing?",
        "What is the normal water pressure standard for residential areas?",
        "How can I check if my building is connected to the main water network?",
        "Who handles water supply complaints outside of business hours?",
        "What is the procedure for temporarily suspending water service?",
    ]

    Q_ELECTRICITY = [
        "Who do I call about a power outage in my area?",
        "How long does it typically take to restore electricity after a fault?",
        "What is the procedure to report a downed power line?",
        "How do I apply for a new electricity connection for my property?",
        "What are the permitted working hours for electrical maintenance?",
        "How do I dispute an incorrect electricity bill?",
        "Can I request a safety inspection for the electrical wiring in my building?",
        "What should I do if I see sparking cables near my home?",
        "How do I find out about planned power cuts in my district?",
        "Who is responsible for the street lighting on residential roads?",
        "How do I apply for additional electricity capacity for my business?",
        "What are the regulations for solar panel installation in residential areas?",
        "Is there financial assistance available for energy efficiency upgrades?",
        "How do I report a faulty electricity meter?",
        "Who do I contact about flickering street lights?",
        "What is the process for getting a generator permit?",
        "How do I transfer an electricity account when I move?",
        "What is the maximum voltage fluctuation allowed in residential supply?",
    ]

    Q_ROADS = [
        "Who is responsible for maintaining the roads in my district?",
        "How do I submit a request to fix a pothole?",
        "What is the process for requesting a new road sign?",
        "How long does a road repair request usually take to be processed?",
        "Can I apply for a road closure permit for a neighborhood event?",
        "What are the regulations for parking near a school?",
        "How do I report a dangerous junction that needs traffic lights?",
        "Who do I contact about road markings that need repainting?",
        "How can I request a speed bump on my residential street?",
        "What is the procedure for requesting a parking permit for my building?",
        "Who handles road accidents involving municipal infrastructure?",
        "How do I find out about planned road works in my area?",
        "What is the weight limit for vehicles on local roads?",
        "How do I request disabled parking bays near my home?",
        "Who is responsible for clearing fallen trees from the road?",
        "What should I do if road works have damaged my vehicle?",
        "How do I apply for road-closure during a renovation project?",
        "Is there a designated route for heavy goods vehicles in the municipality?",
        "How do I report a road sign that has been vandalized?",
        "What are the regulations for opening a trench on a public road?",
    ]

    Q_WASTE = [
        "What day is garbage collected in my street?",
        "How do I arrange for bulk waste collection?",
        "Where is the nearest recycling center?",
        "What items are accepted at the recycling facility?",
        "How do I report an overflowing trash bin?",
        "Is there a fee for large item collection from the municipality?",
        "How do I dispose of hazardous household waste like batteries?",
        "What are the fines for illegal dumping in this municipality?",
        "How often are public bins emptied in parks?",
        "Can I request additional waste bins for my building?",
        "What should I do with old furniture and appliances?",
        "How do I compost food waste in this district?",
        "Is construction waste the responsibility of the owner or the contractor?",
        "What is the electronic waste disposal procedure in this municipality?",
        "How do I report a business that is dumping waste illegally?",
        "Where can I drop off old medications for safe disposal?",
        "What are the rules for waste separation in residential areas?",
        "How do I get the garbage collection schedule for my neighborhood?",
        "Is organic waste collected separately from regular garbage?",
    ]

    Q_PERMITS = [
        "How do I apply for a building permit?",
        "What documents are required to register a new business?",
        "How long does it take to get a building permit approved?",
        "What is the fee for a commercial activity license?",
        "Can I renew my business license online?",
        "What are the zoning regulations for my area?",
        "How do I get approval to put tables on the pavement outside my restaurant?",
        "What permits are needed to open a food business?",
        "Who do I contact to check if a property is listed for heritage protection?",
        "How do I apply for a permit to install solar panels?",
        "What are the rules for building a fence or wall on my property?",
        "How do I get a certificate of occupancy for a new building?",
        "Can I subdivide my land and what is the process?",
        "What permits are required for a home renovation?",
        "How do I appeal a rejected building permit application?",
        "What are the requirements for an outdoor advertising permit?",
        "How long is a building permit valid for?",
        "What happens if I start construction without a permit?",
        "How do I get an exemption for minor works that don't require a permit?",
        "What documents prove that a structure was built with the required permits?",
    ]

    Q_TAXES = [
        "How is my municipal tax calculated?",
        "When is the deadline to pay municipal fees?",
        "Is there a discount for early payment of annual municipal tax?",
        "How do I pay my municipal fee online?",
        "Who qualifies for an exemption from municipal taxes?",
        "What is the penalty for late payment of municipal fees?",
        "How do I contest a municipal tax assessment?",
        "Where can I pay my municipal fees in person?",
        "Are there payment plans available for large municipal tax bills?",
        "What happens if I don't pay my municipal fees for a year?",
        "How do I update my address for municipal fee correspondence?",
        "What receipts do I need to keep for municipal tax purposes?",
        "Is there a property tax rebate for first-time homeowners?",
        "How do I find out if I have any outstanding municipal fees?",
        "Are senior citizens entitled to a municipal tax reduction?",
        "How do I transfer a property and update municipal tax records?",
        "What is the process to register a new property for municipal fees?",
        "What happens to municipal fees when a property is sold?",
        "How are commercial properties taxed compared to residential ones?",
    ]

    Q_ENVIRONMENT = [
        "How do I report a business that is polluting the local river?",
        "What are the noise regulations for construction in residential areas?",
        "Who is responsible for maintaining public green spaces?",
        "How can I report a neighbor who is burning waste?",
        "What environmental impact assessments are required for new developments?",
        "How do I report a chemical spill near a residential area?",
        "Are there any tree preservation orders in our neighborhood?",
        "What can I do about a neighbor whose overgrown trees are blocking light?",
        "Who is responsible for controlling stray animals in our area?",
        "How do I report air pollution from a nearby factory?",
        "What are the rules regarding bonfires in residential areas?",
        "Is there a program to plant trees on my street?",
        "Who should I contact about asbestos found in a public building?",
        "How do I report illegal logging or tree removal in the area?",
        "What noise levels are permitted during nighttime hours?",
        "How can residents access environmental health reports for our area?",
        "What fines apply to businesses that exceed permitted emission levels?",
        "How do I report a pest infestation in a public building?",
        "Is there a program to reduce noise levels from heavy traffic?",
    ]

    Q_GENERAL = [
        "What are the opening hours of the municipality office?",
        "Where exactly is the municipality building located?",
        "Is there a phone number for municipal emergency services?",
        "Do I need an appointment to visit the municipal office?",
        "How do I find out which department handles my complaint?",
        "Can I submit a formal complaint about a municipal employee?",
        "How do I request public records from the municipality?",
        "What services can I access online without visiting the office?",
        "How long does it take to get a response from the municipality?",
        "Is there a mobile app for municipal services?",
        "How can I track the progress of my submitted request?",
        "Are municipal services available in Arabic and English?",
        "How do I request an interpreter for a municipal appointment?",
        "What accessibility services are available at the municipal office?",
        "How do I get a proof of residence certificate?",
        "What is the reference number format for tracking a complaint?",
        "Can I authorize someone else to collect documents on my behalf?",
        "How do I update my contact information with the municipality?",
        "Is there a satisfaction survey after municipal services are completed?",
        "How do I join a community consultation for local planning decisions?",
    ]

    ALL_Q = list(itertools.chain(
        [(q, "water") for q in Q_WATER],
        [(q, "electricity") for q in Q_ELECTRICITY],
        [(q, "roads") for q in Q_ROADS],
        [(q, "waste") for q in Q_WASTE],
        [(q, "permits") for q in Q_PERMITS],
        [(q, "taxes") for q in Q_TAXES],
        [(q, "environment") for q in Q_ENVIRONMENT],
        [(q, "general") for q in Q_GENERAL],
    ))

    # Cycle and vary with prefix/suffix additions to reach 3 000
    PREFIXES = [
        "", "", "", "",                                   # bare question (most common)
        "I'd like to know: ", "Could you tell me ",
        "Quick question — ", "I was wondering, ",
        "Can you help me understand ", "I need information about ",
        "Hello, I have a question about ", "I'm trying to find out ",
        "Excuse me, I need to ask about ",
        "Could you clarify ", "I need to know ",
    ]
    SUFFIXES = [
        "", "", "", "",
        " Please advise.", " Thank you.",
        " Any information would be helpful.",
        " I have been trying to find this out for a while.",
        " I couldn't find this on the website.",
    ]

    seen = set()
    attempts = 0
    while len(rows) < 3000 and attempts < 50000:
        q, cat = RNG.choice(ALL_Q)
        prefix = pick(*PREFIXES)
        suffix = pick(*SUFFIXES)
        if prefix and q[0].isupper():
            q = q[0].lower() + q[1:]
        text = (prefix + q.rstrip("?") + ("?" if not suffix else "") + suffix).strip()
        if text not in seen:
            seen.add(text)
            rows.append(row(text, "question", cat))
        attempts += 1

    return rows


# ── HUMAN templates (~3 000 rows) ─────────────────────────────────────────

def gen_human() -> list[dict]:
    rows = []

    OPENERS = [
        "I need to speak with a real person.",
        "Please connect me to a human agent.",
        "I'd like to talk to someone in the office.",
        "Can I speak to an actual person, not an automated system?",
        "I need to talk to a staff member directly.",
        "Please transfer me to a municipal employee.",
        "I want to speak with a representative from the municipality.",
        "I'd prefer to speak with a human being about this.",
        "Can you connect me with the relevant department?",
        "I need to reach someone who can actually help me.",
        "I want to speak to the person in charge of this matter.",
        "Please put me through to a real person.",
        "I'd like to file a formal complaint with a human employee.",
        "I need to speak to the manager or supervisor.",
        "Is there a direct phone number for a staff member?",
        "Can someone from the municipality call me back?",
        "I don't want to deal with a bot — I need a human.",
        "Please give me the direct contact for this department.",
        "I need to be connected to someone who can make decisions.",
        "I want to escalate this to a real person.",
        "Can a municipal inspector come and assess this situation?",
        "I need to file this complaint with an authorized officer.",
        "Please have someone call me back as soon as possible.",
        "I need to speak to the duty officer today.",
        "Can you arrange for a human representative to contact me?",
        "I want to speak to the head of the relevant department.",
        "I'd like to request a meeting with a municipal official.",
        "Please direct me to the complaints officer.",
        "I need to submit this formally to a staff member.",
        "Can someone from the municipality visit the site with me?",
    ]

    REASONS = [
        "This automated system isn't addressing my specific situation.",
        "My issue is complex and needs a person's judgment.",
        "I've been waiting for resolution and nobody has contacted me.",
        "This is an urgent matter that can't wait for a form submission.",
        "I have physical evidence I need to present to someone.",
        "I want a formal record with a human official.",
        "The previous response I received wasn't helpful.",
        "I need reassurance that my complaint is being taken seriously.",
        "I have additional details that are too complex for this interface.",
        "My elderly neighbor cannot use digital services.",
        "I represent multiple residents on my street with this concern.",
        "I've tried contacting the office by phone and no one answered.",
        "I need an official document confirming my complaint.",
        "I have a time-sensitive legal matter related to this.",
        "I've submitted this complaint three times with no response.",
        "I need someone to come and physically inspect the problem.",
        "",  # no reason given (naturally happens)
        "",
        "",
    ]

    CLOSERS = [
        "", "", "",
        "Please respond as soon as possible.",
        "Thank you for your help.",
        "This is causing real hardship for residents.",
        "Your assistance is greatly appreciated.",
        "I am available any time this week.",
        "Please call me at your earliest convenience.",
        "I will be available at the office between 9am and 5pm.",
    ]

    seen = set()
    attempts = 0
    while len(rows) < 3000 and attempts < 50000:
        opener = pick(*OPENERS)
        reason = pick(*REASONS)
        closer = pick(*CLOSERS)
        parts = [opener]
        if reason:
            parts.append(reason)
        if closer:
            parts.append(closer)
        text = " ".join(parts).strip()
        if text not in seen:
            seen.add(text)
            rows.append(row(text, "human", "none"))
        attempts += 1

    return rows


# ── SPAM templates (~3 000 rows) ──────────────────────────────────────────

def gen_spam() -> list[dict]:
    rows = []

    # ── Enron spam (real emails) ──────────────────────────────────────────
    try:
        from datasets import load_dataset
        print("  Streaming Enron spam...")
        ds = load_dataset("SetFit/enron_spam", split="train", streaming=True)
        collected = 0
        for example in ds:
            if example.get("label") == 1:  # spam
                text = (example.get("subject", "") + " " + example.get("text", "")).strip()[:300]
                if len(text) > 20:
                    rows.append(row(text, "spam", "none"))
                    collected += 1
                    if collected >= 400:
                        break
        print(f"  Enron spam collected: {collected}")
    except Exception as e:
        print(f"  Enron spam skipped: {e}")

    # ── Synthetic spam templates ──────────────────────────────────────────
    # ── Large spam corpus — parameterised for high variety ───────────────

    AMOUNTS   = [49, 99, 199, 299, 499, 999, 1000, 2000, 5000, 10000, 25000, 50000, 100000]
    PERCENTS  = [10, 20, 50, 100, 150, 200, 300, 500, 1000]
    DAYS      = [1, 2, 3, 7, 10, 14, 21, 30]
    FOLLOWERS = [500, 1000, 5000, 10000, 50000, 100000]
    CRYPTO    = ["Bitcoin", "Ethereum", "Dogecoin", "Solana", "XRP", "BNB"]
    DRUGS     = ["Viagra", "Cialis", "Xanax", "Ambien", "Valium", "Adderall", "Oxycodone"]
    DISEASES  = ["diabetes", "cancer", "arthritis", "depression", "hypertension", "obesity"]
    BRANDS    = ["PayPal", "Amazon", "Apple", "Netflix", "Microsoft", "Google", "Facebook"]
    SERVICES  = ["account", "subscription", "membership", "license", "wallet", "profile"]
    STOCKS    = ["XYZQ", "ABCM", "PLQR", "MNOP", "QRST", "UVWX", "BCDE"]
    DEGREES   = ["MBA", "PhD", "Bachelor's degree", "Master's degree", "medical license", "law degree"]
    JOBS      = ["data entry", "online surveys", "copy-paste tasks", "email reading", "social media posting"]
    COUNTRIES = ["Nigeria", "Ghana", "South Africa", "UK", "Spain", "Dubai", "Singapore"]
    GREETINGS = ["Hello dear friend,", "Dear beneficiary,", "Greetings!", "ATTENTION!", "CONGRATULATIONS!", "Dear winner,", "Hi there,"]

    def spam_sentence():
        """Generate a random spam sentence from a large parameterised pool."""
        category = RNG.randint(0, 13)
        if category == 0:
            return f"Congratulations! You have won ${pick(*AMOUNTS)}! Click here to claim your prize today."
        elif category == 1:
            return f"Earn ${pick(*AMOUNTS)} per {pick('day','week','month')} working from home. No experience needed. Start today!"
        elif category == 2:
            return f"URGENT: Your {pick(*BRANDS)} {pick(*SERVICES)} has been suspended. Click to verify your identity immediately."
        elif category == 3:
            return f"Exclusive investment: guaranteed {pick(*PERCENTS)}% return in {pick(*DAYS)} days. Minimum investment only ${pick(100,200,500,1000)}."
        elif category == 4:
            return f"Buy {pick(*DRUGS)} online — no prescription required. Discreet shipping, lowest prices guaranteed."
        elif category == 5:
            return f"Lose {pick(10,20,30,50)} kg in {pick(*DAYS)} days with our revolutionary pill. Doctors are shocked!"
        elif category == 6:
            return f"Get {pick(*FOLLOWERS)} real {pick('Instagram','Twitter','TikTok','YouTube')} followers in {pick(*DAYS)} days. 100% safe."
        elif category == 7:
            return f"{pick(*GREETINGS)} I am a prince from {pick(*COUNTRIES)} with ${pick(5,10,20,50)} million to transfer. I need your help."
        elif category == 8:
            return f"Your {pick(*BRANDS)} account shows suspicious activity. Verify NOW at: secure-{pick('verify','update','confirm')}.link"
        elif category == 9:
            return f"Natural cure for {pick(*DISEASES)} — {pick(100000,500000,1000000)} people already cured. Doctors hiding this secret!"
        elif category == 10:
            return f"FREE {pick(*DEGREES)} diploma — 100% accredited, no study required. Delivered in {pick(*DAYS)} business days."
        elif category == 11:
            return f"Work from home: {pick(*JOBS)}. Earn ${pick(20,50,100,200)}/hour. No skills needed. Apply now!"
        elif category == 12:
            return f"{pick(*CRYPTO)} is about to {pick('10x','20x','50x','100x')}! Buy NOW before it's too late. Insider tip."
        else:
            return f"Forward this to {pick(5,10,20,50)} contacts and receive ${pick(*AMOUNTS)} in your {pick(*BRANDS)} account within {pick(*DAYS)} hours."

    seen = {r["text"] for r in rows}
    attempts = 0
    while len(rows) < 3000 and attempts < 200000:
        text = spam_sentence().strip()
        if text not in seen:
            seen.add(text)
            rows.append(row(text, "spam", "none"))
        attempts += 1

    return rows


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=== English Large Dataset Generator ===")
    print("Target: ~3 000 rows per intent class\n")

    all_new = []

    print("Generating report rows...")
    report_rows = (
        gen_report_roads() +
        gen_report_water() +
        gen_report_electricity() +
        gen_report_waste() +
        gen_report_environment() +
        gen_report_permits() +
        gen_report_general()
    )
    nyc_rows = gen_reports_from_nyc311()
    report_rows += nyc_rows
    # Trim to 3 000, shuffle for variety
    RNG.shuffle(report_rows)
    report_rows = report_rows[:3000]
    print(f"  Report rows: {len(report_rows)}")
    all_new.extend(report_rows)

    print("Generating question rows...")
    question_rows = gen_questions()
    print(f"  Question rows: {len(question_rows)}")
    all_new.extend(question_rows)

    print("Generating human rows...")
    human_rows = gen_human()
    print(f"  Human rows: {len(human_rows)}")
    all_new.extend(human_rows)

    print("Generating spam rows...")
    spam_rows = gen_spam()
    print(f"  Spam rows: {len(spam_rows)}")
    all_new.extend(spam_rows)

    print(f"\nTotal new rows: {len(all_new)}")

    # ── Append to CSV ─────────────────────────────────────────────────────
    existing = []
    if CSV_PATH.exists():
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            existing = list(csv.DictReader(f))

    existing_texts = {r["text"] for r in existing}
    deduped = [r for r in all_new if r["text"] not in existing_texts]
    print(f"After dedup against existing: {len(deduped)} new rows")

    # Renumber IDs
    start_id = len(existing) + 1
    for i, r in enumerate(deduped, start_id):
        r["id"] = f"en-en-large-{i:05d}"

    # Write
    all_rows = existing + deduped
    fieldnames = ["id", "text", "lang", "variety", "intent", "category", "split"]
    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(all_rows)

    # ── Summary ───────────────────────────────────────────────────────────
    from collections import Counter
    split_counts = Counter(r["split"] for r in deduped)
    intent_counts = Counter(r["intent"] for r in deduped)
    print(f"\n=== Summary ===")
    print(f"Total rows in CSV: {len(all_rows)}")
    print(f"New EN rows added: {len(deduped)}")
    print(f"Intent distribution: {dict(intent_counts)}")
    print(f"Split distribution: {dict(split_counts)}")
    pct_test = split_counts['test'] / len(deduped) * 100 if deduped else 0
    print(f"Test %: {pct_test:.1f}%")

    # Per-class test counts
    test_rows = [r for r in deduped if r["split"] == "test"]
    test_by_intent = Counter(r["intent"] for r in test_rows)
    print(f"Test rows per intent: {dict(test_by_intent)}")
    print("\nNext step: python3 train_bilingual.py  (or re-run training notebook)")


if __name__ == "__main__":
    main()
