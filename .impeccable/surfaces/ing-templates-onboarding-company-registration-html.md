---
version: 1
slug: "ing-templates-onboarding-company-registration-html"
primary_target: "onboarding/templates/onboarding/company_registration.html"
related_targets: ["onboarding/templates/onboarding/complete.html","onboarding/templates/onboarding/bot_config.html","onboarding/templates/onboarding/_design_system.html"]
---

## Scope & mode

The onboarding wizard: `company_registration.html` → `bot_config.html` → `complete.html`. Operate mode — the visitor is completing a task (register, configure), not deciding whether to buy (that's the landing's job, already done). Four other templates in this directory (`select_plan.html`, `payment.html`, `documents.html`, `company_setup.html`) plus `onboarding/base.html` are dead code from an earlier 6-step flow — no view renders them; they carry no visual authority and were left untouched.

`bot_config.html` is a partial exception: it extends the shared authenticated-platform shell (`subscriptions/base.html`, used by 18 other templates — dashboard, billing, admin). That shell is unredesigned and out of scope, so `bot_config.html`'s content was fixed to render correctly against its *existing* light/indigo palette, not switched to the tokens below. It inherits this brief's audience/task framing but not its visual system.

## Audience, job, proof, constraints

Same primary user as the landing (PRODUCT.md: PYMEs/negocios en LatAm sin equipo técnico) but past the decision — they already clicked "Empieza tu prueba gratis." The job here is registration + trial activation, not persuasion. Proof is procedural, not social: a visible step indicator and a working form are the only trust signals this surface needs: no logos, no testimonials, nothing borrowed from the landing's Persuade toolkit.

Constraint: PRODUCT.md's confirmed Brand Commitment binds this surface, not just Chatwoot itself — "la plataforma Django (`platform.lyvio.io`, superficie Operar) debe adoptar el sistema visual real de Chatwoot en `app.lyvio.io`." This wizard is the first surface built against that commitment.

## Direction

Dark by default, Radix slate scale (`slate-2`/`slate-12` verified live against the real app; the rest of the ramp is the same canonical Radix scale those two belong to — not independently re-verified this pass), brand blue `#2781F6`, system font stack (no webfont — a deliberate split from the landing's Inter), 8px radius everywhere, no hard shadows, `active:scale-[0.97-0.98]` + `hover:brightness-110` instead of the landing's translateY lifts. Implemented as a shared partial, `onboarding/templates/onboarding/_design_system.html`, included by every standalone step so registro/bot_config/completado read as one continuous product rather than three separately-designed screens.

Memorable moment: none by design. This surface's whole point is to be unremarkable — the visitor should feel like they're already inside the real product (the same product `app.lyvio.io` is), not touring a marketing artifact. Its coherence *with the platform*, not its own personality, is the craft target.

## Unresolved

- The Radix slate ramp beyond the two verified anchor points, and the success/danger semantic colors, were sourced from the canonical public Radix Colors palette rather than re-inspected live against `app.lyvio.io` — worth a live pixel-check if this surface gets more build-out.
- `bot_config.html` stays on the old light/indigo palette until `subscriptions/base.html` (and the 17 other templates it shells) gets its own redesign pass — an explicit, larger decision the user deferred, not an oversight.
- No comp/finish-reviewer round was run for this build (retrofitted onto already-shipped work outside the standard new-work flow); the tokens above are implementation-verified in the browser for `company_registration.html` only, template-verified (no screenshot) for the other two.
