# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users
- **Nhân viên tuyển sinh (primary):** works all day on a desktop computer, often while on the phone with a parent. Takes in learning requests, picks tutors to invite, chases requests that still need a tutor, records trial results and opens courses. Needs to see at a glance what needs action today and to finish each step quickly without re-reading the page.
- **Gia sư:** uses the system mostly in the evening. Updates profile and free time, answers class invitations (accept / reject within 24h), looks at assigned classes and their pay per session.
- **Admin:** occasional use. Manages accounts and roles, approves tutors' subjects, reviews the audit log, supervises requests and courses (read-only on enrollment work).
- Parents and students have no accounts; they are reached by phone and Zalo outside the system.

## Product Purpose
Internal operations system for a small online tutoring center in Vietnam. It replaces spreadsheets and chat threads for the core flow: learning request → rule-based tutor suggestion → invitations (first valid Accept wins) → trial lesson or direct enrollment → official course → lessons with Zoom (later phase) → session count and tutor pay. Success: the enrollment staff never loses a request, a parent gets a tutor fast, and tutors see exactly what is theirs.

## Positioning
Built around the center's own workflow and rules rather than generic CRM screens: invitation race with 24h expiry, trial-vs-direct-enrollment branch, per-session tutor pay, strict privacy (tutors never see parents' phone numbers or tuition).

## Operating Context
- University course project (Quản trị dự án TMĐT, ĐH Kinh tế – ĐH Đà Nẵng); MVP is demoed end-to-end at the final defense and must be explainable to a lecturer.
- Vietnamese UI throughout. Dates dd/mm/yyyy, money as 120.000đ.
- Desktop-first (~1366px laptop). Mobile layout is deferred to a later phase.
- Zoom and Zalo ZNS integrations come in Phần 5; currently simulated.

## Capabilities and Constraints
- Stack fixed: Django 6 templates + Bootstrap 5.3 (kept as the base so the student team can maintain it) + one project stylesheet `static/css/app.css`; font Be Vietnam Pro (kept).
- Built so far (Phần 1–4): login and roles, accounts + audit log, tutor profile and subject approval, tutor list/filter, learning requests (intake, list, detail with tutor suggestions, close), students, invitations (tutor side), courses (create, list with progress, detail, pause/cancel), tutor "Lớp của tôi".
- UI redesign must not change functionality, URLs, data or flows; all automated tests must keep passing.
- Pricing model is on hold (manual tuition / pay entry for now).
- Domain terms: Yêu cầu học tập (YC-xxxx), Lời mời nhận lớp, Khóa học (KH-xxxx), Buổi học, Học thử, Nhánh A (đăng ký thẳng), Thù lao, Đối soát.

## Brand Commitments
- No brand name, logo or colors yet; the working name is "Trung tâm Gia sư Trực tuyến". Visual identity is free to define.
- Keep Bootstrap 5 as the base and Be Vietnam Pro as the typeface.

## Evidence on Hand
- Demo data from `python manage.py seed_demo` (5 accounts, sample students, requests in every state, one course 8/10). No real customers, photos, testimonials or logos exist; do not invent them.

## Product Principles
1. Show what needs action now before totals: the enrollment staff's day is a queue, not a report.
2. One page, one primary action; state is always visible (every request, invitation, course and lesson shows its status in words).
3. Privacy by role: each role sees only what its job needs.
4. Every rule the system enforces is explained in plain Vietnamese at the point of action.

## Accessibility & Inclusion
WCAG AA contrast for text and controls, visible keyboard focus, status never conveyed by color alone, form errors tied to their fields for screen readers.
