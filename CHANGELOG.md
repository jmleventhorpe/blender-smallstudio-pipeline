# Changelog

All notable changes to this project are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Spikes T1 to T11 testing the Blender 5.2 behaviour the design depends on, with results.
- Project scaffold: core and Blender layers, extension manifest, tests in plain Python
  and in headless Blender, extension build script and CI.
- Core (M1), all without Blender:
  - Config: built-in `defaults.toml` merged with a project's `pipeline.toml`, checked on
    load with errors that name the file and setting.
  - Path templates that build paths from fields and read fields back out of paths.
  - Naming rules and episode, sequence and shot codes, numbered in steps with room to
    insert.
  - Entity metadata as JSON files, behind a tracker interface (filesystem now).
  - `Project`, `Asset`, `Sequence` and `Shot`, giving every workfile, publish, hero and
    render path, and enforcing which tasks each entity has.
  - File context: what a file is from its path, with the label for the top bar.
