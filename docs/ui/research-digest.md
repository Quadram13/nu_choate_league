# Hub UI/IA research digest

Primary fetches only. PARTIAL means text arrived and layout, color, or chrome did not. Nothing below is filled in from memory. Archive-host ads and the oocities yellow banner are not original page chrome.

## 0. Source reachability

| Source | URL tried | Status | What actually came back |
| --- | --- | --- | --- |
| Web Design Museum, ESPN 1999 | https://www.webdesignmuseum.org/gallery/espn-com-1999 | PARTIAL | Title plus PNG URL `.../uploaded/fullscreen/espn-com-1999.png`. PNG fetch HTTP 500. Gallery HTML curl HTTP 403 Cloudflare. No pixels, no hex, no columns. |
| ESPN Fantasy, 24 May 2001 | https://web.archive.org/web/20010524004646/games.espn.go.com/cgi/ffl/Request.dll?FRONTPAGE | PARTIAL | Text only. Title "ESPN Fantasy Football". Season-wrap copy, a news blurb, a 6-option receiver poll. Nav, colors, widths stripped by conversion. |
| Reeve FFL '98 | https://www.oocities.org/area51/dimension/5918/Football/Ffl98/ffl98.htm | REACHED | Full HTML, including `bgcolor` and table markup. Mirrored from Geocities, Oct 2009. |
| WFFL '98 (Tripod) | https://cyberweb-design.tripod.com/wffl98/ | UNREACHABLE as a fetch | WebFetch HTTP 500. DNS failed from this host. A search-index snippet exists; treated as unverified fragment, not a page. |
| Eagle FFN 1998 | http://www.geocities.ws/Colosseum/Track/8461/index-2.html | REACHED | Full HTML. Generator comment: Claris Home Page 3.0, file created 7/20/98 1:19 PM. |
| SportsLine / Commissioner.COM | https://www.cbssports.com/info/aboutus/press/1998/fantfoot | REACHED | Full 19 Aug 1998 press release. Product claims, not a screenshot. |
| SportsLine 1997 package | https://www.cbssports.com/info/aboutus/press/1997/ff97 | REACHED | Full 31 Jul 1997 press release. Widening. |
| Lame FFL 1998 | http://www.geocities.ws/Colosseum/Bench/7639/ | REACHED | Full HTML. Widening. |
| Couch Commish FFL 1998 | https://murders.fortunecity.ws/index.htm | REACHED | Full HTML. FrontPage "highway" theme. Last updated 7 Aug 1998. Widening. |
| Deaf FFL 1998 | https://dffl.tripod.com/ | UNREACHABLE as a fetch | DNS failed. Search snippet only. Not used for colors or column counts. |
| Yahoo PR, 2 Sep 1999 | https://web.archive.org/web/20070609002224/http://docs.yahoo.com/docs/pr/release370.html | REACHED | Press release. Names `http://fantasyfootball.yahoo.com/football` and an overall leaderboard. No page chrome. |
| Sportasy, 29 Apr 1999 | https://web.archive.org/web/19990429231416/http://www.sportasy.com/ | REACHED | Acquisition stub only. Points at `http://fantasy.yahoo.com/baseball`. No UI. |
| Yahoo Fantasy Games, 17 Dec 2001 | https://web.archive.org/web/20011217202849/http://fantasysports.yahoo.com/ | PARTIAL | Heading "Football" and five news headlines (AP, CNN/SI). No nav, no tables, no colors. |
| ESPN Fantasy frontpage, 1 Sep 2010 | https://web.archive.org/web/20100901000000/http://games.espn.go.com/frontpage/football | UNREACHABLE | WebFetch timed out. |
| Nearest ESPN Fantasy capture | https://web.archive.org/web/20100914210534/http://games.espn.go.com/frontpage/football | PARTIAL | CDX lists HTTP 200 captures from 20100819074849 through 20100930094248 (lengths ~17–19 KB). WebFetch of 14 Sep 2010 returned the title and one story cluster. Curl of the same URL HTTP 429. No widths, tabs, or hex. |
| ESPN nav guide | https://www.espn.com/espn/print?id=5474529 | PARTIAL | `.com` WebFetch HTTP 403. `.sg` fetch (`/espn/news/story?id=5474529`, 19 Aug 2010) reached MyESPN, Sports tabs, More Sports, and the start of Page 2, then truncated. A search extract of the print URL continues with Fantasy and Watch & Listen. Overlap matches. Full visual guide not seen. Page image URL only: `espn_newnav02_576.jpg`. |
| ESPN Fantasy 2010 press release | https://espnpressroom.com/press-release/espn-kicks-off-15th-anniversary-of-fantasy-football-with-2010-season/ | REACHED | Full 4 Aug 2010 release. Feature list, not a layout. |
| MFL league 16178, 2009 | https://football23.myfantasyleague.com/2009/home/16178 | UNREACHABLE | Live HTTP 500. Wayback CDX for that exact URL returned `[]`. Alternate 2009 host `www17.myfantasyleague.com` did not resolve. |
| MFL company blog, spring 2009 | https://myfantasyleague.wordpress.com/ | REACHED | Posts through 27 May 2009. Commissioner setup paths and module names. |
| MFL customized home, later | https://www49.myfantasyleague.com/2020/home/32317?PRINTER=1 | REACHED | 2020 printer view. Same module system the 2009 blog describes. Not a 2009 skin. |
| Yahoo dark-UI thread | https://fantasy.sports.narkive.com/EgWnUmVm/is-there-any-way-to-change-back-to-the-old-yahoo-fantasy-football | REACHED | Full Y! Answers thread, 23 Aug 2013 through 10 Nov 2013. |
| CBS Fantasy Football, 17 Sep 2009 | https://web.archive.org/web/20090917175536/fantasynews.cbssports.com/fantasyfootball | REACHED | Archive text of the fantasy-news home. Widening for the glossy-portal theme. Colors and pixel widths not in the text. |
| PFR Mahomes, live | https://www.pro-football-reference.com/players/M/MahoPa00.htm | UNREACHABLE | WebFetch timed out. |
| PFR Mahomes, 27 Dec 2024 | https://web.archive.org/web/20241227063804/https://www.pro-football-reference.com/players/M/MahoPa00.htm | REACHED | Full text conversion, 477 lines. QB profile. |
| PFR Mahomes, 18 Jun 2024 | https://web.archive.org/web/20240618175458/https://www.pro-football-reference.com/players/M/MahoPa00.htm | REACHED | Shorter extract. Same header. Summary compares 2023 vs career, not 2024. |
| PFR Barkley game log, live | https://www.pro-football-reference.com/players/B/BarkSa00/gamelog | REACHED | RB career game log. |
| PFR Barkley splits, live | https://www.pro-football-reference.com/players/B/BarkSa00/splits/ | REACHED | Career splits plus career advanced splits. |
| Short-career player page | Peterman and similar fetches | UNREACHABLE | Live fetch timed out. No archive extract. Short-career behavior is inferred only from Mahomes' 1-game 2017 row and Barkley's "Inactive" rows. |
| ESPN.com 1999 vs 2010 essay | https://internet.medialities.org/2020/10/09/espn-com-in-1999-versus-2010/ | REACHED, secondary | 9 Oct 2020 student description of two screenshots. Screenshots themselves were not opened. ESPN.com home, not the fantasy app. |
| Fantasy Football Fools | https://fantasyfootballfools.com/culture/the-new-espncom-is-it-all-a-fantasy/ | REACHED, secondary | Published 9 Jan 2009. Describes an earlier ESPN.com update, not the 18 Aug 2010 nav guide. |

