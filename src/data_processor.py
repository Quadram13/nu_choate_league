"""Main data processor that orchestrates the data munging pipeline."""
import json
from pathlib import Path
from typing import Dict, List

from constants import (
    DEFAULT_LAST_SCORED_LEG,
    DEFAULT_PLAYOFF_WEEK_START
)
from mappers import (
    load_players_maps,
    load_users_map,
    load_rosters_map,
    get_player_name
)
from standings import (
    calculate_weekly_standings,
    calculate_weekly_standings_dict,
    standings_to_list
)
from recap_generator import (
    generate_weekly_recap,
    map_transactions
)
from postseason import (
    generate_postseason_recap,
    generate_weekly_postseason_recap
)


def process_drafts(
    season_unmunged: Path,
    season_munged: Path,
    players_map: Dict[str, str],
    users_map: Dict[str, Dict[str, str]]
) -> None:
    """
    Process draft data and organize by team.
    
    Args:
        season_unmunged: Path to unmunged season directory
        season_munged: Path to munged season directory
        players_map: Player ID to player name mapping
        users_map: User ID to user info mapping
    """
    drafts_path = season_unmunged / "draft.json"
    if not drafts_path.exists():
        print("  No draft.json file found, skipping draft processing")
        return
    
    with open(drafts_path, 'r') as f:
        drafts = json.load(f)
    
    if not drafts:
        print("  No drafts found in draft.json")
        return
    
    # Process the first draft (typically the main regular season draft)
    # If multiple drafts exist, we could extend this to handle all of them
    draft = drafts[0]
    picks = draft.get('picks', [])
    draft_order = draft.get('draft_order', {})
    
    if not picks:
        print("  No picks found in draft data")
        return
    
    # Organize picks by team
    teams_draft_data = {}
    
    for pick in picks:
        picked_by = pick.get('picked_by')
        if not picked_by:
            continue
        
        # Get team name from user_id
        user_info = users_map.get(picked_by)
        if not user_info:
            team_name = f"Team {picked_by}"
        else:
            team_name = user_info.get('team_name', f"Team {picked_by}")
        
        # Initialize team entry if not exists (using setdefault for efficiency)
        if team_name not in teams_draft_data:
            draft_position = draft_order.get(picked_by, 0)
            teams_draft_data[team_name] = {
                'draft_position': draft_position,
                'picks': []
            }
        
        # Get player name
        player_id = pick.get('player_id')
        player_name = get_player_name(player_id, players_map) if player_id else "Unknown"
        
        # Get position (from pick metadata or player data)
        position = pick.get('metadata', {}).get('position') or pick.get('position', '')
        
        # Add pick information
        pick_info = {
            'round': pick.get('round', 0),
            'pick_no': pick.get('pick_no', 0),
            'player_name': player_name,
            'position': position,
            'player_id': player_id
        }
        
        teams_draft_data[team_name]['picks'].append(pick_info)
    
    # Sort picks by round and pick_no for each team
    for team_name in teams_draft_data:
        teams_draft_data[team_name]['picks'].sort(key=lambda x: (x['round'], x['pick_no']))
    
    # Save processed drafts
    drafts_output_path = season_munged / "draft.json"
    with open(drafts_output_path, 'w') as f:
        json.dump(teams_draft_data, f, indent=2)
    
    print(f"  Processed draft data for {len(teams_draft_data)} teams")


