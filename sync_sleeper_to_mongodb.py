#!/usr/bin/env python3
"""
Sleeper API to MongoDB Sync Script

Fetches data from Sleeper API, stores raw data in MongoDB, and processes incrementally.
Only fetches and processes new weeks that haven't been processed yet.

Usage:
    python sync_sleeper_to_mongodb.py [--league-id LEAGUE_ID] [--env ENV]
    
Environment variables:
    MONGODB_URI - MongoDB connection string (required)
    SLEEPER_LEAGUE_ID - Default league ID (optional, can override with --league-id)
"""

import os
import sys
import json
import time
import argparse
import logging
import statistics
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

import requests
from pymongo import MongoClient, UpdateOne
from pymongo.errors import ConnectionFailure, OperationFailure

# Sleeper API configuration
SLEEPER_API_BASE_URL = 'https://api.sleeper.app/v1'

# API retry configuration
MAX_RETRIES = 3
INITIAL_RETRY_DELAY = 1
MAX_RETRY_DELAY = 10

# Default league ID
DEFAULT_LEAGUE_ID = '1251998020954763264'

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('sleeper_sync')


def call_api(url: str, max_retries: int = MAX_RETRIES) -> Optional[dict]:
    """Make HTTP API GET request with retry logic."""
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            last_exception = e
            if attempt < max_retries:
                delay = min(INITIAL_RETRY_DELAY * (2 ** attempt), MAX_RETRY_DELAY)
                logger.warning(f"API call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. Retrying in {delay}s...")
                time.sleep(delay)
            else:
                logger.error(f"API call failed after {max_retries + 1} attempts: {e}")
    
    raise Exception(f"Failed to fetch {url}: {last_exception}")


def get_last_processed_week(db, league_id: str, season: str) -> int:
    """Get the last processed week for a league/season from metadata."""
    metadata = db.metadata.find_one({
        'league_id': league_id,
        'season': season
    })
    
    if metadata:
        return metadata.get('last_processed_week', 0)
    return 0


def update_last_processed_week(db, league_id: str, season: str, week: int):
    """Update the last processed week in metadata."""
    db.metadata.update_one(
        {'league_id': league_id, 'season': season},
        {
            '$set': {
                'last_processed_week': week,
                'last_updated': datetime.utcnow()
            }
        },
        upsert=True
    )


def fetch_league_info(league_id: str) -> dict:
    """Fetch league information from Sleeper API."""
    url = f"{SLEEPER_API_BASE_URL}/league/{league_id}"
    return call_api(url)


def fetch_rosters(league_id: str) -> List[dict]:
    """Fetch rosters from Sleeper API."""
    url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/rosters"
    return call_api(url) or []


def fetch_users(league_id: str) -> List[dict]:
    """Fetch users from Sleeper API."""
    url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/users"
    return call_api(url) or []


def fetch_matchups(league_id: str, week: int) -> List[dict]:
    """Fetch matchups for a specific week."""
    url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/matchups/{week}"
    return call_api(url) or []


def fetch_transactions(league_id: str, week: int) -> List[dict]:
    """Fetch transactions for a specific week."""
    url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/transactions/{week}"
    return call_api(url) or []


def fetch_drafts(league_id: str) -> List[dict]:
    """Fetch drafts from Sleeper API."""
    url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/drafts"
    drafts = call_api(url) or []
    
    # Fetch picks for each draft
    for draft in drafts:
        draft_id = draft.get('draft_id')
        if draft_id:
            try:
                picks_url = f"{SLEEPER_API_BASE_URL}/draft/{draft_id}/picks"
                draft['picks'] = call_api(picks_url) or []
            except Exception as e:
                logger.warning(f"Failed to fetch picks for draft {draft_id}: {e}")
                draft['picks'] = []
    
    return drafts


def fetch_playoff_brackets(league_id: str) -> Tuple[Optional[dict], Optional[dict]]:
    """Fetch playoff brackets from Sleeper API."""
    winners_url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/winners_bracket"
    losers_url = f"{SLEEPER_API_BASE_URL}/league/{league_id}/losers_bracket"
    
    winners = call_api(winners_url)
    losers = call_api(losers_url)
    
    return winners, losers


def store_league_info(db, league_id: str, league_info: dict):
    """Store league information in MongoDB."""
    league_info['league_id'] = league_id
    league_info['last_updated'] = datetime.utcnow()
    
    db.leagues.update_one(
        {'league_id': league_id, 'season': league_info.get('season')},
        {'$set': league_info},
        upsert=True
    )


