"""Seed data initialization for the Fellowship Quest Tracker."""
from models.user import User, db
from models.member import Member
from models.location import Location
from models.quest import Quest
from flask import Flask
from typing import List, Dict, Any

def seed_members() -> List[Member]:
    """Create Fellowship members."""
    members_data = [
        {
            'name': 'Frodo Baggins',
            'race': 'Hobbit',
            'role': 'Ring-bearer',
            'status': 'active',
            'description': 'The brave hobbit who carries the One Ring to Mount Doom.'
        },
        {
            'name': 'Samwise Gamgee',
            'race': 'Hobbit',
            'role': 'Companion',
            'status': 'active',
            'description': 'Frodo\'s loyal friend and companion on the journey.'
        },
        {
            'name': 'Aragorn',
            'race': 'Human',
            'role': 'Ranger',
            'status': 'active',
            'description': 'The rightful heir to the throne of Gondor.'
        },
        {
            'name': 'Legolas',
            'race': 'Elf',
            'role': 'Archer',
            'status': 'active',
            'description': 'Elven prince and master archer from Mirkwood.'
        },
        {
            'name': 'Gimli',
            'race': 'Dwarf',
            'role': 'Warrior',
            'status': 'active',
            'description': 'Dwarf warrior from the Lonely Mountain.'
        },
        {
            'name': 'Gandalf',
            'race': 'Wizard',
            'role': 'Guide',
            'status': 'active',
            'description': 'The Grey Wizard who guides the Fellowship.'
        }
    ]
    
    members = []
    for data in members_data:
        member = Member.query.filter_by(name=data['name']).first()
        if not member:
            member = Member(**data)
            db.session.add(member)
            members.append(member)
        else:
            members.append(member)
    
    db.session.commit()
    return members

