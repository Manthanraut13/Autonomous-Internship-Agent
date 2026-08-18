---
name: Glacial Precision
colors:
  surface: '#f8f9ff'
  surface-dim: '#cedbef'
  surface-bright: '#f8f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#eef4ff'
  surface-container: '#e4efff'
  surface-container-high: '#dce9fe'
  surface-container-highest: '#d6e4f8'
  on-surface: '#0f1c2b'
  on-surface-variant: '#41474f'
  inverse-surface: '#243141'
  inverse-on-surface: '#e9f1ff'
  outline: '#717880'
  outline-variant: '#c1c7d1'
  surface-tint: '#136299'
  primary: '#136299'
  on-primary: '#ffffff'
  primary-container: '#5b9bd5'
  on-primary-container: '#003151'
  inverse-primary: '#98cbff'
  secondary: '#984623'
  on-secondary: '#ffffff'
  secondary-container: '#fe956c'
  on-secondary-container: '#752c0b'
  tertiary: '#006b5c'
  on-tertiary: '#ffffff'
  tertiary-container: '#39a794'
  on-tertiary-container: '#00362e'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#cfe5ff'
  primary-fixed-dim: '#98cbff'
  on-primary-fixed: '#001d33'
  on-primary-fixed-variant: '#004a77'
  secondary-fixed: '#ffdbce'
  secondary-fixed-dim: '#ffb599'
  on-secondary-fixed: '#370e00'
  on-secondary-fixed-variant: '#7a300e'
  tertiary-fixed: '#8df5df'
  tertiary-fixed-dim: '#70d8c3'
  on-tertiary-fixed: '#00201b'
  on-tertiary-fixed-variant: '#005045'
  background: '#eef2f7'
  on-background: '#0f1c2b'
  surface-variant: '#d6e4f8'
  surface-ice: '#f4f7fb'
  sidebar: '#dce6f0'
  border-muted: '#d4dde8'
  score-mid: '#e8a94a'
  score-low: '#d66b6b'
  text-secondary: '#4a6080'
  text-tertiary: '#7a95b0'
typography:
  display-lg:
    fontFamily: Hanken Grotesk
    fontSize: 22px
    fontWeight: '700'
    lineHeight: 32px
    letterSpacing: -0.01em
  section-header:
    fontFamily: Hanken Grotesk
    fontSize: 15px
    fontWeight: '600'
    lineHeight: 24px
    letterSpacing: 0.05em
  body-main:
    fontFamily: Hanken Grotesk
    fontSize: 13px
    fontWeight: '400'
    lineHeight: 20.8px
  body-sm:
    fontFamily: Hanken Grotesk
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 18px
  label-bold:
    fontFamily: Hanken Grotesk
    fontSize: 13px
    fontWeight: '600'
    lineHeight: 16px
  display-lg-mobile:
    fontFamily: Hanken Grotesk
    fontSize: 20px
    fontWeight: '700'
    lineHeight: 28px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  sidebar-width: 220px
  header-height: 64px
  gutter: 1.5rem
  margin-mobile: 1rem
  stack-gap: 0.75rem
---

## Brand & Style

The design system for the Autonomous Internship Agent is built on the narrative of **"Automated Intelligence with a Human Pulse."** It evokes the feeling of a high-end, efficient, and calm workstation. The aesthetic is a refined mix of **Minimalism** and **Modern Corporate**, utilizing a "cold-light" atmosphere that minimizes cognitive load for high-density information management.

The brand personality is professional, hyper-organized, and slightly futuristic—like a digital laboratory. It avoids the starkness of pure white in favor of icy, blue-tinted grays, which reduce eye strain during long-form task management. Restrained warm accents (terracotta and amber) are used surgically to draw attention to critical actions or human-centric data points amidst the automated logic.

## Colors

The palette is anchored by "Steel Blue" and "Pale Ice," creating a sophisticated, low-contrast foundation that feels expansive and clean. 