## 1. 1990s grammar

### Page skeleton

Eagle (Claris, 20 Jul 1998) is a centered stack of bands separated by `<HR>`, then one `TABLE BORDER=0 WIDTH="100%"` with three columns:

- Left, `WIDTH=178`: league tasks, one `<P>` per link.
- Center, `WIDTH=211`: a single image, 203×176.
- Right: outside-world link farm.

There is no data table on the Eagle home page. The page is a portal, not a stat sheet.

Reeve is a single column. Three text links, then playoff prose, then two division tables, then a size-2 glossary, then two images (`playoff.gif`, `cellar.gif`), then accolades, then next year's draft order as a name list. `bgcolor="#c8bfb6"`.

LFFL wraps everything in `TABLE WIDTH="468" BGCOLOR="#FFFFFF"` on a page with `BGCOLOR="#EEEEEE"`. 468px is the banner width of the period. Inside that card, a 2×2 portal: champs + week index | standings; current-league links | past-league links + three off-site links.

CCFL is a FrontPage theme page: full-bleed black, a 599×60 banner, then a row of five Java hover buttons (120×24), then numbered news. Footer holds a 468×60 banner (`lpb_banner.gif`). Last updated sits in the footer.

### Nav order, citable

Eagle left rail, top to bottom: EAGLE I (draft 2:00 pm Aug 2), EAGLE II (draft 2:00 pm Aug 9), IMPORTANT DATES, IMPORTANT NEWS, RECORDBOOK (plain text, not a link), TOP 10, RULES & SCORING with `new.gif` 31×12 and the word "Revised", CHAMPIONS PAGE, then "You are visitor # … since 7-11-97".

Eagle right rail, under a "FANTASY LINKS" heading: NANDO, ESPN (`espnet.sportszone.com`), USA TODAY, CBS SPORTSLINE, CNN/SI, INJURY REPORT, then a gap, then FANTASY INSIGHTS, MR.FOOTBALL, IN THE HUDDLE, TROUT TALK, DR.STATS, THE WEBPAGE OF CHAMPIONS, then an NFL.com image button 69×60.

Reeve top links, in order: "Team Information & Logos", "Rosters, Draft and Final", "Regular Season Week-By-Week Scores".

LFFL week index, three labeled rows of numerals, each number its own `<a>`: Lineups 1–16, Predictions 1–8, Results 1–16. Below that, two link columns titled "Current LFFL" and "Past LFFL", plus "Off-Site Links" (NFL.com injury report, 1998 schedule by team, 1998 schedule by week).

CCFL applet nav, left to right: Standings, Teams, Scoring, Schedule, FFL Links. URLs `standngs.htm` (their spelling), `teams.htm`, `scoring.htm`, `schedule.htm`, `links.htm`.

### Table grammar

Reeve division tables: `border=2 cellpadding=5`. Six columns. Header row is an empty cell `width=220`, then W, L, T, PF, PA. All cells are `<td>`, no `<th>`, no row bgcolor, no stripe. Ties are the character `-`, not 0. One table per division (Purdue, then Georgia Tech), four team rows each. Division name is an `<h3>` above the table, not a column.

LFFL standings: `BORDER=0 CELLSPACING=6`. Five columns: Place, Team, Record, Points, Bonus. Header is `<b>` inside `<td>`, not `<th>`. Place and Bonus are centered. Record is zero-padded (`13-01-0`, `07-07-0`). Team name is a link to a team file (`3.html`). Eight data rows, one table, no divisions on this page.

Neither table uses a header fill, zebra stripe, or a highlighted leader cell. Emphasis is outside the grid: Reeve puts "Congratulations" in red and the champion names in bold above the tables. LFFL puts "1998 LFFL Champs!" in a neighboring cell.

Glossary is one line under the Reeve table, `font size=2`: "PF = Points For = total points scored by you." PA defined the same way. The definition is not a footnote marker inside the header.

### Link, color, type

Eagle colors, from `FONT COLOR` on the title and rails: `#000066` (EAGLE, 1998), `#003300` (FANTASY FOOTBALL), `#0000AF` (rules, HRs, most body), `#006600` (draft times), `#660000` (Email the COMMISSIONER, "Revised", visitor line, FANTASY LINKS). Title is `FONT SIZE="+4"`. Countdown line is `SIZE="+1"`. FANTASY LINKS is `SIZE="+3"`. No `face=` attribute, so the browser default (typically Times). No CSS.

