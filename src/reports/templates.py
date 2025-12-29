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
    Generate navigation bar HTML with relative paths that work for both local and GitHub Pages.
    
    Args:
        season: Current season (e.g., "2024")
        week: Current week number
        prev_week: Previous week number (if available)
        next_week: Next week number (if available)
        in_subdirectory: Whether the page is in a subdirectory (e.g., all_time/)
        
    Returns:
        Navigation HTML string
    """
    nav_links = ['<div class="nav">']
    
    # Home link - use relative path based on current location
    if season or in_subdirectory:
        # From season pages or all_time subdirectory, go up one level
        home_link = "../index.html"
    else:
        # From root index.html, link to itself
        home_link = "index.html"
    nav_links.append(f'<a href="{home_link}">Home</a>')
    
    if season:
        # From season pages, link to root index
        nav_links.append(f'<a href="../index.html">All Seasons</a>')
        # Link to season index (same directory)
        nav_links.append(f'<a href="index.html">{season} Season</a>')
        
        if week:
            # Week navigation (same directory)
            if prev_week:
                nav_links.append(f'<a href="week_{prev_week}.html">← Week {prev_week}</a>')
            if next_week:
                nav_links.append(f'<a href="week_{next_week}.html">Week {next_week} →</a>')
    else:
        # From root index, link to all-time stats
        if not in_subdirectory:
            nav_links.append('<a href="all_time/standings.html">All-Time Stats</a>')
        else:
            # From all_time subdirectory, link back to root
            nav_links.append('<a href="../index.html">All Seasons</a>')
    
    nav_links.append('</div>')
    return ''.join(nav_links)

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

