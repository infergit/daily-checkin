daily-checkin/CHANGELOG.md
# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.2.0] - 2024-03-10
### Added
- Added time display in recent check-ins section
- Enhanced datetime format consistency across dashboard and history pages

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

### Dependencies
- Added pytz package requirement