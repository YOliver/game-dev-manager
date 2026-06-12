# Remember Last Folder - Manual Test Plan

> **For tester:** This document provides step-by-step manual testing instructions for the "Remember Last Folder" feature.

**Goal:** Verify that the app correctly saves and restores the last opened folder.

**Test Environment:**
- Windows 10/11 (x64)
- Python 3.8+ with PySide6, Pillow installed
- GUI environment (can display Qt windows)

---

## Pre-Test Setup

1. Ensure config file does NOT exist:
   ```bash
   del "%APPDATA%\Game Dev Manager\config.json"
   ```
   (If file doesn't exist, that's expected for first launch)

2. Launch the app:
   ```bash
   cd /g/UGit/game-dev-manager
   python -m gdm.main
   ```

---

## Test Case 1: First Launch (No Config)

**Objective:** App should launch with blank window, no errors.

**Steps:**
1. Ensure config file does NOT exist
2. Launch app: `python -m gdm.main`
3. Observe the main window

**Expected Result:**
- ✅ Main window opens successfully
- ✅ No error dialogs or console errors
- ✅ Window title: "Game Dev Manager"
- ✅ Left panel (ProjectPanel) shows nothing
- ✅ Center panel (ThumbnailView) shows nothing
- ✅ Right panel (DetailPanel) shows "No preview"

**Pass/Fail:** ✅ Pass

---

## Test Case 2: Select Folder Saves Config

**Objective:** After selecting a folder, config file should be created with `last_folder` path.

**Steps:**
1. Launch app (from Test 1)
2. Click "File" → "Open Folder"
3. Select a folder that contains images (e.g., `C:\test_sprites`)
4. Verify thumbnails are displayed in center panel
5. Close app
6. Check config file exists and has correct content

**Expected Result:**
- ✅ Folder selection dialog opens
- ✅ After selecting folder, thumbnails display in center panel
- ✅ Config file created at `%APPDATA%\Game Dev Manager\config.json`
- ✅ Config content:
  ```json
  {
    "last_folder": "C:\\test_sprites"
  }
  ```

**Pass/Fail:** ✅ Pass

---

## Test Case 3: Restore on Next Launch

**Objective:** App should automatically open the last folder on next launch.

**Steps:**
1. Ensure config file exists from Test 2
2. Launch app: `python -m gdm.main`
3. Observe if the folder from Test 2 opens automatically

**Expected Result:**
- ✅ Main window opens
- ✅ Folder from Test 2 opens automatically (thumbnails displayed)
- ✅ Left panel shows the folder path
- ✅ No need to manually click "Open Folder"

**Pass/Fail:** ________

---

## Test Case 4: Invalid Path Handling

**Objective:** If `last_folder` points to a non-existent path, app should skip silently (no crash).

**Steps:**
1. Edit config file: Change `last_folder` to a non-existent path:
   ```json
   {
       "last_folder": "C:\\non_existent_folder"
   }
   ```
2. Launch app: `python -m gdm.main`
3. Observe if app launches without errors

**Expected Result:**
- ✅ Main window opens successfully
- ✅ No error dialogs or console errors
- ✅ App shows blank window (no thumbnails, since folder doesn't exist)
- ✅ No crash or freeze

**Pass/Fail:** ________

---

## Test Case 5: Config File Corrupted

**Objective:** If config file is not valid JSON, app should skip silently (no crash).

**Steps:**
1. Edit config file: Write invalid JSON:
   ```json
   { invalid json }
   ```
2. Launch app: `python -m gdm.main`
3. Observe if app launches without errors

**Expected Result:**
- ✅ Main window opens successfully
- ✅ No error dialogs or console errors
- ✅ App shows blank window
- ✅ No crash or freeze

**Pass/Fail:** ________

---

## Test Case 6: Select Different Folder Updates Config

**Objective:** Selecting a different folder should update `last_folder` in config.

**Steps:**
1. Launch app (from Test 3, config has `C:\test_sprites`)
2. Click "File" → "Open Folder"
3. Select a **different** folder (e.g., `C:\other_sprites`)
4. Close app
5. Check config file content

**Expected Result:**
- ✅ New folder's thumbnails display after selection
- ✅ Config file updated: `last_folder` now points to `C:\other_sprites`

**Pass/Fail:** ________

---

## Test Case 7: Permission Error Handling (Optional)

**Objective:** If config file cannot be written (permission error), app should not crash.

**Steps:**
1. Create config directory with read-only permission (Windows):
   ```bash
   # May not work on Windows, skip if unable to set
   icacls "%APPDATA%\Game Dev Manager" /grant Everyone:R
   ```
2. Launch app and try to select a folder
3. Observe if app handles the error gracefully

**Expected Result:**
- ✅ App does not crash
- ✅ Warning logged to console (may not be visible in GUI mode)
- ✅ App continues to function (can still browse folders)

**Pass/Fail:** ________ (or N/A if can't set permissions)

---

## Test Summary

| Test Case | Pass | Fail | Notes |
|-----------|------|------|-------|
| 1. First Launch (No Config) | | | |
| 2. Select Folder Saves Config | | | |
| 3. Restore on Next Launch | | | |
| 4. Invalid Path Handling | | | |
| 5. Config File Corrupted | | | |
| 6. Select Different Folder Updates Config | | | |
| 7. Permission Error Handling (Optional) | | | |

**Overall Result:** ________ (Pass/Fail)

**Tester:** ________  
**Date:** ________  
**App Version:** 1.0.0  
**Commit Hash:** ________  
