#!/usr/bin/env python3
"""Create a self-contained, entirely fictional Simpsons travel demo."""
import argparse
import json
from pathlib import Path

PEOPLE = ['Homer', 'Marge', 'Bart', 'Lisa', 'Maggie']
ROOT = Path(__file__).resolve().parent


def demo_pdf(path, pages):
    """Tiny dependency-free PDF writer; pages contain only invented plain text."""
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'', b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>']
    children = []
    for lines in pages:
        page_id = len(objects) + 1
        content_id = page_id + 1
        children.append(f'{page_id} 0 R')
        objects.append(f'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>'.encode())
        commands = ['BT', '/F1 15 Tf', '48 742 Td', '23 TL']
        for line in lines:
            safe = line.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')
            commands += [f'({safe}) Tj', 'T*']
        commands.append('ET')
        content = '\n'.join(commands).encode('ascii')
        objects.append(b'<< /Length ' + str(len(content)).encode() + b' >>\nstream\n' + content + b'\nendstream')
    objects[1] = f'<< /Type /Pages /Count {len(children)} /Kids [{" ".join(children)}] >>'.encode()
    info_id = len(objects) + 1
    objects.append(b'<< /Title (Springfield family travel demo) /Author (Springfield Demo) /Subject (Fictional sample - not valid for travel) >>')
    output = bytearray(b'%PDF-1.4\n%\xe2\xe3\xcf\xd3\n')
    offsets = [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(output))
        output += f'{n} 0 obj\n'.encode() + obj + b'\nendobj\n'
    xref = len(output)
    output += f'xref\n0 {len(objects)+1}\n0000000000 65535 f \n'.encode()
    output += b''.join(f'{n:010d} 00000 n \n'.encode() for n in offsets[1:])
    output += f'trailer\n<< /Size {len(objects)+1} /Root 1 0 R /Info {info_id} 0 R >>\nstartxref\n{xref}\n%%EOF\n'.encode()
    path.write_bytes(output)


