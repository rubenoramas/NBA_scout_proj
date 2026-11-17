# Design guide: front office console

Every screen in Opponent Scout follows this guide, including screens not designed yet. The reference mockups are in `docs/design/` (see the bottom of this file). Match them.

The idea: a dense, professional analytics tool, like software a team's staff would use. Tables over cards, small labels, numbers that line up, one accent color, and no decoration.

## Rules that matter most

- **No hero sections or big headlines.** The largest text on a page is 20px (team abbreviations in the matchup band). Panel titles are 14px.
- **Full width.** Content fills the window up to a 1600px max width, with 24px side padding. No narrow centered column.
- **Tables before cards.** Lists of games, players, stats or matchups are table rows with a header row, not a grid of cards.
- **Dense spacing.** Rows are 34 to 40px tall. Panels have 10 to 16px padding. The gap between panels is 16px.
- **One accent color (blue).** Green and red mean only win and loss, or better and worse. Gold marks a standout stat or a warning tag.
- **Small radius.** 4px on panels, inputs and buttons, 3px on chips and tags. Never pill shapes on containers.
- **Tabular numbers everywhere** (`font-variant-numeric: tabular-nums`), and numbers right-aligned in table columns.
- **No team logos.** Teams appear as abbreviation chips.
- **No emoji, gradients, glows or shadows.** Separation comes from 1px borders and slightly different surface colors.
- **Show only what works.** A tab or button for a feature that is not built yet is either hidden or shown disabled with the word "Soon". The dashed placeholder panels in the mockups are for planning only and never ship.

## Colors

| Token | Hex | Use |
| --- | --- | --- |
| `--bg` | `#0D1015` | Page background, inputs |
| `--bar` | `#11151B` | Top bar, matchup band |
| `--panel` | `#13171D` | Panels |
| `--panel-head` | `#171C23` | Table header rows, secondary buttons |
| `--chip` | `#1C232C` | Team abbreviation chips |
| `--active` | `#222933` | Selected segment in a segmented control |
| `--border` | `#232A33` | Panel borders, panel header dividers |
| `--row-border` | `#1D232B` | Lines between table rows |
| `--control-border` | `#2A313B` | Inputs, buttons |
| `--chip-border` | `#36404C` | Team chips |
| `--text` | `#E7EAEE` | Main text |
| `--text-2` | `#C2C9D2` | Secondary text in rows |
| `--muted` | `#8E98A5` | Labels, column headers, hints |
| `--accent` | `#4F9DFF` | Primary button, active tab underline, links |
| `--accent-text` | `#7DB6FF` | Accent text on dark (tags, "Scout" links) |
| `--accent-tint` | `rgba(79,157,255,0.08)` | Highlighted row, "today" divider |
| `--win` | `#33C37E` | Wins, positive streaks |
| `--win-tint` | `rgba(51,195,126,0.14)` | W chip background |
| `--loss` | `#F26B6B` | Losses, negative streaks |
| `--loss-tint` | `rgba(242,107,107,0.14)` | L chip background |
| `--gold` | `#E8B44C` | Standout values, "Small sample" tag |

Primary button text on `--accent` is `#08111D`.

Put these in `:root` in `style.css` and use the variables everywhere. No other colors.

## Type

- Font: Inter (400, 500, 600, 700), with `system-ui, sans-serif` as the fallback. Load it from Google Fonts or self-host it in `app/static/`.
- Base: 13px.
- Panel titles: 14px, weight 600.
- Matchup band team names: 16px, weight 600. Team abbreviation blocks: 20px, weight 700.
- Labels and column headers: 11px, weight 600, uppercase, letter-spacing 0.06em, `--muted`.
- Team abbreviation chips: 11px, weight 700, letter-spacing 0.04em.
- Tags (NEXT, SMALL SAMPLE, SOON): 10px, weight 700, uppercase, letter-spacing 0.06em, 1px border, 3px radius.

## Layout

- **Top bar**, 48px tall, `--bar` background, on every page: product name, the team switcher (chip, team name, record), main navigation (Schedule, Scouting, Saved reports) with a 2px `--accent` underline on the active item, the team search box, and "Data as of" with a green dot.
- **Main area**: max width 1600px, centered, padding 16px 24px 32px.
- **Two-column pages** (schedule): main column `flex: 999 1 640px`, sidebar `flex: 1 1 340px`, wrapping to one column on narrow screens.
- **Dashboard pages** (scouting): a 12-column grid with a 16px gap. Panels span 4, 5, 7 or 12 columns. On narrow screens every panel spans 12.
- **Matchup band** (scouting pages): `--bar` background under the top bar. Our team on the left, game date and venue in the middle, the opponent on the right, then the section tabs.

## Components

- **Panel**: `--panel` background, 1px `--border`, 4px radius. Header: 10px 16px padding, title on the left, a muted note or controls on the right, 1px `--border` underneath.
- **Table**: a header row (`--panel-head`, 30 to 32px tall, label style) and data rows (34 to 40px tall, 1px `--row-border` between them). Columns are set with CSS grid so they line up. Wide tables scroll sideways inside their panel.
- **Team chip**: abbreviation in a box, 1px `--chip-border`, `--chip` background, 3px radius.
- **Result chip**: a W or L, 12px bold, in `--win` on `--win-tint` or `--loss` on `--loss-tint`.
- **Primary button**: `--accent` background, dark text, weight 700, 30 to 36px tall. One per screen at most.
- **Secondary button**: `--panel-head` background, 1px `--control-border`, weight 600.
- **Inline action link** (like "Scout"): 26px tall, 1px border `#2E4A6E`, `--accent-text`, with a small chevron.
- **Segmented control**: joined buttons in one border. The active one uses `--active` and `--text`, the rest `--panel-head` and `--muted`.
- **Stat tile grid**: label on top in label style, value under it at 16px bold, divided by `--row-border` lines.
- **Search input**: `--bg` background, 1px `--control-border`, search icon, 30 to 32px tall.

## States

- **Loading**: skeleton rows in the same shape as the real rows, using `--chip` colored bars. Never a full-page spinner.
- **Empty**: one muted line inside the panel, such as "No games this month".
- **Error**: one plain sentence inside the panel plus a secondary "Try again" button. The rest of the page keeps working.

## Accessibility

- Real `<button>`, `<a href>` and `<input>` with a label. Icon-only buttons get an `aria-label`.
- Text contrast at least 4.5:1. The colors above meet that on the panel and page backgrounds.
- Win and loss always carry the letter W or L, never color alone.

## Reference mockups

`docs/design/` holds the mockup source for three screens:

- `TeamSelect.html`: first visit, choosing your team
- `Schedule.html`: the landing page after a team is chosen
- `Scout.html`: the scouting overview

They are written in a design-tool format (tags like `<x-dc>`, `<sc-for>` and `<sc-if>`, and `{{ }}` holes filled by a small script at the bottom). Read them for exact styles, spacing and structure. Do not copy that format into the app: rebuild each screen as normal HTML, CSS and vanilla JS with the data coming from the API. The numbers in them are from Nov 16, 2026 and are for layout only.
