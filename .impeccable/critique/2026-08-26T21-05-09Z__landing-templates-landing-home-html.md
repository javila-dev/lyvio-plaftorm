---
target: landing page
total_score: 23
max_score: 32
na_heuristics: 7,10
p0_count: 1
p1_count: 1
timestamp: 2026-08-26T21-05-09Z
slug: landing-templates-landing-home-html
---
## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 2 | Mobile hamburger toggles a CSS class with no rule behind it — zero visible feedback |
| 2 | Match System / Real World | 4 | Plain domain Spanish throughout; chat demo reads as authentic, not marketing-speak |
| 3 | User Control and Freedom | 2 | Mobile nav/login are completely unreachable (see P0) |
| 4 | Consistency and Standards | 3 | "One Blue Rule" mostly held; broken by the WhatsApp FAB's full-green surface and 2 skipped heading levels (h2→h4) |
| 5 | Error Prevention | 3 | Empty pricing state degrades gracefully to a clear mailto fallback |
| 6 | Recognition Rather Than Recall | 3 | Hamburger is icon-only with no visible label |
| 7 | Flexibility and Efficiency | n/a | Not applicable to a Persuade-mode landing page |
| 8 | Aesthetic and Minimalist Design | 3 | Floating WhatsApp+Chatwoot widget stack adds real, non-decorative clutter |
| 9 | Error Recovery | 3 | No real error paths to test; the one edge case (empty pricing) is handled well |
| 10 | Help and Documentation | n/a | Applicable-max rule allows skipping on landing pages |
| **Total** | | **23/32** | **Good (71.9%) — solid execution undercut by one real functional break** |

## Design Specificity Verdict

**LLM assessment:** Mixed, mostly authored. The hero chat-demo ("Ferretería El Tornillo," a real taladro-inalámbrico exchange) and the DIAN receipt section are genuinely specific — neither could be lifted onto a Wati or ManyChat page unchanged. The lapse: the five vertical-template icons are generic 3D stock-avatar illustrations, exactly the "iconografía genérica de IA" DESIGN.md itself says this system has zero of — ironic since that's the section meant to make a business owner "recognize su rubro."

**Deterministic scan:** 27 findings from detect.mjs in degraded mode (regex fallback — no real CSS parser in this environment). Once checked against DESIGN.md's prose exceptions, most of the 20 "undocumented color" hits are false positives already covered by name (#fff on dark surfaces, #D6CBB0 scrollbar, the 4 real channel-brand hex values, the brand-blue glow shadow). What survives as real drift: 3 undocumented border-radius values (10px/12px/6px, none on the 8/14/20/999 scale) and a pure-black shadow (rgba(0,0,0,0.5)) on the DIAN receipt card that violates DESIGN.md's own named "never pure black, always warm-tinted" shadow rule.

**Visual overlays:** the live browser pass (Assessment B, independent of A) found the same contrast problem A found by eye: 7 live-measured instances of #8f8878 on #fbf8f2 at 3.3:1, below the 4.5:1 AA minimum. It also caught 2 skipped heading levels (h2→h4, no h3) and one unexplained low-contrast value (#6e9bff, white text at 2.7:1) that doesn't appear literally anywhere in source. The "cream palette" and "pulsing dot" detector flags are confirmed-intentional — not real issues.

## Overall Impression

