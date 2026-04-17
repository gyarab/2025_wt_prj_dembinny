#!/bin/bash

# 1. Navigate to the project directory
cd ~/2025_wt_prj_dembinny/ || exit

# 2. Fetch and pull the latest changes
git fetch origin main
git reset --hard origin/main

# 3. Activate the virtual environment
source .venv/bin/activate

# 4. Install any new dependencies
pip install -r requirements.txt

# 5. Apply database migrations
python manage.py migrate

# 6. Collect static files
python manage.py collectstatic --noinput

# 7. Restart the application server (e.g., Gunicorn or uWSGI)
systemctl --user restart gunicorn