Reeve: page `#c8bfb6`. H1 maroon, `size=5`. H2 blue. "Congratulations" red. Body `font size=4`. Glossary `size=2` (one step below the HTML default of 3). No face. Named colors, not hex, except the body bgcolor.

LFFL: `TEXT="#000000" BGCOLOR="#EEEEEE" LINK="#0000FF" VLINK="#990099" ALINK="#0000FF"`. Classic blue unvisited, purple visited. Title is a letter-spacing trick: initials at `SIZE=+4` bold, the rest of each word at `SIZE=+3` ("Lame Fantasy Football League"). No face.

CCFL: `bgcolor="#000000" text="#FFFFFF" link="#FFCC00" vlink="#FFFF99" alink="#FF3300"`, background `_themes/highway/waybkgnd.gif`. `font face="verdana, arial, helvetica"`. Buttons: `color="#008000"`, `hovercolor="#00FF00"`, `textcolor="#FFFFFF"`, `effect="glow"`. This is the one 1998 page with a real font stack, and it is a FrontPage theme, not hand HTML.

### Signature chrome

- Email the commissioner, in the header, with a 25×31 paw gif (Eagle). Address was `wolf1948@erinet.com` in the text conversion; the live HTML obfuscates it. LFFL list item: "Submit Transactions and Lineups to the Commish via Email". CCFL opens with "Email or call me ASAP".
- IMPORTANT DATES / IMPORTANT NEWS as first-class nav items, same weight as rules and champions (Eagle).
- CGI countdown image and CGI visitor counter (Eagle, "since 7-11-97"). LFFL has a counter image in the footer. Both URLs are `geocities.com/cgi-bin/...` and are dead now.
- `new.gif` beside a revised rules link.
- Geocities "get your own Free Home Page" badge, member gifs, flag gifs. CCFL adds an IE4 `dynamicanimation="flyBottom"` on the hurry line (`left: 10000` until script runs) and Java `fphover.class` buttons.
- Reeve playoff block before standings, including a Toilet Bowl line, then a draft-order list that ends "ffl98 champ bowl loser / ffl98 cahmp bowl winner". Typos are still in the source ("toal", "cahmp", LFFL "Fianl Score").
- ESPN 2001 poll, one column, six rows: "Cris Carter, Min", "Jacquez Green, TB", "Torry Holt, StL", "Raghib Ismail, Dal", "Ed McCaffrey, Den", "Keenan McCardell, Jac". Name, comma, team abbreviation. The page also points at "leaderboards of the FFL Traditional and Performance games" without showing the board.

Commissioner.COM, 19 Aug 1998, claimed features a ticket can name but not draw: unique league URL, chat room, publishable news, scrolling CommWire, CommPoll, "Fantasy Football LIVE" updated after every play, weekly emailed stat reports, on-demand reports "by any conceivable category", message board, live draft with time limit, pick queue, and auto-pilot. Price line was $99.95 per league. The 31 Jul 1997 release already promised a personalized league site with chat, individual team pages, and emailed reports, for less than $50 a league, plus Advance Scout (projections and rankings) and a salary-style Challenge game. No screen was attached to either release.

Yahoo, 2 Sep 1999: fantasy football lived at `fantasyfootball.yahoo.com/football`, and the public could "track how Green is faring against all fantasy team owners on the overall leaderboard." Sportasy's 29 Apr 1999 page is only the handoff to Yahoo. The 17 Dec 2001 Yahoo fantasy home, in the text that survived, is a sport heading plus a five-line news list. That is not enough to specify a Yahoo 2001 layout.

### Of the era, versus a costume

Of the era, because it is in the bytes: `FONT` tags, relative sizes, `<HR>` bands, a 468-wide white card, `border=2` standings, week numbers as the entire navigation, mailto-the-commish in the header, CGI counter and countdown, a `new.gif`, Claris and FrontPage generator comments, a "last updated" line, blue `#0000FF` / purple `#990099` links, a right-rail farm of Nando / SportsZone / SportsLine / CNNSI, joke division names, a toilet bowl, and typos left in the HTML.

A costume gives itself away with a CSS grid pretending to be a table, a web-safe palette used tastefully, working hover states, a responsive column, a fake counter that is a styled div, perfectly aligned type, and no last-updated line.

Aged fine: blue links, one small standings table per division, a glossary sentence under the table, left rail = our league and right rail = the outside world, week numerals, email-the-commish as a visible address. LFFL's gray page plus white 468 card plus black text is still a readable stat surface.

Aged poorly: `SIZE="+4"` shouting, size-2 glossary type, CGI images that are now broken, Java glow buttons, IE fly-in that parks content at `left:10000` until script runs, visitor counts, all-caps link lists, and link farms whose targets died. CCFL's yellow `#FFCC00` on black is a chrome theme, not a stat-table theme; that home page has no stat grid.

### Ticket-feeding observations

- Eagle home is three columns, borderless, 178 / 211 / rest. Left order: two drafts, IMPORTANT DATES, IMPORTANT NEWS, record book, TOP 10, RULES & SCORING, CHAMPIONS, visitor counter. Right order starts NANDO, ESPN, USA TODAY, CBS SPORTSLINE, CNN/SI, INJURY REPORT.
- Reeve standings are two tables, not one. Columns: (blank 220px), W, L, T, PF, PA. `border=2 cellpadding=5`. Ties render as `-`. No stripe, no header fill, no leader-cell color.
- LFFL standings columns: Place, Team, Record, Points, Bonus. Record format `13-01-0`. The page frame is 468px white on `#EEEEEE`, links `#0000FF` / visited `#990099`.
- Week UI is the row `Lineups 1 2 3 … 16` plus `Results 1 … 16`. Each numeral is its own link. That is the pagination control.
- Put "Email the COMMISSIONER" in the header band, in `#660000`, not in a footer. Pair it with an IMPORTANT DATES link of equal weight to rules.
- Glossary is a sentence under the table at `font size=2`, not a hover dictionary. Do not copy size 2; it is the part that aged badly. Keep the placement.
- Theme 1 color tokens actually used: navy `#000066`, green `#003300` / `#006600`, link blue `#0000AF` and `#0000FF`, maroon `#660000`, page tan `#c8bfb6`, page gray `#EEEEEE`, card white, visited purple `#990099`. Body type is unset (Times). The only sans stack in the set is CCFL's Verdana, and it belongs to the black FrontPage theme.
- Do not build the counter, the countdown GIF, the `new.gif`, the Java hover button, or the fly-in. They are the tells that aged into broken images and invisible text.

