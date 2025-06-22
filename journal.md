# Spotify Sync Project Journal

## 2025-06-21 - Repository Cleanup and Restructuring

### Completed Tasks
1. **Fixed Data Source Issue**
   - Confirmed Last.fm is the only listening history source
   - Spotify sync methods already commented out in sync_service.py
   - OAuth scope already updated to remove 'user-read-recently-played'
   - Web UI already updated with notes about Spotify removal

2. **Cleaned Repository Structure**
   - Created organized directory structure: data/, scripts/, notebooks/
   - Moved CSV files to data/csv/
   - Removed sensitive Daylio mood tracking data
   - Removed unrelated OAuth server (oath.py)
   - Removed empty test directory and test.py at root
   - Consolidated virtual environments (removed venv, keeping env3.10)
   - Updated .gitignore with comprehensive exclusions

3. **Improved Configuration**
   - Updated .env.example to remove hardcoded usernames
   - Consolidated requirements.txt files
   - Created setup.py helper script

### Future Improvements to Consider
1. **Testing**: The test coverage is minimal (only 3 test files). Consider:
   - Adding unit tests for sync_service, playlist_service
   - Integration tests for API clients
   - End-to-end tests for the sync workflow

2. **Visualization Complexity**: The analytics/visualization features add significant complexity. Consider:
   - Moving visualizations to a separate analytics package
   - Making them optional/plugin-based
   - Simplifying to just core sync functionality

3. **Error Handling**: Add better error recovery for:
   - API rate limits
   - Network failures
   - Database corruption

4. **Performance**: For large libraries (70k+ tracks):
   - Consider implementing database indexing
   - Batch processing optimizations
   - Progress indicators for long operations

5. **Configuration Management**:
   - Move away from environment variables to a single config file
   - Add validation for all required settings
   - Better error messages for missing configuration

### 2025-06-21 Update - Complete Restructuring

4. **Flattened Project Structure**
   - Moved everything from spotify_sync_automated/ to root
   - Created clean, flat structure:
     - src/ - All source code
     - scripts/ - All utility scripts
     - templates/ & static/ - Web assets
     - tests/ - Test suite
   - Updated all import paths in scripts
   - Updated configuration paths for database and cache
   - Removed nested directory confusion

### 2025-06-21 Update - Service Architecture Implementation

5. **Split into Two Services**
   - Created `shared/` directory for database models and configuration
   - Created `sync_service/` - Backend sync with minimal monitoring UI (port 5001)
   - Created `wrapped_service/` - Rich analytics and visualizations (port 5002)
   - Both services share the same SQLite database
   - Moved appropriate code to each service:
     - Sync service: API clients, sync logic, playlist management, scheduler
     - Wrapped service: Analytics engine, visualizations, pattern detection
   - Each service has its own run.py and can be run independently

### Benefits of New Architecture
- **Separation of Concerns**: Sync runs continuously, analytics on-demand
- **Independent Development**: Each service can be updated without affecting the other
- **Focused Features**: Sync focuses on reliability, wrapped on user experience
- **Scalability**: Services can be deployed separately if needed

### Technical Debt
- Multiple sync script versions were consolidated but logic should be reviewed
- Spotify ID sync functionality could be optimized to prevent duplicates
- Import structure could be improved with proper __init__.py files
- Need to clean up old src/ directory after confirming services work
- Tests need to be split between services