"""Generate HTML reports for weekly recaps."""
from pathlib import Path
from typing import Dict, List, Optional

from .html_generator import escape_html, format_number, format_percentage, format_record
from .templates import get_html_template, get_navigation, get_breadcrumb


def generate_player_list_html(players: List[Dict], is_bench: bool = False) -> str:
    """
    Generate HTML for a list of players (starters or bench).
    
    Args:
        players: List of player dictionaries
        is_bench: Whether these are bench players
        
    Returns:
        HTML string
    """
    if not players:
        return '<p style="color: #7f8c8d; font-style: italic;">No players</p>'
    
    html = []
    for player in players:
        player_name = escape_html(player.get('player_name', 'Unknown'))
        points = format_number(player.get('points', 0))
        positions = player.get('positions', [])
        position_str = ', '.join(positions) if positions else ''
        
        bench_class = 'bench' if is_bench else ''
        html.append(f'<div class="player-item {bench_class}">')
        html.append('<div>')
        html.append(f'<span class="player-name">{player_name}</span>')
        if position_str:
            html.append(f'<span class="player-position">({position_str})</span>')
        html.append('</div>')
        html.append(f'<span class="player-points">{points} pts</span>')
        html.append('</div>')
    
    return ''.join(html)


def generate_matchup_table(matchups: List[Dict]) -> str:
    """
    Generate HTML table for matchup results with expandable player details.
    
    Args:
        matchups: List of matchup dictionaries
        
    Returns:
        HTML table string
    """
    html = ['<h2>Matchup Results</h2>']
    html.append('<table>')
    html.append('<thead><tr>')
    html.append('<th>Team 1</th>')
    html.append('<th>Points</th>')
    html.append('<th>Team 2</th>')
    html.append('<th>Points</th>')
    html.append('<th>Winner</th>')
    html.append('</tr></thead>')
    html.append('<tbody>')
    
    # Group matchups by matchup_id
    matchup_groups = {}
    for matchup in matchups:
        matchup_id = matchup.get('matchup_id')
        if matchup_id not in matchup_groups:
            matchup_groups[matchup_id] = []
        matchup_groups[matchup_id].append(matchup)
    
    # Display each matchup as a single row with expandable details
    matchup_index = 0
    for matchup_id, matchup_pair in sorted(matchup_groups.items()):
        if len(matchup_pair) == 2:
            team1 = matchup_pair[0]
            team2 = matchup_pair[1]
            
            points1 = team1.get('points', 0)
            points2 = team2.get('points', 0)
            team1_name = escape_html(team1.get('team_name', 'Unknown'))
            team2_name = escape_html(team2.get('team_name', 'Unknown'))
            
            # Determine winner
            if points1 > points2:
                winner_name = team1_name
                winner_class = 'winner'
            elif points2 > points1:
                winner_name = team2_name
                winner_class = 'winner'
            else:
                winner_name = 'Tie'
                winner_class = 'tie'
            
            # Main matchup row (clickable)
            html.append(f'<tr class="matchup-row {winner_class}" onclick="toggleMatchup({matchup_index})">')
            html.append(f'<td><strong>{team1_name}</strong></td>')
            html.append(f'<td>{format_number(points1)}</td>')
            html.append(f'<td><strong>{team2_name}</strong></td>')
            html.append(f'<td>{format_number(points2)}</td>')
            html.append(f'<td><strong>{winner_name}</strong><span class="expand-icon">▶</span></td>')
            html.append('</tr>')
            
            # Expandable details row
            html.append(f'<tr class="matchup-details" id="matchup-{matchup_index}">')
            html.append('<td colspan="5">')
            html.append('<div class="matchup-details-content">')
            
            # Team 1 details
            html.append('<div class="team-details">')
            html.append(f'<h4>{team1_name} - {format_number(points1)} points</h4>')
            
            # Starters
            starters1 = team1.get('starters', [])
            if starters1:
                html.append('<div class="player-section">')
                html.append('<h5>Starters</h5>')
                html.append(generate_player_list_html(starters1, is_bench=False))
                html.append('</div>')
            
            # Bench
            bench1 = team1.get('bench', [])
            if bench1:
                html.append('<div class="player-section">')
                html.append('<h5>Bench</h5>')
                html.append(generate_player_list_html(bench1, is_bench=True))
                html.append('</div>')
            
            html.append('</div>')  # End team-details
            
            # Team 2 details
            html.append('<div class="team-details">')
            html.append(f'<h4>{team2_name} - {format_number(points2)} points</h4>')
            
            # Starters
            starters2 = team2.get('starters', [])
            if starters2:
                html.append('<div class="player-section">')
                html.append('<h5>Starters</h5>')
                html.append(generate_player_list_html(starters2, is_bench=False))
                html.append('</div>')
            
            # Bench
            bench2 = team2.get('bench', [])
            if bench2:
                html.append('<div class="player-section">')
                html.append('<h5>Bench</h5>')
                html.append(generate_player_list_html(bench2, is_bench=True))
                html.append('</div>')
            
            html.append('</div>')  # End team-details
            html.append('</div>')  # End matchup-details-content
            html.append('</td>')
            html.append('</tr>')
            
            matchup_index += 1
    
    html.append('</tbody>')
    html.append('</table>')
    
    # Add JavaScript for toggling
    html.append('''
    <script>
    function toggleMatchup(index) {
        const details = document.getElementById('matchup-' + index);
        const row = details.previousElementSibling;
        if (details.classList.contains('expanded')) {
            details.classList.remove('expanded');
            row.classList.remove('expanded');
        } else {
            // Close all other expanded matchups
            document.querySelectorAll('.matchup-details.expanded').forEach(el => {
                el.classList.remove('expanded');
                el.previousElementSibling.classList.remove('expanded');
            });
            details.classList.add('expanded');
            row.classList.add('expanded');
        }
    }
    </script>
    ''')
    
    return ''.join(html)


