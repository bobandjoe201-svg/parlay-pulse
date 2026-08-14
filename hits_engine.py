import statsapi
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

# ==========================================
# CONFIGURATION TOGGLES & CONSTANTS
# ==========================================
USE_PARK_FACTORS = True 
CURRENT_SEASON = 2026

# Static historical Park Factors for Hits (League Average = 1.00)
PARK_FACTORS = {
    'ARI': 1.01, 'ATL': 1.00, 'BAL': 1.02, 'BOS': 1.04, 'CHC': 1.02,
    'CHW': 1.00, 'CIN': 1.05, 'CLE': 0.99, 'COL': 1.14, 'DET': 0.99,
    'HOU': 0.99, 'KCR': 1.00, 'LAA': 1.00, 'LAD': 1.01, 'MIA': 0.96,
    'MIL': 1.00, 'MIN': 1.00, 'NYM': 0.97, 'NYY': 1.00, 'OAK': 0.98,
    'PHI': 1.03, 'PIT': 0.99, 'SDP': 0.97, 'SEA': 0.95, 'SFG': 0.96,
    'STL': 1.00, 'TBR': 0.98, 'TEX': 1.03, 'TOR': 1.01, 'WSN': 1.01
}

# Mapping bridge from Baseball Reference team names to StatsAPI abbreviations
TEAM_NAME_TO_ABBR = {
    'Arizona': 'ARI', 'Atlanta': 'ATL', 'Baltimore': 'BAL', 'Boston': 'BOS',
    'Chicago Cubs': 'CHC', 'Chicago White Sox': 'CHW', 'Cincinnati': 'CIN',
    'Cleveland': 'CLE', 'Colorado': 'COL', 'Detroit': 'DET', 'Houston': 'HOU',
    'Kansas City': 'KCR', 'Los Angeles Angels': 'LAA', 'Los Angeles Dodgers': 'LAD',
    'Miami': 'MIA', 'Milwaukee': 'MIL', 'Minnesota': 'MIN', 'New York Mets': 'NYM',
    'New York Yankees': 'NYY', 'Athletics': 'OAK', 'Philadelphia': 'PHI',
    'Pittsburgh': 'PIT', 'San Diego': 'SDP', 'Seattle': 'SEA', 'San Francisco': 'SFG',
    'St. Louis': 'STL', 'Tampa Bay': 'TBR', 'Texas': 'TEX', 'Toronto': 'TOR',
    'Washington': 'WSN'
}

# Standalone 30-Team Proxy Emoji Mapping
TEAM_EMOJIS = {
    'ARI': '🐍', 'ATL': '🪓', 'BAL': '🐤', 'BOS': '🟩', 'CHC': '🐻',
    'CHW': '🧦', 'CIN': '🔴', 'CLE': '🛡️', 'COL': '🏔️', 'DET': '🐯',
    'HOU': '🚀', 'KCR': '👑', 'LAA': '😇', 'LAD': '🌴', 'MIA': '🐟',
    'MIL': '🍺', 'MIN': '👯', 'NYM': '🍎', 'NYY': '🗽', 'OAK': '🎰',
    'PHI': '🔔', 'PIT': '🏴‍☠️', 'SDP': '🤎', 'SEA': '⚓', 'SFG': '🌉',
    'STL': '🐦', 'TBR': '☀️', 'TEX': '🤠', 'TOR': '🍁', 'WSN': '🏛️'
}

# Bridge mapping StatsAPI variant abbreviations to standard 3-letter codes
STATSAPI_TO_STANDARD_ABBR = {
    'AZ': 'ARI', 'ARI': 'ARI',
    'ATL': 'ATL',
    'BAL': 'BAL',
    'BOS': 'BOS',
    'CHC': 'CHC',
    'CWS': 'CHW', 'CHW': 'CHW',
    'CIN': 'CIN',
    'CLE': 'CLE',
    'COL': 'COL',
    'DET': 'DET',
    'HOU': 'HOU',
    'KC': 'KCR', 'KCR': 'KCR',
    'LAA': 'LAA',
    'LAD': 'LAD',
    'MIA': 'MIA',
    'MIL': 'MIL',
    'MIN': 'MIN',
    'NYM': 'NYM',
    'NYY': 'NYY',
    'ATH': 'OAK', 'OAK': 'OAK',
    'PHI': 'PHI',
    'PIT': 'PIT',
    'SD': 'SDP', 'SDP': 'SDP',
    'SEA': 'SEA',
    'SF': 'SFG', 'SFG': 'SFG',
    'STL': 'STL',
    'TB': 'TBR', 'TBR': 'TBR',
    'TEX': 'TEX',
    'TOR': 'TOR',
    'WSH': 'WSN', 'WSN': 'WSN'
}