def seed_locations() -> List[Location]:
    """Create Middle-earth locations.
    
    Coordinates are pixel-based, matching the MiddleEarthMap coordinate system.
    Map image dimensions: 5000x4344 pixels (width x height).
    Coordinates from MiddleEarthMap by Yohann Bethoule (https://github.com/YohannBethoule/MiddleEarthMap).
    Includes all 45 locations from the original MiddleEarthMap markers.json.
    """
    locations_data = [
        # Eriador
        {
            'name': 'Hobbiton',
            'region': 'Eriador',
            'description': 'Hobbiton was a hobbit village in the central regions of the Shire, within the borders of the Westfarthing.',
            'map_x': 1482.0,
            'map_y': 1158.0
        },
        {
            'name': 'The Shire',
            'region': 'Eriador',
            'description': 'The peaceful homeland of the Hobbits.',
            'map_x': 1482.0,
            'map_y': 1158.0
        },
        {
            'name': 'Bree',
            'region': 'Eriador',
            'description': 'Bree was the chief village of Bree-land, a small wooded region near the intersection of the main north-south and east-west routes through Eriador. Bree-land was the only part of Middle-earth where Men and hobbits dwelt side by side and Bree had a large population of Hobbits.',
            'map_x': 1793.0,
            'map_y': 1163.0
        },
        {
            'name': 'Rivendell',
            'region': 'Eriador',
            'description': 'Rivendell was established by Elrond in S.A. 1697 as a refuge from Sauron after the Fall of Eregion. It remained Elrond\'s seat throughout the remainder of the Second Age and until the end of the Third Age, when he took the White Ship for Valinor.',
            'map_x': 2516.0,
            'map_y': 1123.0
        },
        {
            'name': 'Grey Havens',
            'region': 'Eriador',
            'description': 'Founded by the Elves of Lindon in S.A. 1, the Grey Havens were known for their good harbourage and many ships; these were used by any of the Eldar to leave Middle-earth for Eressëa or Valinor.',
            'map_x': 1047.0,
            'map_y': 1186.0
        },
        {
            'name': 'Weathertop',
            'region': 'Eriador',
            'description': 'In T.A.3018, Amun Sûl was the scene of two fights involving the Nazgûl: one with Gandalf on October 3 and one with the Ring-bearer three days later.',
            'map_x': 2000.0,
            'map_y': 1158.0
        },
        # Rhovanion
        {
            'name': 'Esgaroth',
            'region': 'Rhovanion',
            'description': 'Lake-Town was the township of the Lake-men in Wilderland. The town was constructed entirely of wood and stood upon wooden pillars sunk into the bed of the Long Lake, as a protection against the dragon Smaug, who dwelt nearby in the Lonely Mountain.',
            'map_x': 3418.0,
            'map_y': 885.0
        },
        {
            'name': 'Erebor',
            'region': 'Rhovanion',
            'description': 'The Longbeards had control of Erebor since at least the early Second Age. With the awakening of Durin\'s Bane in the capital of Khazad-dûm, Thráin I led a group of Dwarves to Erebor. Once there, the dwarves dug caves and halls to form an underground city, thus establishing the Kingdom under the Mountain in T.A. 1999.',
            'map_x': 3405.0,
            'map_y': 825.0
        },
        {
            'name': 'Lothlórien',
            'region': 'Rhovanion',
            'description': 'Lothlórien (or Lórien) was a kingdom of Silvan Elves on the eastern side of the Hithaeglir. It was considered one of the most beautiful and "elvish" places in Middle-earth during the Third Age, and had the only mallorn-trees east of the sea.',
            'map_x': 2666.0,
            'map_y': 1679.0
        },
        {
            'name': 'Elvenking\'s Hall',
            'region': 'Rhovanion',
            'description': 'Elvenking\'s Hall were a cave system in northern Mirkwood, in which King Thranduil and many of the Elves of Mirkwood lived during most of the Third Age and into the Fourth Age.',
            'map_x': 3311.0,
            'map_y': 849.0
        },
        {
            'name': 'Dol Guldur',
            'region': 'Rhovanion',
            'description': 'Dol Guldur ("Hill of Sorcery" in Sindarin), also called "the dungeons of the Necromancer", was a stronghold of Sauron located in the south of Mirkwood.',
            'map_x': 3014.0,
            'map_y': 1629.0
        },
        {
            'name': 'Edoras',
            'region': 'Rhovanion',
            'description': 'Edoras was the capital of Rohan that held the Golden Hall of Meduseld. Rohan\'s first capital was at Aldburg in the Folde, until King Eorl the Young or his son Brego built Edoras in T.A. 2569.',
            'map_x': 2589.0,
            'map_y': 2383.0
        },
        {
            'name': 'Rohan',
            'region': 'Rhovanion',
            'description': 'The land of the Horse-lords.',
            'map_x': 2589.0,
            'map_y': 2383.0
        },
        {
            'name': 'Helm\'s Deep',
            'region': 'Rhovanion',
            'description': 'Helm\'s Deep was a large valley gorge in the north-western Ered Nimrais (White Mountains) below the Thrihyrne. It was actually the name of the whole defensive system including its major defensive structure, the Hornburg.',
            'map_x': 2423.0,
            'map_y': 2321.0
        },
        {
            'name': 'Beorn\'s Hall',
            'region': 'Rhovanion',
            'description': 'Beorn\'s Hall was the home of Beorn, a powerful Skin-changer. Beorn hosted and aided Thorin and Company during their Quest for Erebor.',
            'map_x': 2871.0,
            'map_y': 1016.0
        },
        {
            'name': 'Dale',
            'region': 'Rhovanion',
            'description': 'Dale was a great city of the Northmen which was destroyed by Smaug and rebuilt as the capital of a great kingdom after his demise.',
            'map_x': 3430.0,
            'map_y': 855.0
        },
        # Misty Mountains
        {
            'name': 'Moria',
            'region': 'Misty Mountains',
            'description': 'Khazad-dûm was the grandest and most famous of the mansions of the Dwarves. There, for many thousands of years, a thriving Dwarvish community created the greatest city ever known.',
            'map_x': 2492.0,
            'map_y': 1505.0
        },
        {
            'name': 'Goblin-town',
            'region': 'Misty Mountains',
            'description': 'Goblin-town was a Goblin dwelling under the Misty Mountains, which was ruled by the Great Goblin. Goblin-town was a series of tunnels and caverns, which went all the way through the mountains, with a "back door" (the Goblin-gate) near the Eagle\'s Eyrie in Wilderland, which served as a means of escape, and an access to the Wilderland.',
            'map_x': 2647.0,
            'map_y': 980.0
        },
        # Mordor
        {
            'name': 'Mount Doom',
            'region': 'Mordor',
            'description': 'Melkor created Mount Doom in the First Age. When Sauron chose the land of Mordor as his dwelling-place in the Second Age, Orodruin was the reason for his choice. The mountain erupted in S.A. 3429, signalling Sauron\'s attack on Gondor and it took the name Amon Amarth, "Mount Doom". This is where the One Ring was forged by Sauron, and where it was destroyed by Gollum.',
            'map_x': 3606.0,
            'map_y': 2603.0
        },
        {
            'name': 'Mordor',
            'region': 'Mordor',
            'description': 'The dark land of Sauron, where the One Ring was forged.',
            'map_x': 3606.0,
            'map_y': 2603.0
        },
        {
            'name': 'Minas Morgul',
            'region': 'Mordor',
            'description': 'Minas Morgul (originally called Minas Ithil) was the twin city of Minas Tirith before its fall to the forces of Sauron in the Third Age. It then became the stronghold of the Witch-king of Angmar until Sauron\'s defeat.',
            'map_x': 3424.0,
            'map_y': 2695.0
        },
        {
            'name': 'Black Gate',
            'region': 'Mordor',
            'description': 'The Black Gate was the main entrance into the land of Mordor. It was built by Sauron after he chose Mordor as a land to make into a stronghold in S.A. 1000.',
            'map_x': 3389.0,
            'map_y': 2377.0
        },
        {
            'name': 'Barad-dûr',
            'region': 'Mordor',
            'description': 'Barad-dûr, also known as the Dark Tower, was the chief fortress of Sauron, on the Plateau of Gorgoroth in Mordor. Sauron began to build Barad-dûr in around S.A. 1000, and completed his fortress after 600 years of the construction with the power of the Ring.',
            'map_x': 3750.0,
            'map_y': 2553.0
        },
        # Gondor
        {
            'name': 'Minas Tirith',
            'region': 'Gondor',
            'description': 'Minas Tirith was originally a fortress, Minas Anor, built in S.A. 3320 by the Faithful Númenóreans. From T.A. 1640 onwards it was the capital of the South-kingdom and the seat of its Kings and ruling Stewards.',
            'map_x': 3279.0,
            'map_y': 2707.0
        },
        {
            'name': 'Osgiliath',
            'region': 'Gondor',
            'description': 'Founded by Isildur and Anárion near the end of the Second Age, Osgiliath was designated the capital of the southern Númenórean kingdom in exile, Gondor. It stays so until the King\'s House was moved to the more secure Minas Anor in T.A. 1640.',
            'map_x': 3330.0,
            'map_y': 2700.0
        },
        {
            'name': 'Paths of the Dead',
            'region': 'Gondor',
            'description': 'The Paths of the Dead was a haunted underground passage through the White Mountains that led from Harrowdale in Rohan to Blackroot Vale in Gondor.',
            'map_x': 2605.0,
            'map_y': 2535.0
        },
        # Isengard
        {
            'name': 'Isengard',
            'region': 'Isengard',
            'description': 'Isengard was one of the three major fortresses of Gondor, and held within it one of the realm\'s palantíri. In the latter half of the Third Age, the stronghold came into the possession of Saruman, becoming his home and personal domain until his defeat in the War of the Ring.',
            'map_x': 2335.0,
            'map_y': 2117.0
        },
        # Angmar
        {
            'name': 'Carn Dûm',
            'region': 'Angmar',
            'description': 'Carn Dûm was the chief fortress of the realm of Angmar and the seat of its king until its defeat against the combined armies of Gondor, Lindon and Arnor in T.A. 1974.',
            'map_x': 2115.0,
            'map_y': 523.0
        },
        {
            'name': 'Mount Gram',
            'region': 'Angmar',
            'description': 'Mount Gram was inhabited by Orcs led by their King Golfimbul. In T.A. 2747 they attacked much of northern Eriador, but were defeated in the Battle of Greenfields.',
            'map_x': 2353.0,
            'map_y': 746.0
        }
    ]
    
    locations = []
    for data in locations_data:
        location = Location.query.filter_by(name=data['name']).first()
        if not location:
            location = Location(**data)
            db.session.add(location)
            locations.append(location)
        else:
            # Update existing location with coordinates if missing
            if location.map_x is None or location.map_y is None:
                location.map_x = data.get('map_x')
                location.map_y = data.get('map_y')
            locations.append(location)
    
    db.session.commit()
    return locations