def store_rosters(db, league_id: str, season: str, rosters: List[dict]):
    """Store rosters in MongoDB."""
    operations = []
    for roster in rosters:
        roster['league_id'] = league_id
        roster['season'] = season
        roster['last_updated'] = datetime.utcnow()
        operations.append(
            UpdateOne(
                {'league_id': league_id, 'season': season, 'roster_id': roster.get('roster_id')},
                {'$set': roster},
                upsert=True
            )
        )
    
    if operations:
        db.rosters.bulk_write(operations)


def store_users(db, league_id: str, users: List[dict]):
    """Store users in MongoDB."""
    operations = []
    for user in users:
        user['league_id'] = league_id
        user['last_updated'] = datetime.utcnow()
        operations.append(
            UpdateOne(
                {'league_id': league_id, 'user_id': user.get('user_id')},
                {'$set': user},
                upsert=True
            )
        )
    
    if operations:
        db.users.bulk_write(operations)


def store_matchups(db, league_id: str, season: str, week: int, matchups: List[dict]):
    """Store matchups for a specific week."""
    operations = []
    for matchup in matchups:
        matchup['league_id'] = league_id
        matchup['season'] = season
        matchup['week'] = week
        matchup['last_updated'] = datetime.utcnow()
        operations.append(
            UpdateOne(
                {
                    'league_id': league_id,
                    'season': season,
                    'week': week,
                    'roster_id': matchup.get('roster_id'),
                    'matchup_id': matchup.get('matchup_id')
                },
                {'$set': matchup},
                upsert=True
            )
        )
    
    if operations:
        db.matchups.bulk_write(operations)


def store_transactions(db, league_id: str, season: str, week: int, transactions: List[dict]):
    """Store transactions for a specific week."""
    operations = []
    for transaction in transactions:
        transaction['league_id'] = league_id
        transaction['season'] = season
        transaction['week'] = week
        transaction['last_updated'] = datetime.utcnow()
        operations.append(
            UpdateOne(
                {
                    'league_id': league_id,
                    'season': season,
                    'week': week,
                    'transaction_id': transaction.get('transaction_id')
                },
                {'$set': transaction},
                upsert=True
            )
        )
    
    if operations:
        db.transactions.bulk_write(operations)


def store_drafts(db, league_id: str, season: str, drafts: List[dict]):
    """Store drafts in MongoDB."""
    operations = []
    for draft in drafts:
        draft['league_id'] = league_id
        draft['season'] = season
        draft['last_updated'] = datetime.utcnow()
        operations.append(
            UpdateOne(
                {'league_id': league_id, 'season': season, 'draft_id': draft.get('draft_id')},
                {'$set': draft},
                upsert=True
            )
        )
    
    if operations:
        db.drafts.bulk_write(operations)


def store_playoff_brackets(db, league_id: str, season: str, winners: Optional[dict], losers: Optional[dict]):
    """Store playoff brackets in MongoDB."""
    if winners:
        winners['league_id'] = league_id
        winners['season'] = season
        winners['bracket_type'] = 'winners'
        winners['last_updated'] = datetime.utcnow()
        db.playoff_brackets.update_one(
            {'league_id': league_id, 'season': season, 'bracket_type': 'winners'},
            {'$set': winners},
            upsert=True
        )
    
    if losers:
        losers['league_id'] = league_id
        losers['season'] = season
        losers['bracket_type'] = 'losers'
        losers['last_updated'] = datetime.utcnow()
        db.playoff_brackets.update_one(
            {'league_id': league_id, 'season': season, 'bracket_type': 'losers'},
            {'$set': losers},
            upsert=True
        )


