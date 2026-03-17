# SEB E-Commerce Compliance Plan

## What SEB requires vs. what we'll build

### 1. Contacts Page (`/contacts`) — NEW PAGE
Company details required by SEB:
- SIA "VN Media"
- Reg: 40203511357
- Address: "Sikšņi 1", Virešu pag., Smiltenes nov., LV-4355
- Email: info@vnmedia.lv
- Phone: 27001074

**Action:** Create `contacts.html` template (same structure as pricing.html — public navbar, standalone page). Add route in main.py.

---

### 2. Pricing Page — MINOR UPDATE
SEB wants: full product/service listing, price list with transaction currency, total cost info, note about possible additional costs.

The current pricing page already covers products/services and prices in EUR. We'll add:
- A small note under the pricing cards: "Visas cenas norādītas EUR. Papildu izmaksas netiek piemērotas — norādītā cena ir galīgā cena."
  (All prices in EUR. No additional costs — the displayed price is the final price.)

This is a SaaS with no shipping/customs, so we just need to state that clearly.

---

### 3. Terms of Service Page (`/terms`) — NEW PAGE
This single page covers SEB's remaining requirements:
- **Payment process** — step-by-step how purchasing works (choose plan → checkout → card payment via EveryPay → confirmation)
- **Accepted payment methods** — Visa, Mastercard via EveryPay/SEB
- **Security** — Mastercard SecureCode, Visa Secure (3D Secure)
- **Service delivery** — digital service, instant access after payment
- **Subscription management** — how to cancel/change
- **Refund policy** — 14-day cooling-off period per EU distance selling rules
- **Customer support** — info@vnmedia.lv (response within 24h), phone 27001074 (P-Pk 9:00–17:00, GMT+2)
- **Consent clause** — user agrees to terms before completing payment

**Action:** Create `terms.html` template. Add route in main.py.

---

### 4. Public Footer — NEW COMPONENT
Add `_public_footer.html` included on all public pages (pricing, contacts, terms, login, register). Contains:
- **Card logos:** Visa, Mastercard, Visa Secure, Mastercard SecureCode (SVG inline or from EveryPay)
- **EveryPay branding:** "Maksājumu apstrādi nodrošina EveryPay"
- **Links:** Cenas | Kontakti | Noteikumi
- **Company line:** © 2025 SIA "VN Media", Reģ. Nr. 40203511357

---

### 5. Navigation Update
Add "Kontakti" and "Noteikumi" links to `_public_navbar.html` center section (alongside existing "Cenas").

---

## Files to create/modify:
1. **CREATE** `app/templates/contacts.html` — Contact info page
2. **CREATE** `app/templates/terms.html` — Terms, payment, delivery, refunds
3. **CREATE** `app/templates/_public_footer.html` — Footer with card logos & links
4. **MODIFY** `app/templates/_public_navbar.html` — Add nav links
5. **MODIFY** `app/templates/_pricing_content.html` — Add EUR/final price note
6. **MODIFY** `app/templates/pricing.html` — Include footer
7. **MODIFY** `app/templates/login.html` — Include footer
8. **MODIFY** `app/templates/register.html` — Include footer
9. **MODIFY** `app/main.py` — Add /contacts and /terms routes