def generate_standings_table(standings: List[Dict]) -> str:
    """
    Generate HTML table for standings.
    
    Args:
        standings: List of standings dictionaries
        
    Returns:
        HTML table string
    """
    html = ['<h2>Current Standings</h2>']
    html.append('<table class="standings-table">')
    html.append('<thead><tr>')
    html.append('<th class="rank">Rank</th>')
    html.append('<th>Team</th>')
    html.append('<th>Record</th>')
    html.append('<th>Win %</th>')
    html.append('<th>PF</th>')
    html.append('<th>PA</th>')
    html.append('</tr></thead>')
    html.append('<tbody>')
    
    for rank, team in enumerate(standings, 1):
        team_name = escape_html(team.get('team_name', 'Unknown'))
        wins = team.get('wins', 0)
        losses = team.get('losses', 0)
        ties = team.get('ties', 0)
        win_pct = team.get('win_pct', 0)
        pf = team.get('pf', 0)
        pa = team.get('pa', 0)
        
        html.append('<tr>')
        html.append(f'<td class="rank">{rank}</td>')
        html.append(f'<td><strong>{team_name}</strong></td>')
        html.append(f'<td>{format_record(wins, losses, ties)}</td>')
        html.append(f'<td>{format_percentage(win_pct)}</td>')
        html.append(f'<td>{format_number(pf)}</td>')
        html.append(f'<td>{format_number(pa)}</td>')
        html.append('</tr>')
    
    html.append('</tbody>')
    html.append('</table>')
    return ''.join(html)