- **Primary & Secondary:** Steel Blue serves as the main driver for interactive states, while Terracotta provides a distinct, warm contrast for high-priority notifications or "human" interventions.
- **Surface Hierarchy:** The background uses a cool grey-blue (`#eef2f7`), while the sidebar uses a slightly deeper tint (`#dce6f0`) to establish clear functional zones. Pure white is reserved exclusively for the highest level of elevation (modals and active cards).
- **Functional Accents:** Seafoam Teal, Amber, and Rose-Red are used strictly for status and scoring, ensuring data visualization is intuitive and legible against the cool-toned backdrop.

## Typography

The typography leverages **Hanken Grotesk** (as a high-quality alternative to Google Sans) to maintain a modern, geometric, and highly legible appearance suitable for an internship management platform.

- **Headlines:** Display headings are compact and bold, utilizing a slight negative letter-spacing to feel more authoritative.
- **Sectioning:** Section headers use uppercase styling with increased letter-spacing to create clear visual anchors in dense dashboards.
- **Body Text:** A line height of 1.6 is strictly maintained for the 13px body font to ensure that complex agent logs and task descriptions remain readable.
- **Color Application:** Use `Text Primary` for headings, `Text Secondary` for standard body copy, and `Text Tertiary` for metadata or inactive labels.

## Layout & Spacing

The layout utilizes a **Fixed Sidebar** model to provide constant access to navigation, reflecting the persistent nature of an autonomous agent.

- **Navigation:** A 220px fixed left sidebar in `#dce6f0` creates a vertical anchor. The top header is 64px, reserved for global search and agent status.
- **Rhythm:** An 8px base grid drives the spacing. Gutters are set at 24px (1.5rem) for desktop to provide breathing room between data widgets.
- **Responsive Behavior:** 
    - **Desktop:** 220px Sidebar + Fluid Content Area.
    - **Tablet:** Sidebar collapses to an icon-only rail (64px) to maximize content space.
    - **Mobile:** Sidebar moves to a bottom navigation bar or a hidden drawer; margins reduce to 16px.

## Elevation & Depth

Depth is achieved through **Tonal Layering** and subtle, crisp shadows rather than heavy blurs.

- **Base Layer:** The background (`#eef2f7`) sits at the lowest level.
- **Sub-Surface:** Sidebar and inactive panels use `#f4f7fb`.
- **Active Surface:** Main content cards and data entries are `#ffffff` with a subtle 1px border in `#d4dde8`.
- **Interactive Elevation:** On hover, cards do not necessarily rise; instead, the border color shifts to `Primary Accent` (`#5b9bd5`).
- **Modals:** Use a centered position with a soft ambient shadow (0px 8px 24px rgba(30, 43, 58, 0.08)) to distinguish from the workspace.

## Shapes

The design system uses a multi-tier corner radius strategy to organize information hierarchy:
- **Small (8px):** Used for buttons, input fields, and small UI controls.
- **Medium (12px):** Used for standard data cards and list items.
- **Large (16px):** Used for primary container blocks, modals, and the main dashboard sections.

This progressive rounding helps users subconsciously group elements—tighter radii for interactive components and softer radii for structural containers.

## Components

- **Buttons:** Primary buttons use `Primary Accent` with white text. Secondary buttons use a transparent background with a `Border` and `Text Secondary`. Use 180ms ease transitions for all hover states.
- **Chips/Badges:** Small badges for "Task Status" use the success/mid/low colors with 10% opacity backgrounds and 100% opacity text of the same hue.
- **Input Fields:** 8px radius, `#ffffff` background, and a `#d4dde8` border. On focus, the border transitions to `Border Active` with a subtle outer glow.
- **Sidebar Items:** Active states use a "pill" highlight with a 4px vertical bar on the left edge in `Primary Accent`.
- **Cards:** White background, 12px or 16px radius. No shadow by default; 1px border only.
- **Agent Logs:** Use a monospace-adjacent weight of the font for timestamped logs to differentiate automated output from user-facing UI.