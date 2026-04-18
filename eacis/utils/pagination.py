from flask import request

# Allowed page sizes for the system-wide pagination feature
ALLOWED_PAGE_SIZES = (5, 10)


def get_page_args(default_per_page=10):
    """Parse paging arguments from the request and normalize values.

    Returns: (page, per_page)
    - `page` is an integer >= 1
    - `per_page` is one of ALLOWED_PAGE_SIZES, defaulting to `default_per_page`
    """
    try:
        page = int(request.args.get('page', 1))
    except (TypeError, ValueError):
        page = 1

    try:
        per_page = int(request.args.get('per_page', default_per_page))
    except (TypeError, ValueError):
        per_page = default_per_page

    if per_page not in ALLOWED_PAGE_SIZES:
        per_page = default_per_page

    if page < 1:
        page = 1

    return page, per_page