def generate_awards_section(awards: Dict) -> str:
    """
    Generate HTML section for weekly awards.
    
    Args:
        awards: Awards dictionary
        
    Returns:
        HTML string for awards section
    """
    html = ['<h2>Weekly Awards</h2>']
    
    # Most/Least Efficient Manager
    most_eff = awards.get('most_efficient_manager')
    least_eff = awards.get('least_efficient_manager')
    
    if most_eff:
        # Calculate points_left from optimal_score - actual_score
        optimal_score = most_eff.get('optimal_score', 0)
        actual_score = most_eff.get('actual_score', 0)
        points_left = optimal_score - actual_score
        
        html.append('<div class="award-box">')
        html.append('<h4>🎯 Most Efficient Manager</h4>')
        html.append(f'<p><strong>{escape_html(most_eff.get("team_name", "Unknown"))}</strong>')
        html.append(f' - Left only {format_number(points_left)} points on the bench</p>')
        html.append('</div>')
    
    if least_eff:
        # Calculate points_left from optimal_score - actual_score
        optimal_score = least_eff.get('optimal_score', 0)
        actual_score = least_eff.get('actual_score', 0)
        points_left = optimal_score - actual_score
        
        html.append('<div class="award-box">')
        html.append('<h4>😅 Least Efficient Manager</h4>')
        html.append(f'<p><strong>{escape_html(least_eff.get("team_name", "Unknown"))}</strong>')
        html.append(f' - Left {format_number(points_left)} points on the bench</p>')
        html.append('</div>')
    
    # Highest Points in Loss
    highest_loss = awards.get('highest_points_in_loss')
    if highest_loss:
        html.append('<div class="award-box">')
        html.append('<h4>💔 Highest Points in a Loss</h4>')
        html.append(f'<p><strong>{escape_html(highest_loss.get("team_name", "Unknown"))}</strong>')
        html.append(f' - Scored {format_number(highest_loss.get("points", 0))} points and still lost')
        html.append(f' (opponent scored {format_number(highest_loss.get("opponent_points", 0))})</p>')
        html.append('</div>')
    
    # Lowest Points in Win
    lowest_win = awards.get('lowest_points_in_win')
    if lowest_win:
        html.append('<div class="award-box">')
        html.append('<h4>🍀 Lowest Points in a Win</h4>')
        html.append(f'<p><strong>{escape_html(lowest_win.get("team_name", "Unknown"))}</strong>')
        html.append(f' - Scored {format_number(lowest_win.get("points", 0))} points and still won')
        html.append(f' (opponent scored {format_number(lowest_win.get("opponent_points", 0))})</p>')
        html.append('</div>')
    
    # Largest/Smallest Winning Margin
    largest_margin = awards.get('largest_winning_margin')
    if largest_margin:
        html.append('<div class="award-box">')
        html.append('<h4>💪 Largest Winning Margin</h4>')
        html.append(f'<p><strong>{escape_html(largest_margin.get("team_name", "Unknown"))}</strong>')
        html.append(f' - Won by {format_number(largest_margin.get("margin", 0))} points')
        html.append(f' ({format_number(largest_margin.get("points", 0))} - {format_number(largest_margin.get("opponent_points", 0))})</p>')
        html.append('</div>')
    
    smallest_margin = awards.get('smallest_winning_margin')
    if smallest_margin:
        html.append('<div class="award-box">')
        html.append('<h4>😬 Smallest Winning Margin</h4>')
        html.append(f'<p><strong>{escape_html(smallest_margin.get("team_name", "Unknown"))}</strong>')
        html.append(f' - Won by {format_number(smallest_margin.get("margin", 0))} points')
        html.append(f' ({format_number(smallest_margin.get("points", 0))} - {format_number(smallest_margin.get("opponent_points", 0))})</p>')
        html.append('</div>')
    
    return ''.join(html)


def convert_position_team_to_players(team: Dict) -> List[Dict]:
    """
    Convert position-based team structure (QB, RB1, etc.) to player list.
    
    Args:
        team: Team dictionary with position keys
        
    Returns:
        List of player dictionaries
    """
    players = []
    position_order = ['QB', 'RB1', 'RB2', 'WR1', 'WR2', 'TE', 'FLEX1', 'FLEX2', 'K', 'DEF']
    
    for pos in position_order:
        if pos in team and team[pos]:
            player = team[pos].copy()
            # Add position to player dict if not present
            if 'positions' not in player:
                player['positions'] = [pos]
            players.append(player)
    
    return players