## 2. Late-2000s / early-2010s grammar

### What the ESPN pages did not yield

No pixel width, no mega-nav screenshot, no left-rail or right-rail measurement, and no matchup-card markup came back from `games.espn.go.com`. The 14 Sep 2010 fantasy frontpage text is a title — "Fantasy Football - Free Fantasy Football Leagues, Rankings and more -- ESPN" — plus one lead: "Brandon Jackson To Start", with three bylines (Berry, Karabell, a third "Joyner: WR/QB pickups"), a photo credit "Howard Smith/US Presswire", "Matthew Berry Home | Feedback", and three dated links "Fantasy Focus Football: 9/13", "9/10", "9/9". Treat that as a news portal with a columnist module, not as a measured shell.

### Site nav order

From the 19 Aug 2010 guide, items confirmed on the `.sg` fetch, in this order: MyESPN, Sports tabs (examples named: NFL, NBA, MLB, College Football), More Sports, then the guide moves to Page 2 & Commentary before the fetch truncated.

The search extract of the print article, which matches that overlap and then continues, inserts two items and gives this sequence:

1. MyESPN — personalize which sports appear, and in what order; favorite teams highlighted in the scoreboard.
2. Sports tabs — news, commentary, video, scores, schedules.
3. More Sports — every sport section, plus featured topics.
4. Fantasy — "Access to all Fantasy news and leagues, mini-games and links to your teams."
5. Watch & Listen — video, podcasts, SportsCenter, TV and radio listings.
6. Page 2 & Commentary.

Fantasy is a labeled destination in that guide. It is not described there as item 1. The Jan 2009 Fools post is a different redesign: it says "Fantasy & Games" was fourth after Sports, Columnists, and Page 2, and complains that reaching a league had been two dropdowns, a sidebar link, and one of two login boxes. Do not merge that 2009 menu with the August 2010 guide.

A secondary essay (screenshots not opened) says the 12 Oct 1999 ESPN.com home used a side sport menu and put polls, contests, and fantasy games beside the logo, and that the 30 Jun 2010 ESPN.com home used a red page, a top menu, a search box, and larger photos. That is ESPN.com, not Fantasy Football.

### League chrome that was actually attested

No full ESPN league tab strip was captured. Two contemporary posts, not screenshots, say the tabs above the league name include League, then My Team. Under My Team: Roster, Add Player, Drop Players. The My Team page has a team icon and "edit team settings" asking for location and name, which together become the team name. URLs in use in 2010: `games.espn.go.com/ffl/leagueoffice?leagueId=` and `games.espn.go.com/ffl/clubhouse?leagueId=&teamId=&seasonId=2010`. A scoreboard is something an opponent "launches"; it was not given a tab index.

Do not ship a ticket that says the ESPN 2010 order was Roster / Scoreboard / Standings / … . That order was not in any page we reached.

### Feature grammar from the 4 Aug 2010 release

These are product claims. Nobody in this pass watched a Sunday refresh.

- FantasyCast: live chat with experts, real-time player-by-player scoring, live updating box scores and results, integrated Gamecast, and a comparison to the opposing roster. The release says "live" and "real-time". It does not say "without a reload".
- Inline player cards on the roster: weekly projections, recent ESPN news, game-by-game stats, graph views, "without leaving their own roster."
- FAAB as an elective replacement for waivers. Player watch lists (add/flag) and player comparison.
- Share icon to Facebook, MySpace, and Twitter, for leagues or team notifications. MySpace dates the chrome.
- Smack boards: chat windows on league pages and on scoring pages.
- Standard leagues of 8 and 12, both on public leaderboards. Public leagues with custom settings. Auction draft against a $200 budget. Live draft, automated draft from pre-rankings, keeper entry, draft-pick trading.
- League message boards, chat, and polls inside the league.
- Insider Recommends sits inside the draft window (next-pick advice; auction value vs overpriced). That is a paid layer on the draft UI, not on the stat table.

### CBS Fantasy home, 17 Sep 2009 (the shell we could actually read)

Top utility: "Web | Fantasy News | Player" plus "Track your favorite teams and players" with Register / Log In.

Sport bar, in order: Home, Fantasy Football, Fantasy Baseball, Fantasy Basketball, Fantasy Hockey, College / More Sports, Fantasy Products, My Fantasy Teams.

Football subnav, long form, in order: Fantasy Football Today, Draft Central, Downloadable Draft Kit, Player News, Stats, Players, Depth Charts, Columns, Injury Report, Projections, Rankings, Red Zone Stats, Teams, Schedules, Scores, Standings, Message Boards.

A shorter football bar also appears: Football Home, Fantasy Football Today, Draft Central, Player News, Stats, Players, Columns, Injuries, Projections, Rankings, Teams, Schedules, Message Boards.

Under that, three product boxes before any story: "Try it FREE for 14 days" (customizable commissioner, keeper options, archived data, mobile), "Compete for Cash" (live scoring and stats), "Play for FREE" (public and private leagues). Then a lead story, a "Related Links" list of eight bullets, then a one-line injury ticker ("Player: blurb …" repeated, ending "View All of Today's Updates").

Projection module: tabs QB, RB, WR, TE, K, DST. Ten rows each. Columns change with the tab:

- QB: Player, YDS, TD-INT, PTS. Cell style `A. Rodgers`, `254`, `1-0`, `23`.
- RB: Player, RUSH, REC, TD, PTS.
- WR and TE: Player, REC, YDS, TD, PTS.
- K: Player, FG, XP, PTS.
- DST: Team, YDS, PA, SCK, TO, PTS. Team is a nickname ("Vikings"), not an abbreviation.