def calculate_standings_incremental(
    db,
    league_id: str,
    season: str,
    week: int,
    rosters_map: Dict[int, Dict],
    league_average_match: int = 0
) -> Dict[int, Dict]:
    """Calculate standings incrementally for a specific week."""
    # Get previous week's standings snapshot
    previous_snapshot = db.standings_snapshots.find_one(
        {
            'league_id': league_id,
            'season': season,
            'week': week - 1
        },
        sort=[('week', -1)]
    )
    
    # Initialize standings
    if previous_snapshot:
        standings = previous_snapshot.get('standings', {})
        # Deep copy to avoid mutation
        standings = {
            roster_id: {
                'roster_id': stats['roster_id'],
                'team_name': stats['team_name'],
                'wins': stats['wins'],
                'losses': stats['losses'],
                'ties': stats['ties'],
                'pf': stats['pf'],
                'pa': stats['pa'],
                'transaction_count': stats.get('transaction_count', 0)
            }
            for roster_id, stats in standings.items()
        }
    else:
        # Initialize from rosters
        standings = {}
        for roster_id, roster_info in rosters_map.items():
            standings[roster_id] = {
                'roster_id': roster_id,
                'team_name': roster_info.get('team_name', f'Team {roster_id}'),
                'wins': 0,
                'losses': 0,
                'ties': 0,
                'pf': 0.0,
                'pa': 0.0,
                'transaction_count': 0
            }
    
    # Get matchups for this week
    matchups = list(db.matchups.find({
        'league_id': league_id,
        'season': season,
        'week': week
    }))
    
    if not matchups:
        logger.warning(f"No matchups found for week {week}")
        return standings
    
    # Group matchups by matchup_id
    matchup_groups = defaultdict(list)
    for matchup in matchups:
        matchup_id = matchup.get('matchup_id')
        if matchup_id:
            matchup_groups[matchup_id].append(matchup)
    
    # Collect scores for median calculation
    all_scores = []
    
    # Process matchups
    for matchup_id, matchup_list in matchup_groups.items():
        if len(matchup_list) == 2:
            team1 = matchup_list[0]
            team2 = matchup_list[1]
            
            roster_id1 = team1.get('roster_id')
            roster_id2 = team2.get('roster_id')
            points1 = team1.get('points', 0.0)
            points2 = team2.get('points', 0.0)
            
            if roster_id1 and roster_id2 and roster_id1 in standings and roster_id2 in standings:
                all_scores.append(points1)
                all_scores.append(points2)
                
                # Update points
                standings[roster_id1]['pf'] += points1
                standings[roster_id1]['pa'] += points2
                standings[roster_id2]['pf'] += points2
                standings[roster_id2]['pa'] += points1
                
                # Update W-L
                if points1 > points2:
                    standings[roster_id1]['wins'] += 1
                    standings[roster_id2]['losses'] += 1
                elif points2 > points1:
                    standings[roster_id1]['losses'] += 1
                    standings[roster_id2]['wins'] += 1
                else:
                    standings[roster_id1]['ties'] += 1
                    standings[roster_id2]['ties'] += 1
    
    # Apply median scoring if enabled
    if league_average_match == 1 and all_scores:
        median_score = statistics.median(all_scores)
        
        for matchup_id, matchup_list in matchup_groups.items():
            if len(matchup_list) == 2:
                for team in matchup_list:
                    roster_id = team.get('roster_id')
                    points = team.get('points', 0.0)
                    
                    if roster_id and roster_id in standings:
                        if points > median_score:
                            standings[roster_id]['wins'] += 1
                        elif points < median_score:
                            standings[roster_id]['losses'] += 1
                        else:
                            standings[roster_id]['ties'] += 1
    
    # Count transactions
    transactions = list(db.transactions.find({
        'league_id': league_id,
        'season': season,
        'week': week,
        'status': 'complete'
    }))
    
    roster_transaction_counts = defaultdict(int)
    for transaction in transactions:
        roster_ids = transaction.get('roster_ids', [])
        for roster_id in roster_ids:
            roster_transaction_counts[roster_id] += 1
    
    for roster_id, count in roster_transaction_counts.items():
        if roster_id in standings:
            standings[roster_id]['transaction_count'] += count
    
    return standings


def store_standings_snapshot(db, league_id: str, season: str, week: int, standings: Dict[int, Dict]):
    """Store standings snapshot for a specific week."""
    snapshot = {
        'league_id': league_id,
        'season': season,
        'week': week,
        'standings': standings,
        'created_at': datetime.utcnow()
    }
    
    db.standings_snapshots.update_one(
        {'league_id': league_id, 'season': season, 'week': week},
        {'$set': snapshot},
        upsert=True
    )