def generate_team_highlight(team: Dict, title: str) -> str:
    """
    Generate HTML for a team highlight section.
    
    Handles two team structures:
    1. Simple teams: {roster_id, team_name, points} - just show summary
    2. Position-based teams: {QB: {...}, RB1: {...}, ...} - show player list
    3. Player list teams: {players: [...], team_name, total_points} - show player list
    
    Args:
        team: Team dictionary
        title: Section title
        
    Returns:
        HTML string
    """
    if not team:
        return ''
    
    html = [f'<div class="team-highlight">']
    html.append(f'<h3>{title}</h3>')
    
    # Check if it's a simple team (just roster_id, team_name, points)
    if 'points' in team and 'roster_id' in team and 'players' not in team:
        # Simple team structure - just show summary
        team_name = escape_html(team.get('team_name', 'Unknown'))
        points = format_number(team.get('points', 0))
        html.append(f'<p><strong>{team_name}</strong> - {points} points</p>')
        html.append('</div>')
        return ''.join(html)
    
    # Check if it's a position-based team (has QB, RB1, etc. keys)
    if 'QB' in team or 'RB1' in team or 'WR1' in team:
        # Position-based structure - convert to player list
        players = convert_position_team_to_players(team)
        team_name = escape_html(team.get('team_name', 'Unknown'))
        total_points = team.get('total_points', 0)
        
        # Calculate total if not provided
        if not total_points:
            total_points = sum(player.get('points', 0) for player in players)
        
        html.append(f'<p><strong>{team_name}</strong>')
        html.append(f' - {format_number(total_points)} points</p>')
        html.append('<ul class="player-list">')
        
        for player in players:
            player_name = escape_html(player.get('player_name', 'Unknown'))
            points = format_number(player.get('points', 0))
            positions = player.get('positions', [])
            position_str = ', '.join(positions) if positions else ''
            
            html.append('<li>')
            html.append(f'<span class="player-name">{player_name}</span>')
            if position_str:
                html.append(f'<span class="player-position">({position_str})</span>')
            html.append(f'<span class="player-points">{points} pts</span>')
            html.append('</li>')
        
        html.append('</ul>')
        html.append('</div>')
        return ''.join(html)
    
    # Check if it's a player list team
    if team.get('players'):
        team_name = escape_html(team.get('team_name', 'Unknown'))
        total_points = format_number(team.get('total_points', 0))
        
        html.append(f'<p><strong>{team_name}</strong>')
        html.append(f' - {total_points} points</p>')
        html.append('<ul class="player-list">')
        
        for player in team.get('players', []):
            player_name = escape_html(player.get('player_name', 'Unknown'))
            points = format_number(player.get('points', 0))
            positions = player.get('positions', [])
            position_str = ', '.join(positions) if positions else ''
            
            html.append('<li>')
            html.append(f'<span class="player-name">{player_name}</span>')
            if position_str:
                html.append(f'<span class="player-position">({position_str})</span>')
            html.append(f'<span class="player-points">{points} pts</span>')
            html.append('</li>')
        
        html.append('</ul>')
        html.append('</div>')
        return ''.join(html)
    
    # Fallback - just show team name if structure is unknown
    team_name = escape_html(team.get('team_name', 'Unknown'))
    html.append(f'<p><strong>{team_name}</strong></p>')
    html.append('</div>')
    return ''.join(html)


def group_failed_claims_by_player(transactions: List[Dict]) -> Dict[str, List[Dict]]:
    """
    Group failed waiver claims by the player being added.
    
    Args:
        transactions: List of transaction dictionaries
        
    Returns:
        Dictionary mapping player name to list of failed claims
    """
    failed_by_player = {}
    
    for transaction in transactions:
        if transaction.get('type') == 'waiver' and transaction.get('status') == 'failed':
            adds = transaction.get('adds', {})
            if adds:
                # Get the first (and usually only) player being added
                player_name = list(adds.keys())[0]
                if player_name not in failed_by_player:
                    failed_by_player[player_name] = []
                failed_by_player[player_name].append(transaction)
    
    return failed_by_player


def format_timestamp(timestamp: Optional[int]) -> str:
    """
    Format a Unix timestamp to a readable date/time string.
    
    Args:
        timestamp: Unix timestamp in milliseconds
        
    Returns:
        Formatted date/time string
    """
    if timestamp is None:
        return ''
    
    try:
        from datetime import datetime
        # Convert from milliseconds to seconds
        dt = datetime.fromtimestamp(timestamp / 1000)
        return dt.strftime('%m/%d %I:%M %p')
    except (ValueError, OSError, OverflowError):
        return ''


