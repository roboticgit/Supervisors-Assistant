import os
import re
import requests
from collections import Counter
from datetime import datetime, timezone
from calendar import monthrange

def get_roblox_user_task_counts(roblox_usernames, year: int = None, month: int = None, month_offset: int = 0):
    """
    Fetch host/co-host counts for the given list of Roblox usernames.

    Parameters
    - roblox_usernames: iterable of usernames to count for
    - year, month: optional explicit year and month to count for (UTC)
    - month_offset: if year/month not provided, offset from current month (0 = this month, -1 = last month)

    Returns a dict mapping username -> {'host': int, 'cohost': int, 'total': int}
    """
    list_ids = [
        os.getenv('CLICKUP_LIST_ID_DRIVING_DEPARTMENT'),
        os.getenv('CLICKUP_LIST_ID_DISPATCHING_DEPARTMENT'),
        os.getenv('CLICKUP_LIST_ID_GUARDING_DEPARTMENT'),
        os.getenv('CLICKUP_LIST_ID_SIGNALLING_DEPARTMENT'),
    ]
    headers = {
        "Authorization": os.getenv('CLICKUP_API_TOKEN'),
        "accept": "application/json"
    }
    # Determine target year/month
    if year is None or month is None:
        now = datetime.now(timezone.utc)
        # Apply month_offset
        target_month = now.month + month_offset
        target_year = now.year
        # Adjust year/month to valid range
        while target_month < 1:
            target_month += 12
            target_year -= 1
        while target_month > 12:
            target_month -= 12
            target_year += 1
    else:
        target_year = year
        target_month = month

    first_of_month = datetime(year=target_year, month=target_month, day=1, tzinfo=timezone.utc)
    last_day = monthrange(target_year, target_month)[1]
    # Last moment of month (23:59:59.999)
    last_of_month = datetime(year=target_year, month=target_month, day=last_day, hour=23, minute=59, second=59, tzinfo=timezone.utc)
    first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)
    last_of_month_unix_ms = int(last_of_month.timestamp() * 1000)
    seen_task_ids = set()
    all_tasks = []

    # Precompile regex patterns for usernames with word boundaries to avoid partial matches
    username_patterns = {
        username: re.compile(rf'\b{re.escape(username)}\b', re.IGNORECASE)
        for username in roblox_usernames
    }

    for list_id in list_ids:
        if not list_id:
            continue
        for archived_value in ["false", "true"]:
            page = 0
            while True:
                url = (
                    f"https://api.clickup.com/api/v2/list/{list_id}/task?"
                    f"archived={archived_value}&"
                    f"statuses=concluded&"
                    f"include_closed=true&"
                    f"due_date_gt={first_of_month_unix_ms}&"
                    f"page={page}"
                )
                response = requests.get(url, headers=headers)
                if response.status_code != 200:
                    print(f"ClickUp API request failed for list {list_id} (archived={archived_value}, page={page}): {response.status_code} {response.text}")
                    break
                data = response.json()
                tasks = data.get('tasks', [])
                # If API returned no tasks on this page, break pagination loop
                if not tasks:
                    break
                for task in tasks:
                    task_id = task.get('id')
                    if task_id in seen_task_ids:
                        continue
                    seen_task_ids.add(task_id)

                    # due_date filter: ensure task due date exists and is within month window
                    due_date = task.get('due_date')
                    if due_date:
                        try:
                            due_ms = int(due_date)
                        except Exception:
                            continue
                        if first_of_month_unix_ms <= due_ms <= last_of_month_unix_ms:
                            all_tasks.append(task)
                    else:
                        # If there's no due date, skip (previous logic ignored tasks without due_date)
                        continue
                
                # Pagination handling based on ClickUp API's 'page' and 'pages' keys
                current_page = data.get('page', 0)
                total_pages = data.get('pages', 1)
                if current_page >= total_pages - 1:
                    break
                page += 1

    host_counter = Counter()
    cohost_counter = Counter()
    total_counter = Counter()

    for task in all_tasks:
        title = task.get('name', '') or ''
        desc = task.get('description', '') or ''
        for username, pattern in username_patterns.items():
            # Only count hosts when the username appears in the task title
            if pattern.search(title):
                host_counter[username] += 1
                total_counter[username] += 1
            else:
                # If username appears in the description but not the title, count as cohost
                if pattern.search(desc):
                    cohost_counter[username] += 1
                    total_counter[username] += 1

    result = {}
    for username in roblox_usernames:
        result[username] = {
            'host': host_counter.get(username, 0),
            'cohost': cohost_counter.get(username, 0),
            'total': total_counter.get(username, 0)
        }
    return result
