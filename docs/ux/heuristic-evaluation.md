# GUI Heuristic Evaluation

**Date**: 2026-03-05
**Evaluator**: Claude (AI-assisted UX audit)
**Application**: Access Ability Arm GUI (Flet framework)
**Target Users**: ALS patients with severely limited motor control

---

## Executive Summary

The GUI is **functionally complete** but **poorly suited for its target users**. It was designed around technical capabilities (detection modes, point cloud export) rather than user tasks ("pick up that cup"). The most critical issues are undersized touch targets (50x50px for motor-impaired users), information overload, and a multi-step workflow that requires unnecessary precision and cognitive switching.

**Overall Score: 2.4 / 5.0** (needs significant redesign)

---

## 1. Nielsen's 10 Usability Heuristics

### H1: Visibility of System Status | Score: 2/5

**Findings:**
- Status bar uses dense, abbreviation-heavy text: `RealSense: [checkmark] With Depth | Detection: RF-DETR | Mode: Object Detection`
- Font size is 12px — nearly unreadable at arm's length
- Arm connection status is buried in the same status row, easy to miss
- Object analysis shows "Analyzing..." on a small button (difficult to notice)
- No progress indicators for multi-second operations (point cloud export, mesh generation)

**Recommendations:**
- Single large contextual status message (24px+) replacing the dense bar
- Full-screen progress overlays for long operations
- Color-coded system state visible without reading text

### H2: Match Between System and Real World | Score: 2/5

**Findings:**
- Tab labels "Manual" and "Auto" don't match user mental models. Users think in terms of *what they want to do*, not control modes
- Technical labels: "Export PLY", "Export Mesh", "Complete Shape" — meaningless to non-technical users
- Button labels like "X+", "X-" assume coordinate system knowledge
- "Show Points" is developer-facing terminology
- Detection modes (RF-DETR, Camera Only, Combined) are implementation details

**Recommendations:**
- Rename tabs to task-oriented labels: "Move Arm" and "Find & Grab"
- Replace technical button labels: "Save 3D Model", "Predict Full Shape"
- Replace X/Y/Z labels with "Left/Right", "Forward/Back", "Up/Down"
- Hide detection mode internals from users

### H3: User Control and Freedom | Score: 3/5

**Findings:**
- No "undo" for arm movements — a mistake means manually correcting
- Tab switching unfreezes video, losing detected objects (destructive, no warning)
- Object deselection requires clicking the same button again (not obvious)
- No "home" position button to reset arm to safe default
- No emergency stop button prominently displayed

**Recommendations:**
- Add "Undo Last Move" button with arm position history
- Add prominent "Emergency Stop" / "Home Position" buttons
- Warn before destructive tab switches
- Add a "Back" button in the Auto workflow

### H4: Consistency and Standards | Score: 3/5

**Findings:**
- Buttons use inconsistent sizing: 50x50px (direction), 135x38px (actions), 140px (Connect Arm)
- Color scheme is inconsistent: Green for flip active, Blue for depth active, no pattern
- Some buttons are IconButtons (flip, depth), others are ElevatedButtons (Find Objects, Export)
- Status uses mix of checkmark/cross Unicode symbols and color coding

**Recommendations:**
- Standardize button sizes to 2-3 tiers: primary (100x60px), secondary (80x50px), icon (60x60px)
- Consistent color language: green=active, blue=action, grey=disabled, red=danger
- Consistent button style per function type

### H5: Error Prevention | Score: 2/5

**Findings:**
- No confirmation before arm movements — a tap sends a 10mm command immediately
- No bounds checking shown to user before movement (can crash arm into table)
- "Find Objects" button behavior changes based on hidden state (frozen vs. unfrozen) with no visual indicator
- Camera switching silently drops detection state
- No "are you sure?" for potentially destructive operations

**Recommendations:**
- Visual boundaries/workspace limits shown in manual control
- Confirm large movements (hold-step of 50mm)
- Make button behavior predictable (separate "Find" and "Refresh" actions)
- Show workspace boundary warnings

### H6: Recognition Rather Than Recall | Score: 2/5

**Findings:**
- Users must remember keyboard shortcut "T" to cycle detection modes (no on-screen affordance)
- Users must remember "L" toggles logging (undiscoverable)
- The relationship between Manual/Auto tabs and detection modes is not visible
- Object buttons disappear when switching tabs, requiring users to remember what was detected
- No visual indication of which workflow step you're on