def generate_transactions_table(transactions: List[Dict], season: str = None) -> str:
    """
    Generate HTML table for transactions with expandable failed claims.
    Transactions are organized by type (Trades first, then Waivers) and sorted by time.
    
    Args:
        transactions: List of transaction dictionaries
        season: Season year (optional, used to load rosters for trade team names)
        
    Returns:
        HTML table string
    """
    html = ['<h2>Transactions</h2>']
    
    if not transactions:
        html.append('<p>No transactions this week.</p>')
        return ''.join(html)
    
    # Filter to only successful transactions (complete status)
    successful_transactions = [
        t for t in transactions
        if t.get('status') == 'complete'
    ]
    
    if not successful_transactions:
        html.append('<p>No successful transactions this week.</p>')
        return ''.join(html)
    
    # Load rosters map for trade team names
    rosters_map = {}
    if season:
        from pathlib import Path
        from constants import UNMUNGED_DIR
        from mappers import load_rosters_map
        
        unmunged_dir = Path(UNMUNGED_DIR) / season
        if unmunged_dir.exists():
            try:
                rosters_map = load_rosters_map(unmunged_dir)
            except Exception:
                # Fallback if loading fails
                rosters_map = {}
    
    # Group failed claims by player
    failed_by_player = group_failed_claims_by_player(transactions)
    
    # Separate trades, waivers, and free agents, sort each by creation time (most recent first)
    trades = [t for t in successful_transactions if t.get('type') == 'trade']
    waivers = [t for t in successful_transactions if t.get('type') == 'waiver']
    free_agents = [t for t in successful_transactions if t.get('type') == 'free_agent']
    
    # Sort by creation time (most recent first)
    trades.sort(key=lambda x: x.get('created', 0), reverse=True)
    waivers.sort(key=lambda x: x.get('created', 0), reverse=True)
    free_agents.sort(key=lambda x: x.get('created', 0), reverse=True)
    
    transaction_index = 0
    
    # Generate trades section
    if trades:
        html.append('<h3>💼 Trades</h3>')
        html.append('<table>')
        html.append('<thead><tr>')
        html.append('<th>Team 1</th>')
        html.append('<th>Gets</th>')
        html.append('<th>Gives</th>')
        html.append('<th>Team 2</th>')
        html.append('<th>Gets</th>')
        html.append('<th>Gives</th>')
        html.append('<th>Time</th>')
        html.append('</tr></thead>')
        html.append('<tbody>')
        
        for transaction in trades:
            _generate_trade_row(html, transaction, rosters_map, show_time=True)
        
        html.append('</tbody>')
        html.append('</table>')
    
    # Generate waivers section
    if waivers:
        html.append('<h3>📋 Waivers</h3>')
        html.append('<table>')
        html.append('<thead><tr>')
        html.append('<th>Team</th>')
        html.append('<th>Adds</th>')
        html.append('<th>Drops</th>')
        html.append('<th>Time</th>')
        html.append('<th></th>')
        html.append('</tr></thead>')
        html.append('<tbody>')
        
        for transaction in waivers:
            transaction_index = _generate_transaction_row(
                html, transaction, failed_by_player, transaction_index, show_time=True
            )
        
        html.append('</tbody>')
        html.append('</table>')
    
    # Generate free agents section
    if free_agents:
        html.append('<h3>🆓 Free Agents</h3>')
        html.append('<table>')
        html.append('<thead><tr>')
        html.append('<th>Team</th>')
        html.append('<th>Adds</th>')
        html.append('<th>Drops</th>')
        html.append('<th>Time</th>')
        html.append('</tr></thead>')
        html.append('<tbody>')
        
        for transaction in free_agents:
            transaction_index = _generate_transaction_row(
                html, transaction, failed_by_player, transaction_index, show_time=True
            )
        
        html.append('</tbody>')
        html.append('</table>')
    
    # Add JavaScript for toggling
    html.append('''
    <script>
    function toggleTransaction(index) {
        const details = document.getElementById('transaction-' + index);
        const row = details.previousElementSibling;
        if (details.classList.contains('expanded')) {
            details.classList.remove('expanded');
            row.classList.remove('expanded');
        } else {
            // Close all other expanded transactions
            document.querySelectorAll('.transaction-details.expanded').forEach(el => {
                el.classList.remove('expanded');
                el.previousElementSibling.classList.remove('expanded');
            });
            details.classList.add('expanded');
            row.classList.add('expanded');
        }
    }
    </script>
    ''')
    
    return ''.join(html)