def get_todays_slate(target_date: str) -> list:
    """Queries statsapi for target_date games. Filters postponed/cancelled and doubleheaders."""
    schedule = statsapi.schedule(date=target_date)
    slate = []
    seen_matchups = set()
    
    for game in schedule:
        if game['status'] in ['Postponed', 'Cancelled']:
            continue
            
        home_id = game['home_id']
        away_id = game['away_id']
        matchup_key = f"{away_id}_{home_id}"
        
        if matchup_key in seen_matchups:
            continue
            
        seen_matchups.add(matchup_key)
        
        slate.append({
            'game_id': game['game_id'],
            'away_team_id': away_id,
            'away_team_name': game['away_name'],
            'home_team_id': home_id,
            'home_team_name': game['home_name'],
            'away_probable_pitcher_name': game.get('away_probable_pitcher', 'TBD'),
            'home_probable_pitcher_name': game.get('home_probable_pitcher', 'TBD'),
            'game_datetime': game.get('game_datetime', '')
        })
        
    return slate


def get_offensive_baselines(season: int = CURRENT_SEASON) -> tuple:
    """
    Queries StatsAPI for all 30 teams' offensive stats (Season + Last 15 Games).
    Calculates 50/50 Blended Team Hits/Game and updated Opponent Multipliers.
    """
    teams_response = statsapi.get('teams', {'sportId': 1})['teams']
    
    team_data = {}
    total_blended_hpg = 0.0
    valid_teams_count = 0
    
    for team in teams_response:
        team_id = team['id']
        # Change this line in get_offensive_baselines():
        raw_abbr = team.get('abbreviation', '')
        abbr = STATSAPI_TO_STANDARD_ABBR.get(raw_abbr, raw_abbr)        
        
        # Pull season and lastXGames (limit 15) in 1 combined HTTP request
        stats_response = statsapi.get('team_stats', {
            'teamId': team_id, 
            'group': 'hitting', 
            'stats': 'season,lastXGames',
            'limit': 15,
            'season': season
        })
        
        try:
            splits = stats_response['stats']
            season_stat = {}
            recent_stat = {}
            
            for split_group in splits:
                type_name = split_group['type']['displayName']
                if type_name == 'season':
                    season_stat = split_group['splits'][0]['stat']
                elif type_name == 'lastXGames':
                    recent_stat = split_group['splits'][0]['stat']
            
            # Full Season Metrics
            g_season = season_stat.get('gamesPlayed', 0)
            h_season = season_stat.get('hits', 0)
            if g_season == 0:
                continue
                
            hpg_season = h_season / g_season
            
            # 15-Game Rolling Metrics
            g_recent = recent_stat.get('gamesPlayed', 0)
            h_recent = recent_stat.get('hits', 0)
            hpg_recent = (h_recent / g_recent) if g_recent > 0 else hpg_season
            
            # 50/50 Weighted Blend
            hpg_blended = (0.50 * hpg_recent) + (0.50 * hpg_season)
            
            team_data[team_id] = {
                'name': team['name'],
                'abbr': abbr,
                'G_Season': g_season,
                'H_Season': h_season,
                'HPG_Season': hpg_season,
                'HPG_Recent15': hpg_recent,
                'Hits_per_Game': hpg_blended
            }
            
            total_blended_hpg += hpg_blended
            valid_teams_count += 1
            
        except (IndexError, KeyError):
            continue
            
    league_avg_hpg = (total_blended_hpg / valid_teams_count) if valid_teams_count > 0 else 1.0
    
    for t_id, data in team_data.items():
        data['Opponent_Multiplier'] = data['Hits_per_Game'] / league_avg_hpg if league_avg_hpg > 0 else 1.0
            
    return team_data, league_avg_hpg


