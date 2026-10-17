# personal-world backlog

This file is the tracking doc for work that was open in GitHub Issues and was closed as not planned on 2026-10-07, so the queue could reach zero without losing the backlog.
The issue bodies themselves are not edited; every summary below is ours, written from the body as it stood.
To restart an item, reopen the linked issue, or open a new one and delete its row here.
The list was built by rule, not by judgement: every issue open in this repository on 2026-10-07 appears below, newest first.

### #268 — Studio's vendored Worlds kit is behind ui/dist-kit; re-stamp must carry icons.svg + daylight

- Issue: https://github.com/rylee-bee-labs/worlds/issues/268
- Opened: 2026-10-04 · Labels: none
- OPEN: Studio still vendors the Worlds kit at static/kit (checked 2026-10-15); reopened by owner decision 2026-10-15. Tracked by the studio item; issue to file by coordinator.

Studio vendors this kit into its own static copy, and its agent instructions say not to hand-edit that copy: fix kit bugs here upstream, then re-stamp it there.
A diff of the two trees shows the vendored copy is behind the published build. The recorded kit version strings differ, so the vendored copy has not been re-stamped since an earlier build.
The vendored copy also carries one fewer theme — it is missing `daylight` — and its token stylesheet scopes rules to the bare root selector, which lets a theme swatch paint Station's colours inside a different theme.
The published build has an icon class in its base stylesheet, documented as drawing from an icon sheet shipped beside the file; the vendored copy has no such class, so the icons do not survive the stamp.
Three comment lines also drifted apart between the two copies.
The ask is to fix whatever is genuinely missing on this side and then re-stamp in Studio, rather than patching the vendored copy by hand.

Next step, when this is picked up: re-stamp Studio from the current published build, after fixing upstream anything the diff shows is really missing.

### #267 — Execute the Play-Nice semantic-kernel rebuild

- Issue: https://github.com/rylee-bee-labs/worlds/issues/267
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

This issue asks for the front-door machine model to be rebuilt on the smallest useful Play-Nice semantic kernel.
The architecture decision and the executable plan live in the earlier pull request, not in this issue, so this issue is the execution ticket.
A stated goal is to keep the Worlds product language down to four surfaces — Home, Connect, Memory, Settings — and to drop old internal models rather than keep them alive for compatibility.
The issue is explicit that only the first packet may start: a vocabulary inventory plus a deletion map, taken from the kernel plan document in this repo's rebuild docs.
That inventory covers the worlds source tree, the front-door UI source, the generated UI tree, and the rebuild docs, and each concept gets classified as belonging to Play-Nice, to Worlds, to an adapter, as derived, as historical, or as unknown.
Anything classified historical has to name the evidence or behaviour worth keeping before it is deleted, so the deletion map is reviewable rather than a bare list of removals.
No semantic refactor is to begin until that inventory has been reviewed in the implementation pull request; the remaining packets then follow serially.

Next step, when this is picked up: produce the vocabulary inventory and deletion map as a reviewable pull request, and change nothing else.

### #263 — Finish applicable main maintenance reconciliation before cutover

- Issue: https://github.com/rylee-bee-labs/worlds/issues/263
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

This issue is about reconciling two diverged branches before the front-door cutover.
As observed on 2026-10-04, the long-lived branch carries one repository-truth cleanup and the rebuild branch carries its own front-door-specific equivalent; the rebuild branch is well ahead and slightly behind, with a merge base well back.
Divergence is explicitly expected, and the goal is stated as making the two branches byte-identical never — the goal is that no applicable maintenance, security or contract fix is lost.
The issue therefore asks for the main-side commits to be classified one by one, each as either already reconciled in meaning on the rebuild branch or as still needing a real port.
Two of them carry explicit do-not-port instructions: one contributes a hard-coded commit-hash table that the rebuild branch replaces with derived branch and runtime routing, and the other contributes old-app documentation that the rebuild branch's continuity model supersedes.
The remaining classification work is the substance of the issue: whatever is judged applicable has to actually land on the rebuild branch before cutover.

Next step, when this is picked up: walk the main-side commits against the rebuild branch's reconciliation pull request and confirm each applicable fix is present there.

### #262 — Front-door rebuild: finish Phase 4 retirement and cutover readiness

- Issue: https://github.com/rylee-bee-labs/worlds/issues/262
- Opened: 2026-10-04 · Labels: none
- Status on 2026-10-07: closed as not planned on 2026-10-07 — tracked here

This issue is the durable queue for the remainder of Phase 4 of the front-door rebuild, which is active on the rebuild branch.
An earlier pull request in that phase re-anchored the framework gate, the restore drill, the route and interface inventory, the CLI, the container image entrypoint and the recovery docs onto the new app, and it deliberately left some work unfinished.
The remainder recorded here is: decide on and finish the API-only route removals from that phase's list; decide whether the old vault at-rest and per-person-isolation tests should be retired or replaced; and finish retiring backend tests that only exercise behaviour belonging to the deleted old app.
There is also an external dependency: a Station-preview caller in the homelab setup still invokes the old initialisation path, and the issue notes that caller is owned by homelab and must not be silently changed here.
Finally the issue asks for the last cutover-readiness gates to be run against the rebuild branch, and it restates that production cutover still needs explicit owner approval.

Next step, when this is picked up: work down the remainder list on the rebuild branch, starting with the outstanding API-only route removals.
