---
version: alpha
name: ShuttleScope
description: A South Bay commuter dashboard inspired by transit wayfinding and route diagrams.
colors:
  ink: "#173c3c"
  muted: "#5c7173"
  brand: "#086d68"
  brand-hover: "#05554f"
  canvas: "#f3f7f7"
  surface: "#ffffff"
  tint: "#e8f3ef"
  line: "#d7e2df"
  accent: "#e5ae48"
  error: "#a2332d"
  scroll: "#8ca5a2"
  scroll-hover: "#617f7a"
  scroll-active: "#365c56"
typography:
  body:
    fontFamily: '"Avenir Next", Avenir, "Segoe UI", sans-serif'
  display:
    fontFamily: '"Trebuchet MS", "Avenir Next", sans-serif'
  data:
    fontFamily: 'ui-monospace, SFMono-Regular, monospace'
rounded:
  DEFAULT: "16px"
spacing:
  panel-gap: "20px"
  page-max: "1600px"
components:
  button:
    height: "43px"
    rounded: "8px"
  panel:
    rounded: "16px"
---

# ShuttleScope design system

## Overview

A product surface for South Bay commuters choosing a pickup hub and checking a shuttle connection. Evidence: README.md proposal, database/example_network.sql, backend/routes/maps.py, and the requested first dashboard. English (en-US), Pacific schedule times; mobile at the pickup hub and desktop while planning. No Japan-market scope.

North Star: station wayfinding, with a quiet teal network line linking pickup, stops, and arrival. The selected hub drives the map and schedule together. Avoid marketing hero imagery, unrelated metric cards, and claims of real-time tracking. This is the first UI; there are no sibling screens or existing shared components.

Runtime ownership: backend/static/dashboard.css :root is the canonical token source. Frontmatter mirrors those variables by the same names; typography roles map to --font-body, --font-display, --font-data, DEFAULT radius maps to --radius. Leaflet feature styles read brand, ink and surface tokens from computed style, keeping the map synchronized with CSS. Update the documentation and runtime together. No build-time adapter or alternate theme.

## Colors

Light surfaces and slate-teal type keep the road map legible. Brand teal indicates selection and primary action; gold distinguishes stored shuttle positions. Error red is always paired with text. Focus uses a visible teal outline. Scrollbar tokens apply globally; forced-colors mode defers to system colors.

## Typography

System-installed Avenir/Segoe UI for prose, Trebuchet for the restrained headline, and system monospace for schedule times. No remote font dependency or font swap. Localized numeric and load-time formatting uses en-US and America/Los_Angeles. Stored schedule times are displayed as Pacific clock times without inventing operating dates.

## Layout

Maximum 1600px page width. At 1200px and above: hub rail, geographic map, schedule rail. Below 1200px: hub rail and stacked map/schedule. Below 760px: one document-scrolling column; the hub choices remain paired. Map height is reserved before loading. All content panels have natural height; no global viewport clipping. Lists intentionally render all hubs because the existing network API returns the complete small network; revisit API pagination for a larger service.

## Elevation & Depth

Flat white panels with quiet borders; shadows are limited to map markers. The map stays below document controls. No floating dialogs or global overlay system is needed.

## Shapes

16px panel corners, 8px buttons, 10px hub cards. Filled hub markers, hollow stops, and square gold shuttle markers encode type through shape and color.

## Components

Shared action classes are .button, .primary, .secondary, .compact. Hover, focus, pressed, disabled and busy states are provided; busy labels retain width. Native details owns coordinate disclosure. Native inputs and the coordinates form own validation, inline errors, field association, and first-invalid focus. There are no selects, tables, dialogs, mutations or account controls.

Canonical feedback: #network-status for loading/refresh/network errors; #location-status for nearest-hub lookup; #coordinate-error for invalid fields; #map-status for a missing map background. These persist inline with polite status announcements. Requests time out after 12 seconds; duplicate actions are blocked. Failed refresh preserves previous data; failed positions do not hide schedules.

Hub buttons use aria-pressed and preserve keyboard focus when selected. A committed hub is shareable through ?hub=. Coordinates and browser location are transient; never stored in URLs or localStorage. Location is requested only by an explicit action and sent only to the same-origin nearest-hub endpoint. Manual coordinates provide a permission-independent alternative.

Map markers mirror readable hub/schedule lists. View all and zoom buttons provide alternatives to dragging. Tile failures retain overlay markers and show recovery text. Dashed lines show stop order, not computed roads. Positions have no timestamps in the API, so the interface explicitly says last reported and time unavailable. Capacity minus assigned riders is an estimate of availability, not a reservation.

Motion is limited to 150ms button color feedback; reduced motion disables transitions and map fitting is unanimated. All dynamic data is inserted with textContent, including Leaflet tooltip/popup nodes.

## Do's and Don'ts

- Do keep selection synchronized across hubs, map and schedule.
- Do provide loading, error, empty and partial-data recovery in the same panel structure.
- Don't label stored coordinates live or invent GPS freshness, route roads, or operating days.
- Don't expose Google API keys or require Google services for this first dashboard.

### Canonical UI Map

| Capability | Canonical owner | Source of truth | Allowed variants | Verification |
|---|---|---|---|---|
| Form | coordinates form and submit handler in dashboard.html/dashboard.js | DESIGN.md validation and location rules | manual coordinates, one-time geolocation | unit checks and manual browser checks |
| Scrollbar | global dashboard.css baseline | :root scrollbar tokens | forced-colors system rendering | static audit and stylesheet inspection |