def parse_ip(ip_str) -> float:
    """Converts baseball IP strings ('4.1', '4.2') into mathematical floats."""
    if not ip_str:
        return 0.0
    
    ip_float = float(ip_str)
    full_innings = int(ip_float)
    remainder = round(ip_float - full_innings, 1)
    
    if remainder == 0.1:
        return full_innings + 0.333
    elif remainder == 0.2:
        return full_innings + 0.667
    else:
        return float(full_innings)


def get_pitcher_id(name: str):
    """Resolves pitcher name string into statsapi Person ID."""
    if not name or name == 'TBD':
        return None
    matches = statsapi.lookup_player(name)
    return matches[0]['id'] if matches else None


def get_starter_metrics(pitcher_id: int, current_date: str) -> dict:
    """
    Pulls starter metrics, enforces sample size checks (<3 starts or <30 BF) and IP caps,
    and applies 60/40 weighted blend (Rolling 5-Start Hit Rate vs Season Hit Rate).
    """
    if not pitcher_id:
        return None
        
    response = statsapi.get('people', {
        'personIds': pitcher_id,
        'hydrate': f'stats(group=[pitching],type=[season,gameLog],season={CURRENT_SEASON})'
    })
    
    try:
        player_data = response['people'][0]
        stats_lists = player_data['stats']
        
        season_stats = {}
        game_logs = []
        
        for stat_block in stats_lists:
            if stat_block['type']['displayName'] == 'season':
                season_stats = stat_block['splits'][0]['stat']
            elif stat_block['type']['displayName'] == 'gameLog':
                game_logs = stat_block['splits']
    except (IndexError, KeyError):
        return None
        
    games_pitched = season_stats.get('gamesPlayed', 0)
    batters_faced = season_stats.get('battersFaced', 0)
    
    if games_pitched < 3 or batters_faced < 30:
        return None
        
    season_ip = parse_ip(season_stats.get('inningsPitched', '0.0'))
    season_hits = season_stats.get('hits', 0)
    
    recent_ip = []
    recent_hits = []
    last_appearance_date = None
    
    baseline_start_date = datetime.strptime('2026-03-28', '%Y-%m-%d').date()
    curr_date_obj = datetime.strptime(current_date, '%Y-%m-%d').date()
    
    for log in game_logs:
        log_date = datetime.strptime(log['date'], '%Y-%m-%d').date()
        
        if log_date >= baseline_start_date:
            if not last_appearance_date:
                last_appearance_date = log_date
                
            if log['stat'].get('gamesStarted', 0) > 0:
                recent_ip.append(parse_ip(log['stat']['inningsPitched']))
                recent_hits.append(log['stat'].get('hits', 0))
                
        if len(recent_ip) == 5:
            break
            
    rolling_ip = sum(recent_ip) / len(recent_ip) if recent_ip else 0.0

    # 60/40 Weighted Blend: Rolling 5-Start Hit Rate vs Season Hit Rate
    season_h_per_ip = season_hits / season_ip if season_ip > 0 else 0.0
    total_recent_ip = sum(recent_ip)
    total_recent_hits = sum(recent_hits)
    rolling_h_per_ip = (total_recent_hits / total_recent_ip) if total_recent_ip > 0 else season_h_per_ip

    blended_h_per_ip = (0.60 * rolling_h_per_ip) + (0.40 * season_h_per_ip)
    days_rest = (curr_date_obj - last_appearance_date).days if last_appearance_date else 0
    avg_season_ip_per_game = season_ip / games_pitched if games_pitched > 0 else 0
    
    projected_ip = rolling_ip
    
    if avg_season_ip_per_game < 2.5:
        projected_ip = min(projected_ip, 2.0)
    elif days_rest > 20:
        projected_ip = min(projected_ip, 4.0)
    elif projected_ip > 7.0:
        projected_ip = 7.0
        
    return {
        'Projected_IP': projected_ip,
        'Season_Hits': season_hits,
        'Season_IP': season_ip,
        'Blended_H_per_IP': blended_h_per_ip
    }