**Recommendations:**
- Remove hidden keyboard shortcuts; provide on-screen controls for all functions
- Add step indicator for Auto workflow: "Step 1 of 3: Find Objects"
- Persist detection results across tab switches

### H7: Flexibility and Efficiency of Use | Score: 2/5

**Findings:**
- No shortcuts for expert users (beyond hidden T/L keys)
- No customizable button sizes or layouts
- Speed slider requires precise manipulation (1-100 range, hard for motor-impaired)
- No preset speed options (Slow/Medium/Fast)
- No way to save arm positions or repeat movements

**Recommendations:**
- Add preset speed buttons (Slow/Medium/Fast) alongside slider
- Add "Save Position" and "Go To Position" for common locations
- Support configurable UI scaling
- Add switch/eye-tracking input mode

### H8: Aesthetic and Minimalist Design | Score: 2/5

**Findings:**
- All controls visible simultaneously (6 buttons in camera row, 4 direction blocks + grip + speed in Manual)
- Auto tab shows all 4 action buttons at once even when only "Find Objects" is relevant
- Exposure controls inline with camera buttons (adds visual clutter when not needed)
- Dense status bar with pipe separators competes for attention
- Right panel is only 220px wide, cramming controls into narrow column
- Information density is high: ~20+ interactive elements visible at any time

**Recommendations:**
- Progressive disclosure: show only the current step's controls
- Hide exposure controls behind a settings panel
- Increase right panel width or use full-width layout for controls
- Reduce visible interactive elements to 3-5 per screen state

### H9: Help Users Recognize, Diagnose, and Recover from Errors | Score: 1/5

**Findings:**
- Error messages go to console (`print()`) — users never see them
- "Analysis failed" appears on a small button with no explanation or recovery action
- Camera connection failures show in status bar at 12px font
- Arm errors display in status text but offer no recovery path
- No user-facing error dialogs or notifications

**Recommendations:**
- Display errors as prominent in-app notifications/banners
- Include recovery actions: "Connection failed — Retry? Check cable?"
- Log errors to UI, not just console

### H10: Help and Documentation | Score: 1/5

**Findings:**
- No in-app help, tooltips are minimal
- No onboarding or tutorial for first-time users
- No documentation of the workflow steps
- Keyboard shortcuts are completely undiscoverable
- No explanation of what "Show Points" or "Complete Shape" do

**Recommendations:**
- Add contextual help text for each workflow step
- First-run tutorial overlay
- Descriptive tooltips on all buttons explaining what happens when clicked

---

## 2. Accessibility Audit (Motor Impairment Focus)

### Touch Target Sizes | FAIL

| Element | Current Size | WCAG Minimum | ALS Recommended |
|---------|-------------|--------------|-----------------|
| Direction buttons (X/Y/Z) | 50x50px | 44x44px | 80-100px |
| Object selection buttons | Auto-sized (~80x38px) | 44x44px | 80x60px |
| Action buttons (Export, etc.) | 135x38px | 44x44px | 135x60px |
| Icon buttons (flip, depth) | ~40x40px | 44x44px | 60x60px |
| Speed slider thumb | ~20px | 44x44px | 44px+ |
| Grip toggle switch | ~36px | 44x44px | 60px+ |

**Direction buttons (50x50px) technically pass WCAG AA** (44px minimum) but are **far too small for ALS patients** who may have severe tremor, limited range of motion, or use head/eye tracking. Research on motor-impaired users recommends **80-100px minimum** with **16px+ spacing** between targets.

### Color Contrast | PARTIAL PASS

| Element | Foreground | Background | Ratio | WCAG AA (4.5:1) | WCAG AAA (7:1) |
|---------|-----------|------------|-------|-----------------|-----------------|
| Status text | #455A64 | #ECEFF1 | 5.6:1 | Pass | Fail |
| Exposure text | #666666 | white | 5.7:1 | Pass | Fail |
| Active button text | #FFFFFF | #4CAF50 | 3.3:1 | **FAIL** | Fail |
| Object button text | #FFFFFF | #37474F | 8.9:1 | Pass | Pass |
| Red button icon | #B71C1C | #EF9A9A | 3.7:1 | **FAIL** | Fail |

**Two critical contrast failures** on active state buttons and direction button icons.

