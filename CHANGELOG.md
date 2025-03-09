# Changelog

## [1.1.0] - 2024-03-09

### Fixed
- Fixed timezone handling in check-in records
- Now properly stores UTC time in database and converts to local time for display

### Added
- Added browser-based timezone detection
- Added timezone.js for automatic timezone detection
- Added utility functions for timezone conversion

### Changed
- Modified CheckIn model to store pure UTC times
- Updated dashboard and history views to handle timezone conversion
- Moved all JavaScript includes into block scripts in base template

### Migration
1. Create new branch:
```bash
git checkout -b fix/timezone-bug main
```

2. Run database migration:
```bash
flask db migrate -m "fix timezone data"
flask db upgrade
```

3. Deploy steps:
```bash
# On production server
git fetch origin
git checkout fix/timezone-bug
flask db upgrade
sudo systemctl restart daily-checkin
```

4. Merge to main after verification:
```bash
git checkout main
git merge fix/timezone-bug
git push origin main
```

### Dependencies
- Added pytz package requirement