Rankings module repeats the same six tabs as two-column numbered lists, 1–5 beside 6–10.

That is the late-2000s stat grammar we can cite: position tabs, initial-plus-last-name, a PTS column on every tab, and a short fixed row count (10), with "View All" as the escape hatch.

### MFL, for a single-league hub

The 2009 league home URL is unreachable. The March–May 2009 blog is the primary description of the commissioner tools:

- Skins: "For Commissioners > Setup > Appearance > Select a Skin". Named skins include "Irish" and "Seasonal" (the skin changes by itself through the year). A skin cannot be selected if the league uses a Template. The blog hoped to combine them later. As of 17 Mar 2009 they were mutually exclusive.
- Home composition: "For Commissioners > Setup > Appearance > Home Page Modules and Tabs Setup". The commissioner adds a module and positions it. Named modules: League Championship Plaque (franchise and owner, per season, on a plaque graphic), League Standings Legend (only after a legend is defined), and the chat module.
- Chat module icons, 2 Apr 2009: Speaker (audio beep on a new message, off by default), Clear (commissioner only), New Window (chat in a separate window).
- Standings can freeze after a chosen week ("Stop updating league standings report after week:", default Week 21) while scores and stats keep updating.
- Owner customization, "For Owners > Franchise Setup", split that spring into Customize (logos, links, appearance, sound) and Contact Info (including which emails to receive: trade proposed, opponent lineup submitted, weekly results).
- Owners set a trade-offer expiry, default one week.

The 2020 printer view shows what that module home looks like after a commissioner has arranged it. Tab names present, DOM order, not confirmed as left-to-right: NFL Pools, Records, Past Champions, Weekly, Results, Standings, Transactions, Top Players, Rosters, Overview, My Team, Live Scoreboard, Gameday, Main. Because order is configured per league, do not hard-code this list as the MFL default.

Modules on that page, top to bottom: Pending Trades, Login, Welcome, Live Scoring (Week 16, with "Live Scoring Summary" and "Live Scoring Details"), 10 Newest Message Board Topics, League Chat, Franchise Owner Activity (owner, "last visited … days ago"), Countdown To (trade deadline, absolute date), Playoff Bracket, 3rd Place, Toilet Bowl, then one standings table per division.

Standings columns on that 2020 page: Franchise, W-L-T, Pct, GB, Strk, PF, Avg PF, PA, Avg PA, Div W-L-T. Bracket cell format: `#4: Screaming Eagles(162.25)`. Player-record cell format: `Portis, Clinton WAS RB` (last, first, team abbreviation, position). Those two cell patterns are the logo-free identity grammar.

### Logos, live scoring, social

Logos: MFL owners attach logos in Customize. ESPN My Team has a team icon plus location and name. No logo size, file type, or placement was in the sources.

Live scoring: claimed by FantasyCast (2010) and by Commissioner.COM "after every play" (1998). The MFL home exposes it as two links under a week label, plus a chat module that can pop out. No XHR trace was captured, so "updates without reload" stays a claim.

Social: 2010 Share goes to Facebook, MySpace, Twitter. Smack-talk is an in-page chat window, not a share sheet. The 1998 equivalent is the league chat room and the CommPoll.

Aged poorly, from sources rather than taste: MySpace as a share target; two login boxes (2009 complaint); fantasy buried under dropdowns (the problem the 2010 guide was answering); house-ad boxes stacked above the news (the CBS page has three before the lead); a dark stat surface (section 5).

### Ticket-feeding observations

- Top-site order to cite, with the Fantasy line flagged as search-extract of a 403 page: MyESPN, Sports, More Sports, Fantasy, Watch & Listen, Page 2. Fantasy's job description is "news and leagues, mini-games, and links to your teams."
- Inside a league, the only ordered pair we can cite is League, then My Team. My Team contains Roster, Add Player, Drop Players, a team icon, and location + name. Do not invent the rest of the tab strip.
- The roster card, per the 2010 release, shows projections, news, a game log, and a graph without leaving the roster. That is the card. A matchup card's internal layout was not on any reached ESPN page.
- CBS 17 Sep 2009 is the measurable portal: sport bar, then a 17-item football bar ending Scores, Standings, Message Boards, then three product boxes, then a story, then a one-line injury ticker, then position-tabbed top-10 tables. QB columns are Player, YDS, TD-INT, PTS. RB columns are Player, RUSH, REC, TD, PTS. Names are `A. Rodgers`.
- MFL commissioner IA, cite the paths verbatim: Setup > Appearance > Select a Skin, and Setup > Appearance > Home Page Modules and Tabs Setup. Skins and templates were exclusive in March 2009. Owners, not the commissioner, set logos and links.
- One league home is a stack of small modules: live scoring for the current week (summary and details as two links), chat, countdown, bracket, standings. The standings row worth copying is Franchise, W-L-T, Pct, GB, Strk, PF, Avg PF, PA, Avg PA, Div W-L-T, with a legend module for clinch marks.
- Player identity strings to pick from, by era: `Cris Carter, Min` (2001 poll), `A. Rodgers` (2009 projections), `Portis, Clinton WAS RB` (MFL record line).
- Freeze standings after the regular season without freezing stats. That split is already a commissioner switch, not a second page.

## 3. PFR anatomy

Pages read: Mahomes QB profile, archive 27 Dec 2024 (a Jun 2024 capture shows the same header with the summary year rolled back). Barkley RB career game log and career splits, live. No separate short-career profile loaded. No headshot, jersey number, or photo caption appeared in any identity block. A converter can drop images, so absence of a photo is not proven. Jersey number shows up later as column `No.` (Mahomes `15` on snap counts and adjusted passing), not in the header.

### Order on the QB profile

