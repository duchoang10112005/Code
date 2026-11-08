---
version: 1
slug: "templates"
primary_target: "templates"
related_targets: ["static/css/app.css"]
---

# Surface: Toàn bộ ứng dụng nội bộ (Phần 1–4)

Mode: operate. Audience: NV tuyển sinh (primary, desktop, all day, often on the phone), gia sư (evenings), admin (occasional).
Job: see what needs action now, act in one step, never lose a request. Constraint: Django templates + Bootstrap 5.3 base, Be Vietnam Pro, no change to behavior/URLs/tests. Desktop-first (≥1280px).

## Direction contract
THESIS: The working day is a page of a Vietnamese "sổ liên lạc": records are labelled like a notebook name-tag and the system writes its remark in red ink. Refuses the generic SaaS dashboard (white sidebar, four metric cards, grey table).
OWN-WORLD: Deep notebook-cover blue shell (#1d3a7a family) with a white double-ruled name-tag; cool blue-white page ground; blue ink for data and links; red ink reserved for "lời phê" (what needs action); status marks drawn as line form (solid running, dashed waiting, struck closed) plus words; record identity shown as a double-ruled tag (mã · tên · lớp · môn). Be Vietnam Pro only, 8px grid.
STORY: The staff member opens the app and reads today's page: grouped queue with the system's red remark telling the next step; one click opens the record; every rule is explained in plain Vietnamese at the point of action.
FIRST VIEWPORT: Left cover rail (name-tag with role + user, nav with counts in red only when action is due). Main: page title "Việc cần làm hôm nay" + date + one primary action (Tiếp nhận yêu cầu) top right; below, the queue grouped by job (cần mời thêm, chờ chốt, sắp hết buổi, lời mời đang chờ) as rows: name-tag · state · red remark · action. Counts live in group headers, not metric cards.
FORM: grounded candidate 4 of 7 (sổ liên lạc), assigned by roll. Raises: line-form status (from emission rail); strict 8px grid (Crouwel); urgency by size step (star atlas); changed state stays marked until opened (gate board). seed:192f392ca5c12b31
FINISH: unreviewed and undocumented is unfinished; this build ends with the finish review, the verdict, DESIGN.md, and every shipping raster carrying its provenance
