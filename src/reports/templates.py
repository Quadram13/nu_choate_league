"""HTML templates and CSS styling for reports."""

def get_css_link(in_subdirectory: bool = False) -> str:
    """
    Generate CSS link tag with correct relative path.
    
    Args:
        in_subdirectory: Whether the page is in a subdirectory
        
    Returns:
        CSS link tag with appropriate path
    """
    if in_subdirectory:
        # From subdirectory (2024/, 2025/, all_time/), go up one level
        return '<link rel="stylesheet" href="../style.css">'
    else:
        # From root (index.html), use relative path
        return '<link rel="stylesheet" href="style.css">'


def get_html_template(title: str, nav: str, content: str, in_subdirectory: bool = False) -> str:
    """
    Generate complete HTML page with external CSS link.
    
    Args:
        title: Page title
        nav: Navigation HTML
        content: Main content HTML
        in_subdirectory: Whether the page is in a subdirectory (for CSS path)
        
    Returns:
        Complete HTML document as string
    """
    css_link = get_css_link(in_subdirectory)
    
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    {css_link}
</head>
<body>
    <div class="container">
        {nav}
        {content}
    </div>
</body>
</html>
"""

def get_navigation(season: str = None, week: int = None, prev_week: int = None, next_week: int = None, in_subdirectory: bool = False) -> str:
    """
    Generate consistent navigation bar HTML with main menu and optional sub-navigation.
    
    Args:
        season: Current season (e.g., "2024")
        week: Current week number
        prev_week: Previous week number (if available)
        next_week: Next week number (if available)
        in_subdirectory: Whether the page is in a subdirectory (e.g., all_time/)
        
    Returns:
        Navigation HTML string with main nav and optional sub-nav
    """
    nav_parts = []
    
    # Determine path prefix based on location
    path_prefix = "../" if (season or in_subdirectory) else ""
    
    # Main navigation bar - consistent across all pages
    nav_parts.append('<div class="nav">')
    nav_parts.append(f'<a href="{path_prefix}index.html">Home</a>')
    nav_parts.append(f'<a href="{path_prefix}all_time/index.html">All-Time Stats</a>')
    nav_parts.append(f'<a href="{path_prefix}seasons.html">Seasons</a>')
    nav_parts.append('</div>')
    
    # Sub-navigation for season pages (week navigation)
    if season and week:
        nav_parts.append('<div class="sub-nav">')
        nav_parts.append(f'<span class="current-location">{season} Season - Week {week}</span>')
        if prev_week:
            nav_parts.append(f'<a href="week_{prev_week}.html">← Week {prev_week}</a>')
        if next_week:
            nav_parts.append(f'<a href="week_{next_week}.html">Week {next_week} →</a>')
        nav_parts.append('</div>')
    elif season:
        # Season index page
        nav_parts.append('<div class="sub-nav">')
        nav_parts.append(f'<span class="current-location">{season} Season</span>')
        nav_parts.append('</div>')
    
    return ''.join(nav_parts)

def get_breadcrumb(season: str = None, week: int = None, in_subdirectory: bool = False) -> str:
    """
    Generate breadcrumb navigation with relative paths.
    
    Args:
        season: Current season
        week: Current week number
        in_subdirectory: Whether the page is in a subdirectory (e.g., all_time/)
        
    Returns:
        Breadcrumb HTML string
    """
    breadcrumbs = ['<div class="breadcrumb">']
    
    # Home link - use relative path based on current location
    if season or in_subdirectory:
        # From season pages or all_time subdirectory, go up one level to root
        breadcrumbs.append('<a href="../index.html">Home</a>')
    else:
        # From root, link to itself
        breadcrumbs.append('<a href="index.html">Home</a>')
    
    if season:
        breadcrumbs.append(' / ')
        breadcrumbs.append(f'<a href="index.html">{season}</a>')
        
        if week:
            breadcrumbs.append(f' / Week {week}')
    elif in_subdirectory:
        # From all_time subdirectory
        breadcrumbs.append(' / <a href="standings.html">All-Time Stats</a>')
    else:
        # From root index
        breadcrumbs.append(' / All-Time Stats')
    
    breadcrumbs.append('</div>')
    return ''.join(breadcrumbs)