### Font Sizes | FAIL

| Element | Current | Recommended for ALS |
|---------|---------|-------------------|
| Status bar | 12px | 18px+ |
| Exposure text | 12px | 16px+ |
| Button labels | 14px | 18px+ |
| Direction labels | 16px | 20px+ |
| Tab labels | 14px | 18px+ |

Most text is too small for users who may be at arm's length from the screen.

### Cognitive Load | HIGH

The GUI presents **~25 interactive elements simultaneously** on the Manual tab. Cognitive load is high because:
- Multiple axis controls visible at once (X, Y, Z, Grip = 8 buttons + 4 labels)
- Speed slider + label
- Camera dropdown + 3 icon buttons
- Tab bar + arm connection button
- Status bar with 4+ pieces of information

For ALS patients experiencing cognitive fatigue, this is overwhelming.

---

## 3. Task Flow Analysis

### Task 1: Detect and Select an Object

| Step | Action | Clicks | Cognitive Load |
|------|--------|--------|---------------|
| 1 | Find and click "Auto" tab | 1 | Must find tab, understand Manual vs Auto |
| 2 | Click "Find Objects" button | 1 | Must locate among other controls |
| 3 | Wait 1 second | 0 | No feedback during capture |
| 4 | Scan generated object buttons | 0 | Must read small button labels |
| 5 | Click desired object button | 1 | Must identify correct object by name |
| 6 | Wait for analysis | 0 | "Analyzing..." on small button |
| **Total** | | **3 clicks** | **Moderate** |

**Issues:**
- Step 1 is unnecessary if the Auto tab were the default for this task
- Step 3 has no visible progress indicator
- Step 4 requires reading class names ("person", "bottle") which may not match user's mental model
- Object buttons are horizontally scrollable but overflow is not obvious

### Task 2: Move Arm to Position

| Step | Action | Clicks | Cognitive Load |
|------|--------|--------|---------------|
| 1 | Ensure on "Manual" tab | 0-1 | May need to switch tabs |
| 2 | Adjust speed slider | 1 | Must evaluate current speed |
| 3 | Click X+/X- for lateral | 1+ | Must map X to "left/right" |
| 4 | Click Y+/Y- for depth | 1+ | Must map Y to "forward/back" |
| 5 | Click Z+/Z- for height | 1+ | Must map Z to "up/down" |
| 6 | Adjust gripper | 1-2 | Toggle or fine adjust |
| **Total** | | **5-10+ clicks** | **High** |

**Issues:**
- X/Y/Z labels require spatial reasoning (cognitive load for ALS patients)
- No visual feedback of arm position during movement
- Each click is a discrete step — no continuous movement
- Tap vs. hold behavior (10mm vs 50mm) is undiscoverable
- No way to see where the arm currently is relative to the object

### Task 3: Export 3D Data (Advanced)

| Step | Action | Clicks | Cognitive Load |
|------|--------|--------|---------------|
| 1 | Select object (Task 1) | 3 | See above |
| 2 | Click "Export PLY" | 1 | Must know what PLY means |
| 3 | Find file in logs/ | 0 | No feedback on where file saved |
| **Total** | | **4 clicks** | **High** (technical) |

**Issues:**
- No feedback confirming export success or file location
- Technical terminology barrier
- File saved to opaque directory path

---

## 4. Priority Issues Summary

### Critical (Fix Immediately)
1. **Touch targets too small** for motor-impaired users (50x50px direction buttons)
2. **Errors invisible** — all errors go to console, users see nothing
3. **No emergency stop** — no way to quickly halt arm movement
4. **Contrast failures** on active buttons and icon colors

### High Priority
5. **Information overload** — 25+ interactive elements visible simultaneously
6. **Technical jargon** — X/Y/Z, PLY, RF-DETR, detection modes
7. **Status bar unreadable** — 12px font, dense information
8. **No progressive disclosure** — all features shown regardless of context

### Medium Priority
9. **No onboarding** or help for first-time users
10. **Undiscoverable features** — keyboard shortcuts, tap vs. hold behavior
11. **Destructive tab switching** — loses detection state without warning
12. **No undo** for arm movements

### Low Priority
13. **No position saving** for arm
14. **No preset speeds** (Slow/Medium/Fast)
15. **No alternative input modes** (switch access, eye tracking)
