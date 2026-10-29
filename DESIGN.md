---
name: NovelOps
description: A calm editorial review desk for traceable story decisions.
colors:
  background: "#f3f6fb"
  foreground: "#14213d"
  card: "#ffffff"
  primary: "#155eef"
  secondary: "#e8eef9"
  secondary-foreground: "#203252"
  muted: "#edf2f9"
  muted-foreground: "#50617e"
  accent: "#e7efff"
  accent-foreground: "#124fc8"
  destructive: "#b42332"
  border: "#d9e2f0"
  input: "#cad6e8"
typography:
  display:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif'
    fontSize: "clamp(2rem, 3vw, 3rem)"
    fontWeight: 720
    lineHeight: 1.08
    letterSpacing: "-0.04em"
  title:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif'
    fontSize: "1.25rem"
    fontWeight: 600
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif'
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", sans-serif'
    fontSize: "0.875rem"
    fontWeight: 600
    lineHeight: 1.25
rounded:
  button: "0.75rem"
  field: "0.875rem"
  navigation: "1rem"
  soft: "1.25rem"
  surface: "1.5rem"
  pill: "9999px"
spacing:
  "4": "1rem"
  "5": "1.25rem"
  "6": "1.5rem"
  "8": "2rem"
  "12": "3rem"
components:
  button-primary:
    backgroundColor: "{colors.primary}"
    textColor: "{colors.card}"
    rounded: "{rounded.button}"
    padding: "0.5rem 1rem"
    height: "2.75rem"
  button-outline:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.button}"
    padding: "0.5rem 1rem"
    height: "2.75rem"
  button-secondary:
    backgroundColor: "{colors.secondary}"
    textColor: "{colors.secondary-foreground}"
    rounded: "{rounded.button}"
    padding: "0.5rem 1rem"
    height: "2.75rem"
  button-destructive:
    backgroundColor: "{colors.destructive}"
    textColor: "{colors.card}"
    rounded: "{rounded.button}"
    padding: "0.5rem 1rem"
    height: "2.75rem"
  card:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.surface}"
    padding: "{spacing.5}"
  input:
    backgroundColor: "{colors.card}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.field}"
    height: "2.75rem"
  navigation-active:
    backgroundColor: "{colors.accent}"
    textColor: "{colors.accent-foreground}"
    rounded: "{rounded.navigation}"
  status-badge:
    backgroundColor: "{colors.muted}"
    textColor: "{colors.foreground}"
    rounded: "{rounded.pill}"
    padding: "0.375rem 0.75rem"
---

# Design System: NovelOps

## Overview

**Creative North Star: "The Editorial Review Desk"**

NovelOps gives a solo writer or editor a calm place to inspect source material and make the next recorded decision. The built interface uses a cool pearl canvas, deep slate ink, cobalt actions, precise pale dividers, and softly raised white surfaces. The overall character is minimalist, modern, and iOS inspired, as confirmed by the user.

Rounded surfaces keep dense workflow details approachable. Motion is brief and useful: it marks an interactive card or the arrival of a page without competing with source, version, and approval data. On narrow screens, the review surface becomes a focused single column modal.

**Key Characteristics:**

- Pearl and blue gray canvas with deep ink text and a single cobalt action accent.
- Broad rounded cards and controls, fine borders, and soft offset depth.
- Compact desktop navigation, mobile bottom navigation, and a focused review surface.
- Visible provenance and decision state inside the same restrained visual language.

## Colors

The palette is cool and quiet; cobalt signals an action or selected location, while status hues communicate workflow meaning.

### Primary

- **Cobalt action** (`primary`): primary buttons, active icons, and checkboxes. Its light foreground is the white `card` token.
- **Cobalt tint** (`accent`) and **deep cobalt ink** (`accent-foreground`): selected navigation, hover surfaces, and small emphasis areas.

### Secondary

- **Blue gray fill** (`secondary`) and **slate text** (`secondary-foreground`): secondary buttons and controls.

### Neutral

- **Cool pearl** (`background`): the main canvas and mobile review background.
- **Deep slate ink** (`foreground`): primary copy and headings.
- **Paper white** (`card`): cards, inputs, and desktop review surface.
- **Quiet fill** (`muted`) and **quiet ink** (`muted-foreground`): low emphasis information and supporting text.
- **Precise divider** (`border`) and **field stroke** (`input`): boundaries that separate work without heavy outlines.

### Semantic

- **Decision red** (`destructive`): destructive actions and error emphasis. Workflow badges also use amber, blue, emerald, orange, violet, red, and slate Tailwind status pairs as defined by `StatusBadge`; these are state colors rather than a second brand palette.

**The Cobalt Decision Rule.** Reserve saturated cobalt for actionable or selected elements; use slate for ordinary information.

## Typography

**Display and body font:** the platform system sans stack, with SF Pro Text and Segoe UI named as fallbacks. The code defines a separate system mono stack for technical material.

**Character:** compact and direct, with tighter tracking on headings. Text stays legible through weight and spacing rather than decorative type.