1. H1 name.
2. Legal name plus nicknames in parentheses.
3. Position and throwing hand. Height and weight, imperial then metric. Team name. Born (date and city). College, with a "College Stats" link. Weighted Career AV and an all-time rank. High school. Draft (team, round, overall, year). Instagram handle. A "More bio, uniform, draft info" disclosure.
4. Award chips as a short list: "6x Pro Bowl", "2x All-Pro", "3x SB Champ", and similar.
5. SUMMARY strip. Two columns, labeled with the current season and "Career". Rows seen: G, AV, QBrec, Cmp%, Yds, Y/A, TD, Int, FantPt. FantPt is on the summary, not only on a fantasy page.
6. In-page jump list: 2024 Game Logs, Passing, Advanced Passing, Adjusted Passing, Fantasy, Rushing & Receiving, Advanced Rushing & Receiving, Defense & Fumbles, Scoring Summary, Snap Counts, Similar Players, Leaderboards / Awards / Honors, Hall of Fame Monitor, All-Pro Teams, Combine, Trades, Transactions, FAQ, Full Site Menu.
7. Current-season game log only, then "Next Game" and a "More:" link row: Game Log, Splits, Fantasy, TD Scores, TD Passes, Passing Plays, Receiving Plays, Rushing Plays.
8. Passing, regular season, then a second passing table that is the postseason (it starts at 2 games in 2018). The postseason label itself was flattened by conversion; the row shape is what identifies it. Same pattern repeats for rushing, defense, and scoring.
9. Footnotes, then Advanced Passing (regular and postseason), a note that advanced stats update the Wednesday after the week's games, then an "Upgraded" marker and Adjusted Passing.
10. Rushing & Receiving, Advanced Rushing & Receiving, Defense & Fumbles, Scoring Summary, Snap Counts ("Since 2012"), Hall of Fame Monitor (a single rank sentence), Trades ("since 1994"), Transactions ("since 2002"), FAQ (one question per bio field), then year-link lists for Passing Plays, Receiving Plays, Rushing Plays.

The jump list names Fantasy, Similar Players, Leaderboards, All-Pro, and Combine. Those sections were not in the body text that came back. Do not specify their columns.

### Column sets

Current-season QB log, grouped Passing then Rushing. Identity columns: Date, Team, (blank or `@`), Opp, Result (`W 29-10`). Passing: Cmp, Att, Cmp%, Yds, TD, TD%, Int, Int%, Lng, Y/A, AY/A, Y/C, Rate, Sk, Yds, Sk%, NY/A, ANY/A. Rushing: Att, Yds, TD, Lng, Y/A, Fmb. `@` is its own column between team and opponent.

Season passing table: Season, Age, Team, Lg, Pos, G, GS, QBrec, Cmp, Att, Cmp%, Yds, TD, TD%, Int, Int%, 1D, Succ%, Lng, Y/A, AY/A, Y/C, Y/G, Rate, QBR, Sk, Yds, Sk%, NY/A, ANY/A, 4QC, GWD, AV, Awards. Footer rows: `8 Yrs` and `17 Game Avg`. The Jun 2024 capture used Year, Tm, No. instead of Season, Team, Lg on the adjusted table. Header vocabulary moved; do not freeze one era's abbreviations as eternal.

Awards cell is a compact code: `PB, AP-1, AP MVP-1, AP OPoY-1`. Playoff rows use `SB MVP`.

Adjusted passing adds `No.` and index stats (`Y/A+`, `NY/A+`, `AY/A+`, `ANY/A+`, `Cmp%+`, `TD%+`, `Int%+`, `Sack%+`, `Rate+`) with a legend line: `* Selected to Pro Bowl, + First-Team AP All-Pro, Bold indicates league leader`.

Rushing & Receiving groups Rushing, Receiving, Scrimmage. Snap counts: Year, Age, Tm, Pos, No., G, GS, then Off / Def / ST as Num and Pct.

RB career game log (Barkley), one table titled Regular Season, groups: Rushing, Receiving, Scoring, Fumbles, Off. Snaps, Def. Snaps, ST Snaps. Identity: Rk, Year, Date, G#, Week, Age, Tm, Opp, Result, GS. GS is `*` for a start. Rushing Att, Yds, Y/A, TD. Receiving Tgt, Rec, Yds, Y/R, TD, Ctch%, Y/Tgt. Scoring 2PM, TD, Pts. Fumbles Fmb, FL, FF, FR, Yds, TD. Snaps Num, Pct three times. A Status column. Rows with no line render as the word `Inactive` and drop the stat cells (seen on 2019-09-29, 2019-10-06, 2019-10-10).

Mahomes' 2017 season is one ordinary row (`G=1`, `GS=1`) inside the same career table. A short career does not get a different page. It gets fewer rows of the same columns.

### Splits

Barkley career splits are one table, repeated group header, columns fixed: Split, Value, G, W, L, T, then rushing (Att, Yds, Y/A, TD, A/G, Y/G), receiving (Tgt, Rec, Yds, Y/R, TD, Ctch%, Y/Tgt, R/G, Y/G), scoring (2PM, TD, Pts), fumbles (Fmb, FL, FF, FR, Yds, TD).

Split groups, in the order they appeared: League, Place (Home, Road), Result (Win, Loss, Tie), Final Margin (0-7, 8-14, 15+), Month, Game Number (1-4, 5-8, 9-12, 13+), Day, Time (Morning, Early, Afternoon, Late), Conference, Division, Opponent (one row per franchise, historical names in the label), Playoffs (Total, Super Bowl, Conference Championship, Divisional, Wild Card), Stadium (dome, outdoors, retroof).

Advanced splits are a second table with a shorter stat set (Att, Yds, Y/A, TD, 1D, and the receiving equivalents). Groups seen: Down, Yards To Go, Down & Yards to Go, Field Position (including Red Zone and Opp 1-10), Score Differential, Quarter (plus OT, 1st Half, 2nd Half), Game Situation (leading/tied/trailing with <2 and <4 min), Snap Type & Huddle, Play Action, Run/Pass Option, Time in Pocket. The extract cut off inside Time in Pocket.

### Glossary, leaders, cross-links, disclosure

Footnote, quoted, under the passing tables: "Bold season totals indicate player led league. Gold career totals indicate an all-time career record. Italic career totals indicate player is active leader." Next line: "Black Ink appears for stats with a leaderboard." Gold is the word they used. No yellow cell fill and no hex were in the extract.