def get_bullpen_metrics(season: int = CURRENT_SEASON) -> dict:
    """
    Queries StatsAPI for official relief pitching team splits (sitCodes='rp').
    Eliminates pybaseball dependencies and early-season/injured starter bugs.
    """
    teams_response = statsapi.get('teams', {'sportId': 1})['teams']
    
    bullpen_dict = {}
    for team in teams_response:
        team_id = team['id']
        raw_abbr = team.get('abbreviation', '')
        abbr = STATSAPI_TO_STANDARD_ABBR.get(raw_abbr, raw_abbr)
        
        try:
            stats = statsapi.get('team_stats', {
                'teamId': team_id,
                'group': 'pitching',
                'stats': 'statSplits',
                'sitCodes': 'rp',
                'season': season
            })
            
            rp_stat = stats['stats'][0]['splits'][0]['stat']
            ip_str = rp_stat.get('inningsPitched', '0.0')
            bp_ip = parse_ip(ip_str)
            bp_hits = rp_stat.get('hits', 0)
            
            bp_h_per_ip = (bp_hits / bp_ip) if bp_ip > 0 else 1.0
            
            bullpen_dict[abbr] = {
                'Bullpen_IP': bp_ip,
                'Bullpen_Hits': bp_hits,
                'Blended_BP_H_per_IP': bp_h_per_ip
            }
        except (IndexError, KeyError):
            bullpen_dict[abbr] = {
                'Bullpen_IP': 400.0,
                'Bullpen_Hits': 400.0,
                'Blended_BP_H_per_IP': 1.0
            }
        
    return bullpen_dict