### Hierarchy

- **Display:** the large page title uses the `display` token, with tighter tracking and a responsive size.
- **Title:** card and section titles use the `title` token; section titles also appear at the smaller `text-lg` utility size where density calls for it.
- **Body:** regular copy uses the `body` token; long introductions are capped near 72 characters and use a roomier 1.6 line height.
- **Label:** button and navigation labels use the `label` token. Table headings and badges step down to `text-xs` while retaining semibold weight.

## Layout

The centered page shell tops out at 1540px. Its desktop padding is 2rem vertically with responsive side padding between 1rem and 3rem; on narrow screens it uses 1.25rem top and 1rem sides, leaving extra room for the fixed bottom navigation. Content commonly uses 1rem to 1.5rem gaps and 1.25rem to 2rem card padding.

The shared header is 72px high. Main navigation sits across the top from the `md` breakpoint (768px); below that, a five item bottom bar takes over. Desktop hotspot review opens beside the list from 1024px, reserving up to 37rem of page width, while the detail dialog occupies up to 35rem or 40vw on the right. Below 1024px it opens as a full viewport modal with one vertical reading path. The list itself becomes cards below 768px.

**The One Decision Rule.** Keep the source list and active review visible together when width permits; on a phone, give the active review the full screen.

## Elevation & Depth

The interface uses tonal layering and ambient shadows together. White surfaces sit above the cool canvas with pale borders. Hoverable cards rise only slightly, and the navigation uses translucency and blur to maintain separation while scrolling.

### Shadow Vocabulary

- **Surface:** `0 16px 42px -28px rgb(35 61 106 / 36%), 0 5px 18px -12px rgb(35 61 106 / 19%)` on `.surface`.
- **Raised surface:** `0 26px 52px -30px rgb(35 61 106 / 42%), 0 10px 24px -15px rgb(35 61 106 / 25%)` on hoverable surfaces.
- **Navigation:** `0 9px 30px -24px rgb(28 55 102 / 45%)` under the top and bottom chrome.

**The Soft Lift Rule.** A hoverable surface moves up only 2px, with shadow and border changes over 220ms. Its resting state remains visually stable.

## Shapes

Generous corners define the system. Primary surfaces use a 1.5rem radius; inset soft surfaces use 1.25rem. Buttons use 0.75rem, fields 0.875rem, navigation items 1rem, and small status labels are full pills. Thin borders do most of the edge work. Tables remain rectangular internally but sit inside a rounded, clipped container.

## Components

### Buttons

Buttons feel solid and easy to target. The shared component uses a minimum 44px height, semibold 0.875rem labels, and horizontal spacing of 1rem by default. Primary is cobalt with white type and a compact blue shadow; outline is white with the field border; secondary is pale blue gray; destructive is red; ghost and link variants use lighter emphasis. Hover changes fill or border, active presses to 98% scale, and keyboard focus uses a 2px cobalt outline offset from the edge. Disabled buttons dim to 50% opacity. Small and large size variants use 40px and 48px minimum heights respectively.

### Cards / Containers

Cards are white, softly raised, and enclosed by a pale border. The shared header and content use 1.25rem padding, increasing to 1.5rem from the small breakpoint. The inset `.surface-soft` treatment is pale blue gray, with a finer border and a 1.25rem radius. Only explicitly interactive cards receive the slight hover lift.

### Inputs / Fields

Text fields, selects, and textareas have white fill, a blue gray stroke, a 0.875rem radius, and a subtle inset shadow. Standard fields have a 44px minimum height; textareas have a 78px minimum. The shared visible focus outline is cobalt and offset 3px. Checkboxes use cobalt and an 18px square.

### Navigation

The top bar is translucent white with blur, a fine bottom border, and restrained shadow. Desktop links have 44px minimum targets and rounded active tints; the mobile bottom bar has five 58px minimum targets, icon above label, and safe area padding. Active location uses cobalt ink on the pale cobalt tint.

### Status badges

Small, semibold pills display workflow states. The status component maps each known state to a semantic light fill and dark text. Unknown states fall back to slate, keeping the state legible without guessing its meaning.

### Tables and review surface

Desktop tables use a rounded bordered container, 48px headers, 1rem cell padding, pale row hover, and a tinted selected row. The hotspot detail is a right side review surface on desktop and a full viewport modal on smaller screens; it keeps analysis history, provenance, and the approval form in one scrollable reading order.

## Do's and Don'ts

### Do:

- **Do** use cobalt for the next action and active location, with pale cobalt for its surrounding state.
- **Do** keep 44px minimum targets for standard controls and a visible keyboard focus outline.
- **Do** give dense source and approval information rounded, bordered containers with a clear reading order.
- **Do** reduce animation duration to near zero when the user prefers reduced motion.

### Don't:

- **Don't** use status hues as competing brand accents or infer an approval from their color alone.
- **Don't** add decorative shadows to every nested container; use the soft inset surface for grouping.
- **Don't** place the desktop list beside a cramped mobile review; use the full screen review mode already implemented.
