#!/usr/bin/env python3
"""
Migrate JSON data from src/data/unmunged to MongoDB

This script reads all your existing JSON files and imports them into MongoDB.

Usage:
    1. Make sure MongoDB is running and you have the connection string
    2. Create a .env file with MONGODB_URI
    3. Run: python scripts/migrate_to_mongodb.py
"""
import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv
import os

# Load environment variables
env_path = Path(__file__).parent.parent / '.env'
load_dotenv(env_path)

# Get MongoDB connection string from environment
MONGODB_URI = os.getenv('MONGODB_URI')
DATABASE_NAME = os.getenv('DATABASE_NAME', 'nu_choate_league')

if not MONGODB_URI:
    print("❌ Error: MONGODB_URI not found in .env file")
    print("Please create a .env file with your MongoDB connection string")
    sys.exit(1)


async def migrate_data():
    """Main migration function"""
    print("=" * 70)
    print("Nu Choate League - MongoDB Migration")
    print("=" * 70)
    print()
    
    # Connect to MongoDB
    print(f"Connecting to MongoDB...")
    try:
        client = AsyncIOMotorClient(MONGODB_URI)
        await client.admin.command('ping')
        print(f"✓ Connected to MongoDB successfully")
    except Exception as e:
        print(f"✗ Failed to connect to MongoDB: {e}")
        print("\nPlease check:")
        print("  1. MongoDB is running on your droplet")
        print("  2. Your connection string is correct in .env")
        print("  3. Firewall allows connections from your IP")
        sys.exit(1)
    
    db = client[DATABASE_NAME]
    
    # Get path to unmunged data
    unmunged_dir = Path(__file__).parent.parent / 'src' / 'data' / 'unmunged'
    
    if not unmunged_dir.exists():
        print(f"✗ Data directory not found: {unmunged_dir}")
        sys.exit(1)
    
    print(f"✓ Found data directory: {unmunged_dir}")
    print()
    
    # Statistics
    stats = {
        'leagues': 0,
        'rosters': 0,
        'users': 0,
        'matchups': 0,
        'transactions': 0,
        'drafts': 0,
        'brackets': 0,
        'players': 0
    }
    
    # Migrate each season
    season_dirs = [d for d in unmunged_dir.iterdir() if d.is_dir()]
    
    for season_dir in sorted(season_dirs):
        season = season_dir.name
        print(f"{'=' * 70}")
        print(f"Migrating Season: {season}")
        print(f"{'=' * 70}")
        
        # 1. Migrate league info
        league_info_path = season_dir / 'league_info.json'
        if league_info_path.exists():
            with open(league_info_path, 'r') as f:
                league_data = json.load(f)
                league_data['season'] = season
                league_data['created_at'] = datetime.utcnow()
                league_data['updated_at'] = datetime.utcnow()
                
                await db.leagues.update_one(
                    {'league_id': league_data['league_id'], 'season': season},
                    {'$set': league_data},
                    upsert=True
                )
                stats['leagues'] += 1
                print(f"  ✓ League info")
        
        # 2. Migrate rosters
        rosters_path = season_dir / 'rosters.json'
        if rosters_path.exists():
            with open(rosters_path, 'r') as f:
                rosters_data = json.load(f)
                for roster in rosters_data:
                    roster['season'] = season
                    roster['league_id'] = league_data.get('league_id')
                    roster['created_at'] = datetime.utcnow()
                    roster['updated_at'] = datetime.utcnow()
                    
                    await db.rosters.update_one(
                        {
                            'roster_id': roster['roster_id'],
                            'league_id': roster.get('league_id'),
                            'season': season
                        },
                        {'$set': roster},
                        upsert=True
                    )
                stats['rosters'] += len(rosters_data)
                print(f"  ✓ Rosters ({len(rosters_data)} teams)")
        
        # 3. Migrate users
        users_path = season_dir / 'users.json'
        if users_path.exists():
            with open(users_path, 'r') as f:
                users_data = json.load(f)
                for user in users_data:
                    user['created_at'] = datetime.utcnow()
                    user['updated_at'] = datetime.utcnow()
                    
                    await db.users.update_one(
                        {'user_id': user['user_id']},
                        {'$set': user, '$addToSet': {'leagues': league_data.get('league_id')}},
                        upsert=True
                    )
                stats['users'] += len(users_data)
                print(f"  ✓ Users ({len(users_data)} users)")
        
        # 4. Migrate draft
        draft_path = season_dir / 'draft.json'
        if draft_path.exists():
            with open(draft_path, 'r') as f:
                draft_data = json.load(f)
                for draft in draft_data:
                    draft['season'] = season
                    draft['league_id'] = league_data.get('league_id')
                    draft['created_at'] = datetime.utcnow()
                    draft['updated_at'] = datetime.utcnow()
                    
                    await db.drafts.update_one(
                        {'draft_id': draft['draft_id']},
                        {'$set': draft},
                        upsert=True
                    )
                    stats['drafts'] += 1
                print(f"  ✓ Draft")
        
        # 5. Migrate playoff brackets
        winners_bracket_path = season_dir / 'playoffs_winnersbracket.json'
        if winners_bracket_path.exists():
            with open(winners_bracket_path, 'r') as f:
                bracket_data = json.load(f)
                if bracket_data:
                    for bracket in bracket_data:
                        bracket['season'] = season
                        bracket['league_id'] = league_data.get('league_id')
                        bracket['bracket_type'] = 'winners'
                        bracket['created_at'] = datetime.utcnow()
                        bracket['updated_at'] = datetime.utcnow()
                        
                        await db.brackets.update_one(
                            {'bracket_id': bracket.get('bracket_id'), 'season': season},
                            {'$set': bracket},
                            upsert=True
                        )
                        stats['brackets'] += 1
                    print(f"  ✓ Winners bracket")
        
        losers_bracket_path = season_dir / 'playoffs_losersbracket.json'
        if losers_bracket_path.exists():
            with open(losers_bracket_path, 'r') as f:
                bracket_data = json.load(f)
                if bracket_data:
                    for bracket in bracket_data:
                        bracket['season'] = season
                        bracket['league_id'] = league_data.get('league_id')
                        bracket['bracket_type'] = 'losers'
                        bracket['created_at'] = datetime.utcnow()
                        bracket['updated_at'] = datetime.utcnow()
                        
                        await db.brackets.update_one(
                            {'bracket_id': bracket.get('bracket_id'), 'season': season},
                            {'$set': bracket},
                            upsert=True
                        )
                        stats['brackets'] += 1
                    print(f"  ✓ Losers bracket")
        
        # 6. Migrate weekly data
        week_dirs = sorted([d for d in season_dir.iterdir() if d.is_dir() and d.name.startswith('week_')])
        
        if week_dirs:
            print(f"  Migrating weekly data:")
        
        for week_dir in week_dirs:
            week_num = int(week_dir.name.split('_')[1])
            
            # Matchups
            matchups_path = week_dir / 'matchups.json'
            if matchups_path.exists():
                with open(matchups_path, 'r') as f:
                    matchups_data = json.load(f)
                    for matchup in matchups_data:
                        matchup['season'] = season
                        matchup['week'] = week_num
                        matchup['league_id'] = league_data.get('league_id')
                        matchup['created_at'] = datetime.utcnow()
                        matchup['updated_at'] = datetime.utcnow()
                        
                        await db.matchups.update_one(
                            {
                                'league_id': matchup['league_id'],
                                'season': season,
                                'week': week_num,
                                'roster_id': matchup['roster_id']
                            },
                            {'$set': matchup},
                            upsert=True
                        )
                    stats['matchups'] += len(matchups_data)
            
            # Transactions
            transactions_path = week_dir / 'transactions.json'
            if transactions_path.exists():
                with open(transactions_path, 'r') as f:
                    transactions_data = json.load(f)
                    for transaction in transactions_data:
                        transaction['season'] = season
                        transaction['week'] = week_num
                        transaction['league_id'] = league_data.get('league_id')
                        transaction['created_at'] = datetime.utcnow()
                        transaction['updated_at'] = datetime.utcnow()
                        
                        # Use transaction_id as unique identifier
                        await db.transactions.update_one(
                            {
                                'transaction_id': transaction.get('transaction_id'),
                                'league_id': transaction['league_id']
                            },
                            {'$set': transaction},
                            upsert=True
                        )
                    stats['transactions'] += len(transactions_data)
            
            print(f"    ✓ Week {week_num}")
        
        print()
    
    # 7. Migrate players (shared across all seasons)
    print(f"{'=' * 70}")
    print(f"Migrating Players Database")
    print(f"{'=' * 70}")
    
    players_path = unmunged_dir / 'players.json'
    if players_path.exists():
        with open(players_path, 'r') as f:
            players_data = json.load(f)
            
            # Players data is a dict with player_id as key
            player_count = 0
            for player_id, player_info in players_data.items():
                player_info['player_id'] = player_id
                player_info['created_at'] = datetime.utcnow()
                player_info['updated_at'] = datetime.utcnow()
                
                await db.players.update_one(
                    {'player_id': player_id},
                    {'$set': player_info},
                    upsert=True
                )
                player_count += 1
            
            stats['players'] = player_count
            print(f"  ✓ Players ({player_count} players)")
    
    print()
    
    # 8. Create indexes for better query performance
    print(f"{'=' * 70}")
    print(f"Creating Database Indexes")
    print(f"{'=' * 70}")
    
    await db.leagues.create_index([("league_id", 1), ("season", 1)])
    print("  ✓ leagues: (league_id, season)")
    
    await db.rosters.create_index([("league_id", 1), ("season", 1)])
    print("  ✓ rosters: (league_id, season)")
    
    await db.rosters.create_index("owner_id")
    print("  ✓ rosters: (owner_id)")
    
    await db.matchups.create_index([("league_id", 1), ("season", 1), ("week", 1)])
    print("  ✓ matchups: (league_id, season, week)")
    
    await db.matchups.create_index("roster_id")
    print("  ✓ matchups: (roster_id)")
    
    await db.users.create_index("user_id", unique=True)
    print("  ✓ users: (user_id) [unique]")
    
    await db.players.create_index("player_id", unique=True)
    print("  ✓ players: (player_id) [unique]")
    
    await db.transactions.create_index([("league_id", 1), ("season", 1), ("week", 1)])
    print("  ✓ transactions: (league_id, season, week)")
    
    await db.drafts.create_index("draft_id", unique=True)
    print("  ✓ drafts: (draft_id) [unique]")
    
    print()
    
    # Print summary
    print(f"{'=' * 70}")
    print(f"Migration Complete!")
    print(f"{'=' * 70}")
    print()
    print(f"Summary:")
    print(f"  • Leagues:      {stats['leagues']:>6}")
    print(f"  • Rosters:      {stats['rosters']:>6}")
    print(f"  • Users:        {stats['users']:>6}")
    print(f"  • Matchups:     {stats['matchups']:>6}")
    print(f"  • Transactions: {stats['transactions']:>6}")
    print(f"  • Drafts:       {stats['drafts']:>6}")
    print(f"  • Brackets:     {stats['brackets']:>6}")
    print(f"  • Players:      {stats['players']:>6}")
    print()
    print(f"Next steps:")
    print(f"  1. Verify data in MongoDB: mongosh '{MONGODB_URI}'")
    print(f"  2. Test API locally: cd backend && uvicorn app.main:app --reload")
    print(f"  3. Deploy to DigitalOcean App Platform")
    print()
    
    client.close()


if __name__ == "__main__":
    asyncio.run(migrate_data())