This is a real step up from the original page and the discipline shows: one blue, warm neutrals, no gradients, tabular numbers, honest copy. Undercut by exactly one severe functional break — mobile visitors cannot reach navigation or login at all — plus a floating-widget collision that two independent methods (a design director's eye and a live contrast scanner) both caught from different angles.

## What's Working

1. **The hero chat-demo** — specific, honest, shows-don't-tells in the first viewport without fabricating anything.
2. **The DIAN section** — the one moment on the page a competitor couldn't copy-paste.
3. **Color/spacing discipline** — the "One Blue Rule" and warm-neutral system are visibly consistent.

## Priority Issues

**[P0] Mobile navigation is completely dead.** #mobile-menu-btn toggles an active class on .primary-nav (JS), but no .primary-nav.active CSS rule exists to override display:none at ≤860px — and .header-actions .btn-ghost{display:none} hides "Ingresar" at the same breakpoint. Why it matters: the primary audience decides on their phone between customers (PRODUCT.md) — mobile visitors have zero path to nav or login. Fix: add the missing .primary-nav.active panel CSS and surface "Ingresar" inside it. Suggested command: /impeccable harden.

**[P1] The floating WhatsApp + Chatwoot widgets cover real content and break the color rule.** At 375px, the WhatsApp FAB covers the word "bot" in the chat-demo caption; the Chatwoot bubble covers the Verticals and DIAN h2s as the page scrolls. The FAB's full-green surface is also a plausible violation of the One Blue Rule. Fix: collapse Chatwoot to icon-only on mobile or reposition so widgets never sit at heading height. Suggested command: /impeccable harden.

**[P2] Systemic sub-AA contrast on --ink-faint, confirmed independently twice.** #8F8878 on #FBF8F2/#FFFFFF measures 3.3–3.5:1 against 4.5:1, live-verified at 7+ instances. Why it matters: the two trust bullets under the primary CTA are the hardest line on the page to read. Fix: darken --ink-faint and re-verify ≥4.5:1. Suggested command: /impeccable harden.

**[P2] Design-system drift: a pure-black shadow and 3 undocumented radii.** The DIAN receipt card uses rgba(0,0,0,0.5), violating the documented "never pure black" shadow rule; 3 border-radius values (10/12/6px) sit off the 8/14/20/999 scale. Fix: swap the shadow to a warm-tinted value, snap the radii onto the scale or document them. Suggested command: /impeccable audit.

**[P3] Vertical-card icons contradict the system's own "no generic AI iconography" rule.** The five illustrations are generic 3D stock avatars. Fix: replace with something grounded in the product. Suggested command: /impeccable adapt.

## Persona Red Flags

**Jordan (First-timer):** Taps the mobile hamburger expecting Ayuda/Precios — nothing happens. Icon-only button with no visible label.

**Riley (Stress tester):** Probes the hamburger toggle — DOM class changes, zero visual effect. Confirmed real occlusion of the DIAN and Verticals headlines by the floating widgets.

**Casey (Mobile, distracted):** Primary CTA correctly thumb-zone and full-width. But scrolling one-handed, repeatedly hits headlines partially covered by the two stacked widgets.

**"Marta" (project-specific, PRODUCT.md's primary user):** None of the 5 vertical templates is "ferretería/retail físico" — her exact business type, the one the hero itself uses to sell the product. She'd also reach first for the WhatsApp FAB — the same button currently hiding the DIAN headline for her.

## Minor Observations

- 2 skipped heading levels (h2→h4, no h3) on the Verticals and Final-CTA sections.
- Final CTA repeats the hero's headline/lede almost verbatim instead of closing on the strongest proof.
- One paragraph runs ~107 chars/line, exceeding the documented ≤62ch body measure.
- Header carries 6 interactive targets, at the ≤5 top-level-nav guideline's edge; 5 vertical cards is one over the ≤4-per-group chunking ideal.
- Trust-line's "·" separator orphans onto its own line on mobile.
- An unexplained #6e9bff low-contrast (2.7:1) white-on-blue value was caught live but doesn't appear in source.
- GTM/Meta Pixel/Clarity load synchronously in <head> ahead of CSS.

## Questions to Consider

1. The hero sells the product using "Ferretería El Tornillo," but no vertical template covers retail/ferretería — should the verticals list include the exact business type the page uses to sell itself?
2. Two floating buttons compete for the same "talk to us" intent — does a WhatsApp-first audience need both, or would collapsing to one solve the occlusion and the color-rule break at once?
3. If Final CTA is the last thing a visitor sees, why repeat the hero instead of closing on the strongest, most specific proof?
