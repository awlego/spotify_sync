#!/bin/bash

# Load environment variables from .env file
export $(grep -v '^#' /Users/awlego/Repositories/spotify_sync/.env | xargs)

# Activate virtual environment and run the sync service
source /Users/awlego/Repositories/spotify_sync/env3.10/bin/activate
python /Users/awlego/Repositories/spotify_sync/sync_service/run.py