def initialize(data):
    data = Path(data)
    target = data / 'travel-app.json'
    if target.exists():
        return False
    data.mkdir(parents=True, exist_ok=True)
    bookings = []
    for carrier, ref, prefix, title, route in [
        ('Krusty Air', 'D0NUT5', 'outbound', 'Outbound · Krusty Air', '1–3 June · Springfield → Brockway → Terror Lake → Cypress Creek'),
        ('Monorail Express', 'MONO42', 'return', 'Homeward · Monorail Express', '10–12 June · Cypress Creek → Ogdenville → North Haverbrook → Springfield'),
    ]:
        tickets = []
        for person in PEOPLE:
            name = f'{prefix}-{person.lower()}-simpson.pdf'
            demo_pdf(data / name, [['SIMPSONS FAMILY TRAVEL', 'FICTIONAL SAMPLE - NOT VALID FOR TRAVEL', '', f'Traveler: {person} Simpson', f'Carrier: {carrier}', f'Demo booking: {ref}', f'Direction: {title.split(" · ")[0]}', 'All locations, flights and allowances are fictional.', 'Keep a spare donut in your carry-on.']])
            tickets.append({'person': person, 'file': name})
        bookings.append({'airline': carrier, 'reference': ref, 'title': title, 'subtitle': route, 'tickets': tickets})
    route = [
        ('KA101', 'Krusty Air', 'SPF', 'Springfield', 'BRK', 'Brockway', '2030-06-01T09:00', '2030-06-01T10:15', 'Donut Terminal', 'Monorail Hall', 'Homer 1A · Marge 1B · Bart 2A · Lisa 2B · Maggie on lap', 'Brockway · inspect the monorail before boarding'),
        ('ME202', 'Monorail Express', 'BRK', 'Brockway', 'TRL', 'Terror Lake', '2030-06-02T11:00', '2030-06-02T12:30', 'Platform 1', 'Houseboat Dock', 'Family cabin · keep the rakes stowed', 'Terror Lake · houseboat stop; watch your step'),
        ('GA303', 'Globex Air', 'TRL', 'Terror Lake', 'CYP', 'Cypress Creek', '2030-06-03T14:00', '2030-06-03T15:45', 'Witness Protection Lounge', 'Globex Terminal', 'Business hammocks · Maggie on lap', 'Cypress Creek · 3–10 June · hammock district'),
        ('ME404', 'Monorail Express', 'CYP', 'Cypress Creek', 'OGD', 'Ogdenville', '2030-06-10T10:00', '2030-06-10T11:30', 'Globex Terminal', 'Platform 2', 'Four seats and one lap infant · demo only', 'Ogdenville · a perfectly cromulent connection'),
        ('ME505', 'Monorail Express', 'OGD', 'Ogdenville', 'NHB', 'North Haverbrook', '2030-06-11T13:00', '2030-06-11T14:00', 'Platform 2', 'Abandoned Station', 'Do not buy a used monorail', 'North Haverbrook · change before the track runs out'),
        ('KA606', 'Krusty Air', 'NHB', 'North Haverbrook', 'SPF', 'Springfield', '2030-06-12T16:00', '2030-06-12T17:15', 'Platform 3', 'Donut Terminal', 'Homer 1A · Marge 1B · Bart 2A · Lisa 2B · Maggie on lap', 'Home · 12 June'),
    ]
    fields = ('number', 'carrier', 'from', 'fromCity', 'to', 'toCity', 'depart', 'arrive', 'fromTerminal', 'toTerminal', 'note', 'after')
    flights = [dict(zip(fields, leg)) for leg in route]
    passes = []
    all_pages = []
    for flight in (flights[0], flights[-1]):
        per_person = []
        for person, seat in zip(PEOPLE, ['1A', '1B', '2A', '2B', 'Lap infant with Marge']):
            name = f'boarding-{flight["number"].lower()}-{person.lower()}.pdf'
            page = ['DEMO BOARDING PASS', 'FICTIONAL SAMPLE - NOT VALID FOR TRAVEL', '', f'Traveler: {person} Simpson', f'Flight: {flight["number"]} / {flight["carrier"]}', f'Route: {flight["fromCity"]} to {flight["toCity"]}', f'Departure: {flight["depart"].replace("T", " ")}', f'Seat: {seat}', 'Gate: DONUT - check the fictional departure board.']
            demo_pdf(data / name, [page])
            all_pages.append(page)
            per_person.append({'person': person, 'seat': seat, 'file': name})
        passes.append({'title': f'{flight["fromCity"]} → {flight["toCity"]}', 'note': f'{flight["number"]} · {flight["depart"][:10]} · fictional demonstration', 'passes': per_person})
    demo_pdf(data / 'all-demo-boarding-passes.pdf', all_pages)
    items = []

    def add(ident, title, section, group, **extra):
        items.append({'id': ident, 'text': title, 'section': section, 'group': group, 'done': False, 'source': 'demo', **extra})

    for ident, title, group, note in [
        ('homer-clothes', 'Homer: white shirts, blue trousers and one spare outfit', 'Family clothes', 'Leave room for an emergency donut.'),
        ('marge-clothes', 'Marge: green dress, layers and comfortable shoes', 'Family clothes', 'Pack a practical travel outfit too.'),
        ('bart-clothes', 'Bart: orange shirts, blue shorts and sneakers', 'Family clothes', 'Skateboard travels only if the carrier allows it.'),
        ('lisa-clothes', 'Lisa: red dress, layers and walking shoes', 'Family clothes', 'Saxophone is a separate packing decision.'),
        ('maggie-clothes', 'Maggie: three spare outfits, warm layer and socks', 'Maggie’s carry-on', 'Use her actual needs to set quantities.'),
        ('diapers', 'Diapers, wipes and changing mat', 'Maggie’s carry-on', 'Size the supply for the journey plus delays.'),
        ('feeding', 'Milk, bottles, familiar meals and bib', 'Maggie’s carry-on', 'Carry food and a small bottle-washing kit.'),
        ('pacifiers', 'Maggie’s pacifiers and a familiar comfort toy', 'Maggie’s carry-on', 'A spare prevents an airport treasure hunt.'),
        ('donuts', 'Homer’s donuts and family snacks', 'Cabin kits', 'Lisa gets a vegetarian option.'),
        ('entertainment', 'Books, headphones and offline cartoons', 'Cabin kits', 'Bart does not get a megaphone.'),
        ('toiletries', 'Toothbrushes, toothpaste and wash kit', 'Cabin kits', 'Keep toiletries together.'),
        ('medicine', 'Family medicines in their labelled containers', 'Cabin kits', 'Bring the family’s usual supplies.'),
        ('chargers', 'Chargers, adapters and permitted power bank', 'Cabin kits', 'Check your actual carrier rules before a real trip.'),
        ('stroller', 'Stroller, carrier and protective bag', 'Family equipment', 'Do not leave it beside a suspicious rake.'),
        ('documents', 'Fictional tickets and visitor paperwork', 'Family equipment', 'Every PDF in this demo is generated from invented data.'),
        ('hammock', 'Hammock district shopping list', 'Optional extras', 'Visit Mary Ann’s Hammocks or Hammocks R Us.'),
        ('rake-safety', 'Closed-toe shoes for Terror Lake', 'Optional extras', 'Sideshow Bob has not completed the hazard assessment.'),
    ]:
        add(ident, title, 'packing', group, note=note)
    add('visitor-cards', 'File fictional visitor cards for all five Simpsons', 'admin', 'Before departure', due='2030-05-28', note='Demo task only. Checking this box updates todo.md; no form is submitted.')
    add('documents-check', 'Check every family member’s travel documents', 'admin', 'Before departure', note='The sample PDFs are not real tickets.')
    add('maggie-seat', 'Confirm Maggie’s seating and infant equipment', 'admin', 'Before departure', note='Demo assumes she travels on Marge’s lap; no bassinet is reserved.')
    add('lounge', 'Confirm the Krusty Air donut lounge', 'admin', 'Connections', note='An invented lounge, with an invented donut allowance.')
    add('houseboat', 'Confirm the Terror Lake houseboat mooring', 'admin', 'At the destination', note='Ask whether the rakes are complimentary.')
    add('globex', 'Arrange a Cypress Creek transfer', 'admin', 'At the destination', note='Hank Scorpio’s flamethrower is not an airport shuttle.')
    add('monorail', 'Check all three monorail connections', 'admin', 'Connections', note='Brockway, Ogdenville and North Haverbrook remain fictional routing choices.')
    trip = {'title': 'The Simpsons’ Great Escape', 'dates': '1–12 June 2030', 'people': PEOPLE, 'bookings': bookings, 'flights': flights,
            'boardingPasses': {'bundle': 'all-demo-boarding-passes.pdf', 'flights': passes}}
    state = {'revision': 1, 'updatedAt': None, 'trip': trip, 'items': items}
    (data / 'todo.md').write_text('# The Simpsons — travel admin\n\n- [ ] **28 May 2030 — File fictional visitor cards** for Homer, Marge, Bart, Lisa and Maggie.\n\nThis is a fictional demonstration; no external form is submitted.\n', encoding='utf-8')
    target.write_text(json.dumps(state, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    return True


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', type=Path, default=ROOT / 'demo-data')
    args = parser.parse_args()
    fresh = initialize(args.data)
    print('Demo created: five Simpsons, six legs, ten tickets and ten boarding passes.' if fresh else 'Existing demo data preserved.')