def sync_league(league_id: str, db, force_full: bool = False):
    """Sync a single league from Sleeper API to MongoDB."""
    logger.info(f"Syncing league {league_id}...")
    
    # Fetch league info
    league_info = fetch_league_info(league_id)
    if not league_info:
        logger.error(f"Failed to fetch league info for {league_id}")
        return False
    
    season = str(league_info.get('season'))
    if not season:
        logger.error(f"No season found in league info")
        return False
    
    logger.info(f"Processing season {season}")
    
    # Store league info
    store_league_info(db, league_id, league_info)
    
    # Fetch and store static data (rosters, users, drafts)
    logger.info("Fetching rosters...")
    rosters = fetch_rosters(league_id)
    store_rosters(db, league_id, season, rosters)
    
    # Build rosters map for standings calculation
    rosters_map = {}
    users = fetch_users(league_id)
    store_users(db, league_id, users)
    
    # Create user_id to team_name mapping
    users_map = {user.get('user_id'): user for user in users}
    for roster in rosters:
        roster_id = roster.get('roster_id')
        owner_id = roster.get('owner_id')
        if roster_id and owner_id:
            user = users_map.get(owner_id, {})
            rosters_map[roster_id] = {
                'team_name': user.get('display_name', f'Team {owner_id}'),
                'owner_id': owner_id
            }
    
    # Fetch and store drafts
    logger.info("Fetching drafts...")
    drafts = fetch_drafts(league_id)
    store_drafts(db, league_id, season, drafts)
    
    # Fetch playoff brackets
    logger.info("Fetching playoff brackets...")
    winners, losers = fetch_playoff_brackets(league_id)
    store_playoff_brackets(db, league_id, season, winners, losers)
    
    # Get current week and last processed week
    current_week = league_info.get('settings', {}).get('last_scored_leg', 0)
    last_processed_week = 0 if force_full else get_last_processed_week(db, league_id, season)
    
    league_average_match = league_info.get('settings', {}).get('league_average_match', 0)
    
    logger.info(f"Current week: {current_week}, Last processed: {last_processed_week}")
    
    # Process weeks incrementally
    weeks_to_process = range(last_processed_week + 1, current_week + 1) if current_week > last_processed_week else []
    
    if not weeks_to_process:
        logger.info("No new weeks to process")
        return True
    
    logger.info(f"Processing weeks {min(weeks_to_process)} to {max(weeks_to_process)}...")
    
    for week in weeks_to_process:
        logger.info(f"Processing week {week}...")
        
        # Fetch and store matchups
        matchups = fetch_matchups(league_id, week)
        if matchups:
            store_matchups(db, league_id, season, week, matchups)
            time.sleep(0.5)  # Rate limiting
        
        # Fetch and store transactions
        transactions = fetch_transactions(league_id, week)
        if transactions:
            store_transactions(db, league_id, season, week, transactions)
            time.sleep(0.5)  # Rate limiting
        
        # Calculate standings incrementally
        standings = calculate_standings_incremental(
            db, league_id, season, week, rosters_map, league_average_match
        )
        
        # Store standings snapshot
        store_standings_snapshot(db, league_id, season, week, standings)
        
        # Update last processed week
        update_last_processed_week(db, league_id, season, week)
        
        logger.info(f"Completed week {week}")
    
    logger.info(f"Successfully synced league {league_id} for season {season}")
    return True


def sync_all_seasons(league_id: str, db, force_full: bool = False):
    """Sync all seasons for a league by following previous_league_id chain."""
    processed_leagues = set()
    current_league_id = league_id
    
    while current_league_id and current_league_id not in processed_leagues:
        processed_leagues.add(current_league_id)
        
        # Sync current league
        success = sync_league(current_league_id, db, force_full)
        if not success:
            logger.error(f"Failed to sync league {current_league_id}")
            break
        
        # Get previous league ID
        league_info = fetch_league_info(current_league_id)
        if league_info:
            current_league_id = league_info.get('previous_league_id')
            if current_league_id:
                logger.info(f"Found previous league: {current_league_id}")
        else:
            break


def main():
    parser = argparse.ArgumentParser(description='Sync Sleeper API data to MongoDB')
    parser.add_argument('--league-id', type=str, help='Sleeper league ID')
    parser.add_argument('--env', type=str, choices=['dev', 'staging', 'prod'], default='dev',
                       help='Environment (determines database name)')
    parser.add_argument('--force-full', action='store_true',
                       help='Force full sync (reprocess all weeks)')
    
    args = parser.parse_args()
    
    # Get MongoDB URI from environment
    mongodb_uri = os.getenv('MONGODB_URI')
    if not mongodb_uri:
        logger.error("MONGODB_URI environment variable not set")
        sys.exit(1)
    
    # Get league ID
    league_id = args.league_id or os.getenv('SLEEPER_LEAGUE_ID', DEFAULT_LEAGUE_ID)
    
    # Determine database name based on environment
    db_names = {
        'dev': 'nu_choate_league_dev',
        'staging': 'nu_choate_league_staging',
        'prod': 'nu_choate_league_prod'
    }
    db_name = db_names[args.env]
    
    # Connect to MongoDB
    try:
        client = MongoClient(mongodb_uri)
        db = client[db_name]
        
        # Test connection
        client.admin.command('ping')
        logger.info(f"Connected to MongoDB database: {db_name}")
    except (ConnectionFailure, OperationFailure) as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        sys.exit(1)
    
    # Sync all seasons
    try:
        sync_all_seasons(league_id, db, force_full=args.force_full)
        logger.info("Sync completed successfully")
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        sys.exit(1)
    finally:
        client.close()


if __name__ == '__main__':
    main()