def process_season(year: str, unmunged_dir: Path, munged_dir: Path) -> None:
    """
    Process a complete season's data.
    
    Args:
        year: Season year (e.g., "2024")
        unmunged_dir: Path to unmunged directory (e.g., src/unmunged)
        munged_dir: Path to munged directory (e.g., src/munged)
    """
    season_unmunged = unmunged_dir / year
    season_munged = munged_dir / year
    
    # Create output directories
    regular_season_dir = season_munged / "regular_season"
    postseason_dir = season_munged / "postseason"
    regular_season_dir.mkdir(parents=True, exist_ok=True)
    postseason_dir.mkdir(parents=True, exist_ok=True)
    
    # Load league info
    league_info_path = season_unmunged / "league_info.json"
    with open(league_info_path, 'r') as f:
        league_info = json.load(f)
    
    playoff_week_start = league_info.get('settings', {}).get('playoff_week_start', DEFAULT_PLAYOFF_WEEK_START)
    last_scored_leg = league_info.get('settings', {}).get('last_scored_leg', DEFAULT_LAST_SCORED_LEG)
    roster_positions = league_info.get('roster_positions', [])
    
    # Load all mappings
    print(f"Loading mappings for {year}...")
    players_path = unmunged_dir / "players.json"
    users_path = season_unmunged / "users.json"
    rosters_path = season_unmunged / "rosters.json"
    
    # Load players data once and extract both mappings
    players_map, positions_map = load_players_maps(players_path)
    users_map = load_users_map(users_path)
    rosters_map = load_rosters_map(rosters_path, users_map)
    
    print(f"Loaded {len(players_map)} players, {len(users_map)} users, {len(rosters_map)} rosters")
    
    # Process drafts
    print("\nProcessing drafts...")
    process_drafts(season_unmunged, season_munged, players_map, users_map)
    
    # Process regular season weeks
    regular_season_weeks = range(1, playoff_week_start)
    print(f"\nProcessing regular season weeks 1-{playoff_week_start - 1}...")
    
    all_regular_standings = []
    cached_standings = None  # Cache standings dict for incremental calculation
    
    for week in regular_season_weeks:
        week_dir = season_unmunged / f"week_{week}"
        matchups_path = week_dir / "matchups.json"
        transactions_path = week_dir / "transactions.json"
        
        if not matchups_path.exists():
            print(f"  Week {week}: No matchups file found, skipping")
            continue
        
        print(f"  Processing week {week}...")
        
        # Load week data
        with open(matchups_path, 'r') as f:
            matchups = json.load(f)
        
        transactions = []
        if transactions_path.exists():
            with open(transactions_path, 'r') as f:
                transactions = json.load(f)
        
        # Calculate standings up to this week (incrementally using cache)
        cached_standings = calculate_weekly_standings_dict(
            season_unmunged, week, rosters_map, cached_standings
        )
        # Convert to list for recap generation
        standings = standings_to_list(cached_standings)
        all_regular_standings.append({
            'week': week,
            'standings': standings
        })
        
        # Generate weekly recap (transactions excluded - saved separately)
        recap = generate_weekly_recap(
            matchups,
            transactions,
            standings,
            players_map,
            rosters_map,
            positions_map,
            roster_positions
        )
        
        # Create week subdirectory
        week_output_dir = regular_season_dir / f"week_{week}"
        week_output_dir.mkdir(parents=True, exist_ok=True)
        
        # Map and save transactions file separately
        mapped_transactions = map_transactions(transactions, players_map, rosters_map)
        transactions_output = week_output_dir / "transactions.json"
        with open(transactions_output, 'w') as f:
            json.dump(mapped_transactions, f, indent=2)
        
        # Save recap file (without transactions)
        recap_output = week_output_dir / "recap.json"
        with open(recap_output, 'w') as f:
            json.dump(recap, f, indent=2)
    
    # Generate complete regular season recap
    print("\nGenerating regular season recap...")
    # Use cached standings from the last week instead of recalculating
    if cached_standings is not None:
        final_standings = standings_to_list(cached_standings)
    else:
        # Fallback if no cached standings (shouldn't happen, but safe)
        final_standings = calculate_weekly_standings(
            season_unmunged,
            playoff_week_start - 1,
            rosters_map
        )
    
    reg_season_recap = {
        'standings': final_standings
    }
    
    reg_season_recap_path = regular_season_dir / "reg_season_recap.json"
    with open(reg_season_recap_path, 'w') as f:
        json.dump(reg_season_recap, f, indent=2)
    
    # Process postseason weeks (only if postseason has started)
    if last_scored_leg >= playoff_week_start:
        postseason_weeks = range(playoff_week_start, last_scored_leg + 1)
        print(f"\nProcessing postseason weeks {playoff_week_start}-{last_scored_leg}...")
        
        for week in postseason_weeks:
            week_dir = season_unmunged / f"week_{week}"
            matchups_path = week_dir / "matchups.json"
            transactions_path = week_dir / "transactions.json"
            
            if not matchups_path.exists():
                print(f"  Week {week}: No matchups file found, skipping")
                continue
            
            print(f"  Processing week {week}...")
            
            # Load week data
            with open(matchups_path, 'r') as f:
                matchups = json.load(f)
            
            transactions = []
            if transactions_path.exists():
                with open(transactions_path, 'r') as f:
                    transactions = json.load(f)
            
            # Generate weekly postseason recap
            recap = generate_weekly_postseason_recap(
                matchups,
                transactions,
                [],  # No standings for postseason
                players_map,
                rosters_map,
                positions_map,
                roster_positions
            )
            
            # Save recap file
            recap_output = postseason_dir / f"week_{week}_recap.json"
            with open(recap_output, 'w') as f:
                json.dump(recap, f, indent=2)
    else:
        print(f"\nPostseason has not started yet (starts at week {playoff_week_start}, currently at week {last_scored_leg})")
    
    # Generate complete postseason recap
    print("\nGenerating postseason recap...")
    winners_bracket_path = season_unmunged / "playoffs_winnersbracket.json"
    losers_bracket_path = season_unmunged / "playoffs_losersbracket.json"
    
    if winners_bracket_path.exists() and losers_bracket_path.exists():
        postseason_recap = generate_postseason_recap(
            winners_bracket_path,
            losers_bracket_path,
            rosters_map
        )
        
        postseason_recap_path = postseason_dir / "postseason_recap.json"
        with open(postseason_recap_path, 'w') as f:
            json.dump(postseason_recap, f, indent=2)
    else:
        print("  Postseason bracket files not found (postseason may not have started yet)")
    
    print(f"\nCompleted processing {year} season!")


def main():
    """Main entry point."""
    import sys
    
    # Default to processing 2024 if no year specified
    year = sys.argv[1] if len(sys.argv) > 1 else "2024"
    
    unmunged_dir = Path("src/unmunged")
    munged_dir = Path("src/munged")
    
    if not (unmunged_dir / year).exists():
        print(f"Error: Season {year} not found in {unmunged_dir}")
        sys.exit(1)
    
    process_season(year, unmunged_dir, munged_dir)


if __name__ == "__main__":
    main()