def get_projected_hits_payload(target_date: str) -> dict:
    """
    Main calculation engine. 
    Returns a structured dictionary payload containing slate metrics, 
    KISS target games, and disqualified games for UI consumption.
    """
    slate = get_todays_slate(target_date)
    team_data, league_avg_hpg = get_offensive_baselines(CURRENT_SEASON)
    bullpen_data = get_bullpen_metrics(CURRENT_SEASON)
    
    all_games = []
    kiss_targets = []
    disqualified_games = []
    
    for game in slate:
        away_id = game['away_team_id']
        home_id = game['home_team_id']
        
        if away_id not in team_data or home_id not in team_data:
            disqualified_games.append({
                'matchup': f"{game['away_team_name']} @ {game['home_team_name']}",
                'reason': "Missing Team Baseline Data"
            })
            continue
            
        away_abbr = team_data[away_id]['abbr']
        home_abbr = team_data[home_id]['abbr']
        
        away_emoji = TEAM_EMOJIS.get(away_abbr, '⚾')
        home_emoji = TEAM_EMOJIS.get(home_abbr, '⚾')
        
        game_dt_str = game.get('game_datetime', '')
        try:
            dt_utc = datetime.strptime(game_dt_str, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
            dt_local = dt_utc.astimezone(ZoneInfo('America/Toronto'))
            game_time_formatted = dt_local.strftime('%I:%M %p').lstrip('0')
        except Exception:
            game_time_formatted = 'TBD'
        
        away_p_id = get_pitcher_id(game.get('away_probable_pitcher_name'))
        home_p_id = get_pitcher_id(game.get('home_probable_pitcher_name'))
        
        away_starter = get_starter_metrics(away_p_id, target_date)
        home_starter = get_starter_metrics(home_p_id, target_date)
        
        if not away_starter or not home_starter:
            disqualified_games.append({
                'matchup': f"{game['away_team_name']} @ {game['home_team_name']}",
                'reason': "Starter failed sample size check (< 3 starts or < 30 batters faced)"
            })
            continue
            
        away_bp = bullpen_data.get(away_abbr, {'Bullpen_IP': 400.0, 'Bullpen_Hits': 400.0})
        home_bp = bullpen_data.get(home_abbr, {'Bullpen_IP': 400.0, 'Bullpen_Hits': 400.0})
        
        # Starter & Bullpen Projections (Using Blended Hit Rates)
        away_starter_hits = away_starter['Projected_IP'] * away_starter['Blended_H_per_IP']
        away_bp_ip = max(0.0, 8.5 - away_starter['Projected_IP'])
        away_bp_hits_per_ip = away_bp.get('Blended_BP_H_per_IP', away_bp['Bullpen_Hits'] / away_bp['Bullpen_IP'] if away_bp['Bullpen_IP'] > 0 else 1.0)        
        away_bp_hits = away_bp_ip * away_bp_hits_per_ip
        away_pitching_hits_allowed = away_starter_hits + away_bp_hits
        
        home_starter_hits = home_starter['Projected_IP'] * home_starter['Blended_H_per_IP']        
        home_bp_ip = max(0.0, 9.0 - home_starter['Projected_IP'])
        home_bp_hits_per_ip = home_bp.get('Blended_BP_H_per_IP', home_bp['Bullpen_Hits'] / home_bp['Bullpen_IP'] if home_bp['Bullpen_IP'] > 0 else 1.0)        
        home_bp_hits = home_bp_ip * home_bp_hits_per_ip
        home_pitching_hits_allowed = home_starter_hits + home_bp_hits
        
        # Matchup Projections
        away_opp_mult = team_data[away_id]['Opponent_Multiplier']
        home_opp_mult = team_data[home_id]['Opponent_Multiplier']
        
        away_batter_hits = home_pitching_hits_allowed * away_opp_mult
        home_batter_hits = away_pitching_hits_allowed * home_opp_mult
        
        total_game_hits = away_batter_hits + home_batter_hits
        
        if USE_PARK_FACTORS:
            pf = PARK_FACTORS.get(home_abbr, 1.00)
            total_game_hits *= pf
            away_batter_hits *= pf
            home_batter_hits *= pf
            
        avg_proj_team = total_game_hits / 2.0
        
        away_hpg = team_data[away_id]['Hits_per_Game']
        home_hpg = team_data[home_id]['Hits_per_Game']
        season_avg_total_hits = away_hpg + home_hpg
        model_vs_baseline = total_game_hits - season_avg_total_hits
        
        game_dict = {
            'game_time': game_time_formatted,
            'matchup_raw': f"{game['away_team_name']} @ {game['home_team_name']}",
            'matchup_display': f"{away_emoji} {away_abbr} @ {home_abbr} {home_emoji}",
            'away_abbr': away_abbr,
            'home_abbr': home_abbr,
            'away_emoji': away_emoji,
            'home_emoji': home_emoji,
            'away_hits': round(away_batter_hits, 2),
            'home_hits': round(home_batter_hits, 2),
            'total_hits': round(total_game_hits, 2),
            'avg_proj_team': round(avg_proj_team, 2),
            'baseline_hits': round(season_avg_total_hits, 2),
            'delta': round(model_vs_baseline, 2),
            'delta_str': f"+{round(model_vs_baseline, 2)}" if model_vs_baseline > 0 else str(round(model_vs_baseline, 2))
        }
        
        all_games.append(game_dict)
        
        # KISS Filter: Home Batter Hits >= 8.0 AND Away Batter Hits >= 8.0 (Nothing else considered)
        if (game_dict['away_hits'] >= 8.00) and (game_dict['home_hits'] >= 8.00):
            kiss_game = game_dict.copy()
            kiss_game['target_rec'] = "Dual Team Stack"
            kiss_targets.append(kiss_game)
            
    # Sort by Delta descending
    all_games.sort(key=lambda x: x['delta'], reverse=True)
    kiss_targets.sort(key=lambda x: x['delta'], reverse=True)
    
    return {
        'target_date': target_date,
        'all_games': all_games,
        'kiss_targets': kiss_targets,
        'disqualified_games': disqualified_games
    }


if __name__ == "__main__":
    today_str = datetime.today().strftime('%Y-%m-%d')
    results = get_projected_hits_payload(today_str)
    print(f"Slate Execution Complete for {results['target_date']}.")