Header cells on the game log carry the glossary in the header itself. Examples that survived conversion: rank "is a count of the rows from top to bottom. It is recalculated following the sorting of a column." Y/A cites the leader minimum. Fumbles: "ALL fumbles by the player on offense, defense, and special teams. Available for player games since 1989." So the table is sortable, and sorting recomputes Rk. The full log was in the HTML (2018 weeks 1–17 were all present). This is full-load plus client sort, not virtual scroll and not paged rows.

Cross-links seen as text: College Stats; team name in the header; team abbreviation in the table; "More:" row to Game Log, Splits, Fantasy, TD logs, and play-type pages; year lists at the bottom of the game-log page (Regular Season years, Postseason, Career; Advanced Gamelogs by year; Splits by year plus "Player Split Finder"; Fantasy by year plus "Player Game Finder"; Versus Finder; play-type years; "College Football at Sports-Reference.com"). Opponent filter on the log: "Show Games vs." and a list of every franchise. Whether that filter reloads the page was not visible.

Progressive disclosure that was real: "More bio" ; current-season log on the profile and the career log on another URL; splits and fantasy on other URLs, each with a year list; inactive weeks collapsed to one word; jump links down a long profile. Not seen: a show-more button, a hidden-column toggle, or a virtualized body.

Stathead: the Barkley game log shows the line "Become a Stathead & surf this site ad-free." That is an ads upsell. The advanced splits table loaded in full on the free URL. No column-level paywall was visible. The Mahomes profile extract did not include that sentence; it did include an "Upgraded" marker immediately before Adjusted Passing, with no explanation of what is gated. Do not spec a Stathead column lock from these pages.

### Ticket-feeding observations

- Player header order: name, nicknames, position, hand, height/weight, team, born, college link, career value, high school, draft, then a disclosure for the rest of the bio. Awards as chips. No jersey number in that block.
- First stat object is a two-column summary, this season vs career, and it includes FantPt. Then the current season's games only.
- Career log, splits, and fantasy are separate pages, each with a year list plus Career. The profile's jump list may name Fantasy without the fantasy table being on the profile.
- Leader treatment, cite the footnote: bold = led the league that season, gold = all-time record, italic = active leader, black ink = the number links to a leaderboard. Do not spec a yellow cell.
- QB log identity is Date, Team, `@` or blank, Opp, Result. RB log identity adds Rk, Year, G#, Week, Age, GS=`*`. Inactive is a status word, not a row of zeros.
- Splits are one repeating table. Group order starts League, Place, Result, Margin, Month, Game Number, Day, then opponent and playoff round. Put the group name in a row, not in a new page.
- Glossary lives in the column header, and a one-line footnote under the table carries bold/gold/italic. Sort may reorder rows; Rk must be recomputed.
- A 1-game season is the same table with one row. Do not design a second, "short career" template.

## 4. Disclosure patterns for a server-rendered hub

Constraints used below: three switchable themes, a players index that is 5.2 MB with about 520 career rows, about 1370 season rows, and boards, and a no-JS fallback. Era mapping is from the pages above, not from a general history of the web.

| Pattern | One-line trade | Themes | 5.2 MB index | No-JS |
| --- | --- | --- | --- | --- |
| Full-load (status quo) | One URL, complete, printable, and theme-safe. | Trivial: one render, one stylesheet. | This is the failure. 520 + 1370 rows plus boards are why the document is 5.2 MB. | Works, and that is its only advantage here. |
| Pagination | Small, cacheable, addressable pages. | Each page is a normal document. Theme is a class or a cookie, not a chunk to reappend. | Right cut for a season log or a week. Wrong as the only way to scan 520 careers unless the page size is a chosen number (25 or 50) with a stable sort. | The LFFL pattern: numerals are links. No script required. |
| Load-more / infinite | Feels fast, hides the real size. | Theme switch mid-list must not drop already-loaded rows or restripe them against a different background. | Does not help if the first response still contains the hidden rows. | A "next" link is required or the rest of the league does not exist. Infinite scroll has no no-JS form. |
| Summary-first, sections expand | Home stays a portal; depth is opt-in. | Expanders must be structure (`<details>` or a URL), not a theme-colored box baked into HTML. | `<details>` that wraps all 1370 rows still ships 5.2 MB. Expansion has to be another request. | `<details>` works without JS. For a payload this size, prefer a link, which also works. |
| Deferred section fetch (HTMX or fetch) | First paint is identity, summary, and one board. | Fragment HTML uses classes only. No inline `FONT COLOR`, or the other two themes cannot restyle the fragment. | The right cut for this page: career table, season table, and each board are their own URLs. The 5.2 MB document becomes a shell. | Every fragment URL is a normal link. HTMX only upgrades the link. PFR already did the non-JS version. |
| Sticky header, big page | Wide logs stay readable. | Header background has to be opaque in all three themes or rows show through. | Saves nothing on the wire. | `position: sticky` needs no script. Use it on the log page, not as a substitute for splitting the index. |
| Tab-deferred boards | One position, one week, one board. | Tab chrome is themed; the panel is ordinary HTML. | CBS shipped 10 rows times 6 positions, not 1370. If all panels are in the document and hidden with CSS, the 5.2 MB is still paid. | CBS position tabs and PFR year lists are real navigation. A JS-only tab that `display:none`s the other boards fails no-JS and fails the payload budget. |
| Virtual scroll | Paints a window of rows. | Stripes, sticky headers, and row colors drift because the row index is no longer the DOM index. Three themes make that worse. | Could shrink paint, not the server-rendered document, unless the server also pages. | Find-in-page, print, and no-JS all break. Not appropriate for this hub. |

Era assignment, so the themes do not share one disclosure widget:

- Theme 1, dense portal. The home page full-loads a small standings table (Reeve's 8 rows, LFFL's 8 rows) and nothing else. Depth is numbered links: week 1–16, and separate pages for rules, rosters, transactions. That is pagination plus a summary home. Do not infinite-scroll a link farm. Do not sticky-header a 6-column table.
- Theme 2, glossy shell. The home is modules (live week, chat, countdown, one standings card, a top-10). Boards open as tabs that are real links, the way CBS splits QB/RB/WR/TE/K/DST and offers View All. Live scoring is a module with Summary and Details links, not the players index embedded in the card.
- Player pages, all themes. Copy the PFR split, not the PFR profile's habit of stacking every advanced table on one URL. Summary strip (season vs career, including fantasy points), current-season log on the page, career log and splits and fantasy on their own URLs. Sticky header on the log only. Sort is an enhancement; the rows are in the HTML.

No-JS bar for the whole hub: theme choice is a link or a form, not only a script that toggles a class. Disclosure is an href. A ticker, if theme 1 has one, has a static list in the page, because the 1998 Deaf league page already had to tell people with no JavaScript that the tape would be missing. CCFL's fly-in is the counterexample: content starts at `left:10000` and never appears if the script does not run.

### Ticket-feeding observations

- Do not full-load the 5.2 MB index. Split it the way PFR splits a player: summary and one board on the URL, career rows and season rows and the other boards on their own URLs.
- Theme 1 pagination is the numeral row `1 2 3 … 16`, one link per week. Theme 2 pagination is a tab that is a link (position, or View All), plus a module that shows 10 rows.
- Hidden rows are not a savings. `<details>`, `display:none` tabs, and load-more all fail the payload if the 1370 rows are in the first document.
- HTMX may upgrade those links. It may not be the only way to reach the section.
- Sticky headers on the game log, opaque background per theme. No virtual scroll.
- Theme switching without JS, or the no-JS fallback is stuck in whichever theme the server guessed.

## 5. Anti-patterns

- Black stat surface. Mark, 25 Aug 2013: "stats and numbers don't go well with black (dark) background." Patrick, 2 Oct 2013: "glitchy and impossible to see." Felix, 24 Aug 2013: Trading Block, Messages, and Matchups were still the old UI. There was no revert control; the suggested workaround from one reply was a different Yahoo URL, not a setting. Lesson: a dark theme may paint chrome dark and must paint the table light (LFFL already used `#FFFFFF` on `#EEEEEE`). Every surface, including matchups and messages, ships in the same pass. Ship a light-table variant inside the dark theme rather than a toggle that users cannot find.
- Half a migration. Same thread. Lesson for three themes: a theme is done when roster, scoreboard, standings, and the player page all use it. A glossy header on an unthemed table is the 2013 failure.
- Plugin chrome. CCFL nav is a Java applet. The hurry line is invisible until an IE4 script runs. Eagle's countdown and both visitor counters are CGI images and are already broken. Lesson: theme chrome is HTML and CSS. No applet, no generated-image counter, no content positioned offscreen until script runs. Flash was not present on any page fetched here; the reached cousins are the applet and the CGI image. Do not add Flash to look period-correct.
- House ads above the work. CBS 17 Sep 2009 places three product boxes before the lead story. Archive hosts now inject 728×90 and 300×250 around the 1998 pages; the originals already carried a 468×60 badge and a Geocities footer. Lesson: one promo slot. The right column is a labeled link list (Eagle's FANTASY LINKS), not a second stack of ads that pushes the 6-column table down.
- Ticker abuse. Commissioner.COM sold a scrolling CommWire. The Deaf league snippet (unverified fetch, so do not style from it) already needed a no-JS apology for a ticker tape. Lesson: if theme 1 has a tape, it is one static line of items the server rendered, with motion as an enhancement that respects reduced motion. The items exist when script does not.
- Type below the default. Reeve's glossary is `font size=2`. Eagle's title is `SIZE="+4"`. Yahoo's complaint is "i cant really see much" without a pixel value, so do not invent one. Lesson: stat cells stay at least the browser default. The glossary sentence can be smaller than the table and still must be readable. One display line per page, then normal-case links. All-caps rails and +4 titles are the costume.
- Two ways in. The Jan 2009 Fools post: two login boxes, and a league that took two menus plus a sidebar. Lesson: one login, and Fantasy (or this league) is a top-level destination, which is what the August 2010 guide was for.
- Link farms as the product. Eagle's right rail is correct as a labeled list of outside sites. It is a bad primary nav, and those URLs are dead. Lesson: league tasks keep the Eagle left-rail order; outside links stay in a box titled like FANTASY LINKS.
- Poll instead of the standings. The 2001 ESPN fantasy home, in the text we got, is a thank-you and a six-row receiver poll. For this hub the first data object is the current week or the standings, and a poll is a module under it.
- Yellow-on-black as a stat theme. CCFL's `#FFCC00` links on `#000000` are chrome. That page has no stat table. Do not reuse it for numbers. Combined with the Yahoo thread, the rule is: dark chrome, light grid, dark text, blue links.
- Leader color we did not see. PFR's word is gold, applied to career-record totals, plus bold and italic. Specifying a yellow cell fill would be an invention.

### Ticket-feeding observations

- Dark theme: light table surface, dark text, blue links. Cite Yahoo, Aug 2013, and LFFL's `#FFFFFF` card.
- A theme does not ship until matchups, messages, roster, and player tables all use it.
- No Java, Flash, CGI counter, or offscreen-until-script chrome. CCFL is the specimen.
- One login. Fantasy or the league is a top-level tab. One promo box, not three, and not a 300px rail.
- Glossary and labels at or above default type size. `font size=2` is the measured mistake.
- Ticker content is in the HTML. Scrolling is optional.
- First module is standings or the current week, not a poll and not a house ad.
- Leader marks are bold, gold, and italic, with the footnote PFR prints. Not a yellow fill.

## Sources not to over-cite

WFFL Tripod, Deaf FFL Tripod, the 1 Sep 2010 ESPN snapshot, MFL league 16178, live Mahomes, and any short-career profile were not retrieved as pages. The Jan 2009 Fools menu and the 2020 student essay are secondary. The Fantasy line in the August 2010 nav guide is a search extract of a URL that returned 403 to a direct fetch; the items above it were confirmed on espn.com.sg.
