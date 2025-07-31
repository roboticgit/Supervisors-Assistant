import os
import re
import requests
from collections import Counter
from datetime import datetime, timezone

def get_roblox_user_task_counts(roblox_usernames):
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
    now = datetime.now(timezone.utc)
    first_of_month = datetime(year=now.year, month=now.month, day=1, tzinfo=timezone.utc)
    first_of_month_unix_ms = int(first_of_month.timestamp() * 1000)
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
                    # You can add logging here if desired
                    break
                data = response.json()
                tasks = data.get('tasks', [])
                if not tasks:
                    break
                for task in tasks:
                    task_id = task.get('id')
                    if task_id in seen_task_ids:
                        continue
                    seen_task_ids.add(task_id)

                    # due_date filter is redundant but kept for safety
                    due_date = task.get('due_date')
                    if due_date and int(due_date) >= first_of_month_unix_ms:
                        all_tasks.append(task)
                
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
            if pattern.search(desc):
                if pattern.search(title):
                    host_counter[username] += 1
                    total_counter[username] += 1
                else:
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