def seed_users(members: List[Member]) -> List[User]:
    """Create user accounts for Fellowship members."""
    users = []
    default_password = 'fellowship123'  # Simple password for MVP
    
    for member in members:
        user = User.query.filter_by(username=member.name.lower().replace(' ', '_')).first()
        if not user:
            user = User(
                username=member.name.lower().replace(' ', '_'),
                email=f"{member.name.lower().replace(' ', '_')}@fellowship.com",
                role=member.name
            )
            user.set_password(default_password)
            db.session.add(user)
            users.append(user)
        else:
            users.append(user)
    
    db.session.commit()
    return users

def seed_quests(locations: List[Location], users: List[User]) -> List[Quest]:
    """Create initial quests with epic descriptions and LOTR attributes."""
    quests_data = [
        {
            'title': 'Destroy the One Ring',
            'description': 'Journey to the fires of Mount Doom and cast the Ring into the flames where it was forged. The fate of Middle-earth depends on this quest.',
            'status': 'the_road_goes_ever_on',
            'quest_type': 'The Ring',
            'priority': 'Critical',
            'is_dark_magic': False,
            'character_quote': 'I will take the Ring, though I do not know the way.',
            'location_name': 'Mount Doom',  # Use specific location name
            'assignee_username': 'frodo_baggins'
        },
        {
            'title': 'Reach Rivendell',
            'description': 'Travel to Rivendell to seek counsel from Elrond. The Last Homely House awaits, where the Fellowship will be formed and the path forward decided.',
            'status': 'it_is_done',
            'quest_type': 'The Journey',
            'priority': 'Important',
            'is_dark_magic': False,
            'character_quote': 'The Road goes ever on and on...',
            'location_name': 'Rivendell',
            'assignee_username': 'frodo_baggins'
        },
        {
            'title': 'Cross the Misty Mountains',
            'description': 'Navigate through the treacherous Misty Mountains, avoiding the dangers that lurk in the shadows and the watchful eyes of the enemy.',
            'status': 'it_is_done',
            'quest_type': 'The Journey',
            'priority': 'Important',
            'is_dark_magic': False,
            'character_quote': None,
            'location_name': 'Moria',
            'assignee_username': 'aragorn'
        },
        {
            'title': 'Escape from Moria',
            'description': 'Flee from the depths of Moria as the Balrog awakens. The Fellowship must escape before the darkness consumes them.',
            'status': 'it_is_done',
            'quest_type': 'The Battle',
            'priority': 'Critical',
            'is_dark_magic': False,
            'character_quote': 'Fly, you fools!',
            'location_name': 'Moria',
            'assignee_username': 'gandalf'
        },
        {
            'title': 'Reach Mordor',
            'description': 'Travel to the dark land of Mordor, where Sauron\'s power is strongest. The journey grows more perilous with each step.',
            'status': 'the_road_goes_ever_on',
            'quest_type': 'The Journey',
            'priority': 'Critical',
            'is_dark_magic': False,
            'character_quote': None,
            'location_name': 'Mordor',  # Keep generic name, will match either "Mordor" or "Mount Doom"
            'assignee_username': 'frodo_baggins'
        },
        {
            'title': 'Fix the Broken Bridge',
            'description': 'Sauron\'s dark magic has corrupted the bridge. The Fellowship must restore it to continue their journey. This quest has been tainted by dark forces.',
            'status': 'the_shadow_falls',
            'quest_type': 'Dark Magic',
            'priority': 'Critical',
            'is_dark_magic': True,
            'character_quote': None,
            'location_name': 'Edoras',  # Use specific location name
            'assignee_username': 'samwise_gamgee'
        },
        {
            'title': 'Rescue Merry and Pippin',
            'description': 'The Fellowship must rescue the captured Hobbits from the Uruk-hai. Time is running out, and the fate of our friends hangs in the balance.',
            'status': 'not_yet_begun',
            'quest_type': 'The Fellowship',
            'priority': 'Important',
            'is_dark_magic': False,
            'character_quote': None,
            'location_name': 'Edoras',  # Use specific location name
            'assignee_username': 'aragorn'
        },
        {
            'title': 'Defend Helm\'s Deep',
            'description': 'Stand with the people of Rohan as they face the armies of Saruman. The battle will be fierce, but courage and unity will prevail.',
            'status': 'not_yet_begun',
            'quest_type': 'The Battle',
            'priority': 'Critical',
            'is_dark_magic': False,
            'character_quote': None,
            'location_name': 'Helm\'s Deep',  # Use specific location name
            'assignee_username': 'aragorn'
        }
    ]
    
    quests = []
    for data in quests_data:
        # Find location
        location = next((loc for loc in locations if loc.name == data['location_name']), None)
        # Find user
        user = next((u for u in users if u.username == data['assignee_username']), None)
        
        quest = Quest.query.filter_by(title=data['title']).first()
        if not quest:
            quest = Quest(
                title=data['title'],
                description=data['description'],
                status=data['status'],
                quest_type=data.get('quest_type'),
                priority=data.get('priority'),
                is_dark_magic=data.get('is_dark_magic', False),
                character_quote=data.get('character_quote'),
                location_id=location.id if location else None,
                assigned_to=user.id if user else None
            )
            # Set completed_at if quest is done
            if data['status'] == 'it_is_done':
                from datetime import datetime
                quest.completed_at = datetime.utcnow()
            db.session.add(quest)
            quests.append(quest)
        else:
            # Update existing quest with new fields if they're missing
            if quest.quest_type is None and data.get('quest_type'):
                quest.quest_type = data.get('quest_type')
            if quest.priority is None and data.get('priority'):
                quest.priority = data.get('priority')
            if quest.is_dark_magic is False and data.get('is_dark_magic'):
                quest.is_dark_magic = data.get('is_dark_magic')
            if quest.character_quote is None and data.get('character_quote'):
                quest.character_quote = data.get('character_quote')
            # Update location_id if missing or if location name matches
            if quest.location_id is None and location:
                quest.location_id = location.id
            elif quest.location_id is None:
                # Try to find location by name if not found initially
                location = next((loc for loc in locations if loc.name == data['location_name']), None)
                if location:
                    quest.location_id = location.id
            # Migrate old status values
            status_mapping = {
                'pending': 'not_yet_begun',
                'in_progress': 'the_road_goes_ever_on',
                'completed': 'it_is_done',
                'blocked': 'the_shadow_falls'
            }
            if quest.status in status_mapping:
                quest.status = status_mapping[quest.status]
            quests.append(quest)
    
    db.session.commit()
    return quests

def seed_database(app: Flask) -> None:
    """Seed the database with initial data."""
    with app.app_context():
        # Check if database is already seeded
        if User.query.first() is not None:
            print("Database already seeded, skipping...")
            return
        
        print("Seeding database...")
        
        # Seed in order: members -> locations -> users -> quests
        members = seed_members()
        print(f"Seeded {len(members)} members")
        
        locations = seed_locations()
        print(f"Seeded {len(locations)} locations")
        
        users = seed_users(members)
        print(f"Seeded {len(users)} users")
        
        quests = seed_quests(locations, users)
        print(f"Seeded {len(quests)} quests")
        
        print("Database seeding completed!")
