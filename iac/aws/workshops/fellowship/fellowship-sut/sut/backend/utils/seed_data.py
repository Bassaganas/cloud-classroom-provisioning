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
    """Create Middle-earth locations."""
    locations_data = [
        {
            'name': 'The Shire',
            'region': 'Eriador',
            'description': 'The peaceful homeland of the Hobbits.'
        },
        {
            'name': 'Rivendell',
            'region': 'Eriador',
            'description': 'The Last Homely House, home of Elrond.'
        },
        {
            'name': 'Moria',
            'region': 'Misty Mountains',
            'description': 'The ancient Dwarven kingdom, now overrun by darkness.'
        },
        {
            'name': 'Lothlórien',
            'region': 'Rhovanion',
            'description': 'The Golden Wood, realm of Galadriel and Celeborn.'
        },
        {
            'name': 'Rohan',
            'region': 'Rhovanion',
            'description': 'The land of the Horse-lords.'
        },
        {
            'name': 'Mordor',
            'region': 'Mordor',
            'description': 'The dark land of Sauron, where the One Ring was forged.'
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
    """Create initial quests."""
    quests_data = [
        {
            'title': 'Destroy the One Ring',
            'description': 'Journey to Mount Doom and destroy the One Ring in the fires where it was forged.',
            'status': 'in_progress',
            'location_name': 'Mordor',
            'assignee_username': 'frodo_baggins'
        },
        {
            'title': 'Reach Rivendell',
            'description': 'Travel to Rivendell to seek counsel from Elrond.',
            'status': 'completed',
            'location_name': 'Rivendell',
            'assignee_username': 'frodo_baggins'
        },
        {
            'title': 'Cross the Misty Mountains',
            'description': 'Navigate through the treacherous Misty Mountains.',
            'status': 'completed',
            'location_name': 'Moria',
            'assignee_username': 'aragorn'
        },
        {
            'title': 'Escape from Moria',
            'description': 'Survive the dangers of the ancient Dwarven kingdom.',
            'status': 'completed',
            'location_name': 'Moria',
            'assignee_username': 'gandalf'
        },
        {
            'title': 'Reach Mordor',
            'description': 'Travel to the dark land of Mordor to complete the quest.',
            'status': 'in_progress',
            'location_name': 'Mordor',
            'assignee_username': 'frodo_baggins'
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
                location_id=location.id if location else None,
                assigned_to=user.id if user else None
            )
            db.session.add(quest)
            quests.append(quest)
        else:
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
