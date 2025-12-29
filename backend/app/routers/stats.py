"""
Statistics and all-time records API endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.database import get_database

router = APIRouter()


@router.get("/stats/all-time/standings")
async def get_all_time_standings():
    """Get all-time standings across all seasons"""
    db = get_database()
    
    # Get all rosters across all seasons
    rosters = await db.rosters.find().to_list(length=1000)
    
    if not rosters:
        raise HTTPException(status_code=404, detail="No roster data found")
    
    # Aggregate by owner_id
    owner_stats = {}
    for roster in rosters:
        owner_id = roster.get("owner_id")
        if not owner_id:
            continue
        
        if owner_id not in owner_stats:
            owner_stats[owner_id] = {
                "owner_id": owner_id,
                "total_wins": 0,
                "total_losses": 0,
                "total_ties": 0,
                "total_points": 0,
                "seasons": []
            }
        
        settings = roster.get("settings", {})
        owner_stats[owner_id]["total_wins"] += settings.get("wins", 0)
        owner_stats[owner_id]["total_losses"] += settings.get("losses", 0)
        owner_stats[owner_id]["total_ties"] += settings.get("ties", 0)
        owner_stats[owner_id]["total_points"] += settings.get("fpts", 0)
        owner_stats[owner_id]["seasons"].append(roster.get("season"))
    
    # Convert to list and sort by wins
    standings = list(owner_stats.values())
    standings.sort(key=lambda x: (-x["total_wins"], -x["total_points"]))
    
    # Add rank
    for idx, standing in enumerate(standings, 1):
        standing["rank"] = idx
    
    return {"all_time_standings": standings}


@router.get("/stats/all-time/high-scores")
async def get_high_scores():
    """Get highest scoring games/weeks of all time"""
    db = get_database()
    
    # Get all matchups sorted by points (descending)
    matchups = await db.matchups.find().sort("points", -1).limit(50).to_list(length=50)
    
    if not matchups:
        raise HTTPException(status_code=404, detail="No matchup data found")
    
    # Format high scores
    high_scores = []
    for matchup in matchups:
        high_scores.append({
            "season": matchup.get("season"),
            "week": matchup.get("week"),
            "roster_id": matchup.get("roster_id"),
            "points": matchup.get("points"),
            "matchup_id": matchup.get("matchup_id")
        })
    
    return {"high_scores": high_scores}


@router.get("/players/{player_id}")
async def get_player(player_id: str):
    """Get player information"""
    db = get_database()
    
    player = await db.players.find_one({"player_id": player_id})
    
    if not player:
        raise HTTPException(status_code=404, detail=f"Player {player_id} not found")
    
    player["_id"] = str(player["_id"])
    return player


@router.get("/users/{user_id}")
async def get_user(user_id: str):
    """Get user information"""
    db = get_database()
    
    user = await db.users.find_one({"user_id": user_id})
    
    if not user:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    user["_id"] = str(user["_id"])
    return user