def _generate_trade_row(
    html: List[str],
    transaction: Dict,
    rosters_map: Dict[int, Dict[str, str]],
    show_time: bool = False
) -> None:
    """
    Generate a trade row showing both teams involved in the trade.
    
    Args:
        html: List to append HTML to
        transaction: Trade transaction dictionary
        rosters_map: Roster ID to team info mapping
        show_time: Whether to show the timestamp column
    """
    adds = transaction.get('adds', {})
    drops = transaction.get('drops', {})
    roster_ids = transaction.get('roster_ids', [])
    created = transaction.get('created')
    time_str = format_timestamp(created) if show_time else ''
    
    if len(roster_ids) < 2:
        # Fallback if we don't have both teams
        team_name = escape_html(transaction.get('creator_team_name', 'Unknown'))
        adds_list = [escape_html(player) for player in adds.keys()]
        drops_list = [escape_html(player) for player in drops.keys()]
        adds_str = ', '.join(adds_list) if adds_list else '—'
        drops_str = ', '.join(drops_list) if drops_list else '—'
        
        html.append('<tr>')
        html.append(f'<td colspan="3">{team_name}</td>')
        html.append(f'<td>{adds_str}</td>')
        html.append(f'<td>{drops_str}</td>')
        if show_time:
            html.append(f'<td class="time-cell">{time_str}</td>')
        html.append('</tr>')
        return
    
    # Get team IDs
    team1_id = roster_ids[0]
    team2_id = roster_ids[1] if len(roster_ids) > 1 else None
    
    # Get team names from rosters_map
    team1_name = escape_html(
        rosters_map.get(team1_id, {}).get('team_name', transaction.get('creator_team_name', f'Team {team1_id}'))
    )
    team2_name = escape_html(
        rosters_map.get(team2_id, {}).get('team_name', f'Team {team2_id}') if team2_id else 'Unknown'
    )
    
    # Get team 1's adds and drops (players where the roster_id matches team1_id)
    team1_adds = [escape_html(player) for player, rid in adds.items() if rid == team1_id]
    team1_drops = [escape_html(player) for player, rid in drops.items() if rid == team1_id]
    
    # Get team 2's adds and drops
    team2_adds = []
    team2_drops = []
    if team2_id:
        team2_adds = [escape_html(player) for player, rid in adds.items() if rid == team2_id]
        team2_drops = [escape_html(player) for player, rid in drops.items() if rid == team2_id]
    
    team1_adds_str = ', '.join(team1_adds) if team1_adds else '—'
    team1_drops_str = ', '.join(team1_drops) if team1_drops else '—'
    team2_adds_str = ', '.join(team2_adds) if team2_adds else '—'
    team2_drops_str = ', '.join(team2_drops) if team2_drops else '—'
    
    html.append('<tr>')
    html.append(f'<td><strong>{team1_name}</strong></td>')
    html.append(f'<td>{team1_adds_str}</td>')
    html.append(f'<td>{team1_drops_str}</td>')
    html.append(f'<td><strong>{team2_name}</strong></td>')
    html.append(f'<td>{team2_adds_str}</td>')
    html.append(f'<td>{team2_drops_str}</td>')
    if show_time:
        html.append(f'<td class="time-cell">{time_str}</td>')
    html.append('</tr>')


def _generate_transaction_row(
    html: List[str],
    transaction: Dict,
    failed_by_player: Dict[str, List[Dict]],
    transaction_index: int,
    show_time: bool = False
) -> int:
    """
    Generate a single transaction row and its expandable details if needed.
    
    Args:
        html: List to append HTML to
        transaction: Transaction dictionary
        failed_by_player: Dictionary of failed claims grouped by player
        transaction_index: Current transaction index for unique IDs
        show_time: Whether to show the timestamp column
        
    Returns:
        Updated transaction_index (incremented if expandable row was added)
    """
    team_name = escape_html(transaction.get('creator_team_name', 'Unknown'))
    adds = transaction.get('adds', {})
    drops = transaction.get('drops', {})
    created = transaction.get('created')
    time_str = format_timestamp(created) if show_time else ''
    
    # Format adds and drops (use original player names, not escaped, for lookup)
    adds_list_original = list(adds.keys())
    adds_list = [escape_html(player) for player in adds_list_original]
    drops_list = [escape_html(player) for player in drops.keys()]
    adds_str = ', '.join(adds_list) if adds_list else '—'
    drops_str = ', '.join(drops_list) if drops_list else '—'
    
    # Check if any of the added players have failed claims (only for waivers)
    has_failed_claims = False
    failed_claims_players = []
    if transaction.get('type') == 'waiver':
        for player_original in adds_list_original:
            if player_original in failed_by_player:
                has_failed_claims = True
                failed_claims_players.append(player_original)
    
    # Main transaction row
    row_class = 'transaction-row'
    if has_failed_claims:
        row_class += ' has-failed-claims'
        onclick = f'toggleTransaction({transaction_index})'
    else:
        onclick = ''
    
    html.append(f'<tr class="{row_class}" onclick="{onclick}">')
    html.append(f'<td>{team_name}</td>')
    html.append(f'<td>{adds_str}</td>')
    html.append(f'<td>{drops_str}</td>')
    if show_time:
        html.append(f'<td class="time-cell">{time_str}</td>')
    if has_failed_claims:
        html.append(f'<td><span class="expand-icon">▶</span></td>')
    elif show_time:
        html.append('<td></td>')
    html.append('</tr>')
    
    # Expandable failed claims row
    if has_failed_claims:
        html.append(f'<tr class="transaction-details" id="transaction-{transaction_index}">')
        colspan = 5 if show_time else 4
        html.append(f'<td colspan="{colspan}">')
        html.append('<div class="transaction-details-content">')
        html.append('<h4>Failed Claims for This Player</h4>')
        
        for player_original in failed_claims_players:
            failed_claims = failed_by_player[player_original]
            html.append(f'<div class="failed-claims-group">')
            html.append(f'<h5>{escape_html(player_original)}</h5>')
            html.append('<ul class="failed-claims-list">')
            
            for failed_claim in failed_claims:
                failed_team = escape_html(failed_claim.get('creator_team_name', 'Unknown'))
                failed_drops = failed_claim.get('drops', {})
                failed_drops_list = [escape_html(p) for p in failed_drops.keys()]
                failed_drops_str = ', '.join(failed_drops_list) if failed_drops_list else 'None'
                
                html.append('<li>')
                html.append(f'<strong>{failed_team}</strong>')
                if failed_drops_str != 'None':
                    html.append(f' (dropped: {failed_drops_str})')
                html.append('</li>')
            
            html.append('</ul>')
            html.append('</div>')
        
        html.append('</div>')
        html.append('</td>')
        html.append('</tr>')
        
        transaction_index += 1
    
    return transaction_index


