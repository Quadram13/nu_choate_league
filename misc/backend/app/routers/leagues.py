"""
League-related API endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any
from app.database import get_database

router = APIRouter()


@router.get("/leagues")
async def get_all_leagues():
    """Get all leagues/seasons"""
    db = get_database()
    leagues = await db.leagues.find().sort("season", -1).to_list(length=100)
    
    # Convert ObjectId to string for JSON serialization
    for league in leagues:
        league["_id"] = str(league["_id"])
    
    return {"leagues": leagues}


@router.get("/leagues/{season}")
async def get_league_by_season(season: str):
    """Get league info for a specific season"""
    db = get_database()
    league = await db.leagues.find_one({"season": season})
    
    if not league:
        raise HTTPException(status_code=404, detail=f"League for season {season} not found")
    
    league["_id"] = str(league["_id"])
    return league


@router.get("/leagues/{season}/rosters")
async def get_rosters(season: str):
    """Get all rosters for a season"""
    db = get_database()
    rosters = await db.rosters.find({"season": season}).to_list(length=100)
    
    if not rosters:
        raise HTTPException(status_code=404, detail=f"No rosters found for season {season}")
    
    for roster in rosters:
        roster["_id"] = str(roster["_id"])
    
    return {"season": season, "rosters": rosters}


@router.get("/leagues/{season}/rosters/{roster_id}")
async def get_roster(season: str, roster_id: int):
    """Get a specific roster"""
    db = get_database()
    roster = await db.rosters.find_one({"season": season, "roster_id": roster_id})
    
    if not roster:
        raise HTTPException(
            status_code=404, 
            detail=f"Roster {roster_id} not found for season {season}"
        )
    
    roster["_id"] = str(roster["_id"])
    return roster


@router.get("/leagues/{season}/matchups/week/{week}")
async def get_matchups(season: str, week: int):
    """Get matchups for a specific week"""
    db = get_database()
    matchups = await db.matchups.find({"season": season, "week": week}).to_list(length=100)
    
    if not matchups:
        raise HTTPException(
            status_code=404, 
            detail=f"No matchups found for season {season}, week {week}"
        )
    
    for matchup in matchups:
        matchup["_id"] = str(matchup["_id"])
    
    return {"season": season, "week": week, "matchups": matchups}


@router.get("/leagues/{season}/standings")
async def get_current_standings(season: str):
    """Get current standings for a season"""
    db = get_database()
    
    # Get rosters with their records
    rosters = await db.rosters.find({"season": season}).to_list(length=100)
    
    if not rosters:
        raise HTTPException(status_code=404, detail=f"No standings found for season {season}")
    
    # Sort by wins (descending), then by points (descending)
    rosters.sort(key=lambda x: (-x.get("settings", {}).get("wins", 0), 
                                 -x.get("settings", {}).get("fpts", 0)))
    
    # Format standings
    standings = []
    for idx, roster in enumerate(rosters, 1):
        standings.append({
            "rank": idx,
            "roster_id": roster.get("roster_id"),
            "owner_id": roster.get("owner_id"),
            "wins": roster.get("settings", {}).get("wins", 0),
            "losses": roster.get("settings", {}).get("losses", 0),
            "ties": roster.get("settings", {}).get("ties", 0),
            "points_for": roster.get("settings", {}).get("fpts", 0),
            "points_against": roster.get("settings", {}).get("fpts_against", 0),
        })
    
    return {"season": season, "standings": standings}


@router.get("/leagues/{season}/draft")
async def get_draft(season: str):
    """Get draft results for a season"""
    db = get_database()
    
    # Find league to get draft_id
    league = await db.leagues.find_one({"season": season})
    if not league or "draft_id" not in league:
        raise HTTPException(status_code=404, detail=f"No draft found for season {season}")
    
    draft = await db.drafts.find_one({"draft_id": league["draft_id"]})
    
    if not draft:
        raise HTTPException(status_code=404, detail=f"Draft data not found for season {season}")
    
    draft["_id"] = str(draft["_id"])
    return draft