def generate_weekly_html(
    recap_data: Dict,
    week: int,
    season: str,
    output_path: Path,
    prev_week: Optional[int] = None,
    next_week: Optional[int] = None,
    transactions: Optional[List[Dict]] = None
) -> None:
    """
    Generate HTML page for a weekly recap.
    
    Args:
        recap_data: Weekly recap data dictionary
        week: Week number
        season: Season year (e.g., "2024")
        output_path: Path to output HTML file
        prev_week: Previous week number (optional)
        next_week: Next week number (optional)
        transactions: List of transaction dictionaries (optional)
    """
    title = f'{season} Season - Week {week} Recap'
    
    # Navigation
    nav = get_navigation(season=season, week=week, prev_week=prev_week, next_week=next_week)
    breadcrumb = get_breadcrumb(season=season, week=week)
    
    # Content
    content_parts = [breadcrumb]
    content_parts.append(f'<h1>Week {week} Recap - {season} Season</h1>')
    
    # Matchups
    matchups = recap_data.get('matchups', [])
    if matchups:
        content_parts.append(generate_matchup_table(matchups))
    
    # Transactions
    if transactions:
        content_parts.append(generate_transactions_table(transactions, season=season))
    
    # Standings
    standings = recap_data.get('standings', [])
    if standings:
        content_parts.append(generate_standings_table(standings))
    
    # Awards
    awards = recap_data.get('awards', {})
    if awards:
        content_parts.append(generate_awards_section(awards))
    
    # Team Highlights
    content_parts.append('<h2>Team Highlights</h2>')
    
    highest_team = recap_data.get('highest_scoring_team')
    if highest_team:
        content_parts.append(generate_team_highlight(highest_team, '🏆 Highest Scoring Team'))
    
    lowest_team = recap_data.get('lowest_scoring_team')
    if lowest_team:
        content_parts.append(generate_team_highlight(lowest_team, '📉 Lowest Scoring Team'))
    
    highest_starters = recap_data.get('highest_scoring_starters')
    if highest_starters:
        content_parts.append(generate_team_highlight(highest_starters, '⭐ Highest Scoring Starters'))
    
    lowest_starters = recap_data.get('lowest_scoring_starters')
    if lowest_starters:
        content_parts.append(generate_team_highlight(lowest_starters, '💤 Lowest Scoring Starters'))
    
    benchwarmers = recap_data.get('benchwarmers')
    if benchwarmers:
        content_parts.append(generate_team_highlight(benchwarmers, '🔥 Benchwarmers (Best Bench Lineup)'))
    
    content = ''.join(content_parts)
    
    # Generate full HTML
    html = get_html_template(title, nav, content)
    
    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html)

