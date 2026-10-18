# Decision Log: F2 Compliance Retrofit

Status: Done for F2 · Date: Week 5

## Task 1: Three decisions

### 1. Authentication strategy: I went with session auth AND JWT, not one or the other

The problem I kept running into when thinking about this: the dashboard (people on the cooperative's team, logging in from a browser) and the buyer/registry integrations (machines talking to each other, no browser, no cookie jar) don't actually want the same kind of login. If I forced everyone through session auth, the buyer integration would have to deal with CSRF tokens and cookies, which is awkward for a non-browser client. If I forced everyone through JWT, dashboard users would have to manage access tokens by hand, which is a bad experience for a human.

So I just let both work at the same time. `DEFAULT_AUTHENTICATION_CLASSES` has both `SessionAuthentication` and `JWTAuthentication` in it, and DRF tries each one until something works, so individual views don't need to know or care which kind of login the caller used.

The trade-off is I now have two auth code paths instead of one, which is more for me to keep straight. I think it's worth it here specifically because the two kinds of users are genuinely different, not because "more options is always better."

What I'm NOT solving right now: if someone's JWT access token gets stolen, there's no way to kill it before it naturally expires. I did turn on refresh token rotation (`ROTATE_REFRESH_TOKENS = True`), so at least a stale refresh token can't be reused twice - but I haven't installed the blacklist app that would let me revoke a whole token's lineage mid-flight. That's a real gap, I'm just naming it instead of pretending it's handled.

### 2. Where the access rules actually live: one file (`core/rbac.py`), not scattered checks

This was the part I spent the most time thinking about before writing any code. The access matrix isn't a simple "this role can do more than that role" ladder - exporter_partner and compliance_auditor each see MORE of some things and LESS of others compared to each other. If I'd written `if role == 'exporter_partner': ...` checks directly inside each view and each serializer, I'd end up with the same logic copy-pasted in like five places, and the first time I updated one of them and forgot the others, the rules would quietly stop matching each other.

So instead I put every rule in one dictionary (`ROLE_RULES` in `core/rbac.py`) and made every view and serializer ask that dictionary what to do, instead of deciding for themselves. It's an extra layer to go look at if you're reading the code for the first time, which is a real cost - but I think it pays for itself the moment a new role gets added.

That's actually the direct question Task 3 asks: what happens when a fourth role shows up next season? With this setup, it's one new entry in `ROLE_RULES` - saying what that role's coordinate precision, national ID visibility, delivery scope, delivery fields, and audit access should be - plus maybe one more `if` branch in the two scoping functions if the new role needs row-level filtering like field_agent does. Nothing in any view, serializer, or URL has to change. The access rules are just data now, not logic buried in the request path.

### 3. How I handled coordinate precision for exporters: compute it fresh from the sector, don't store a second copy

The brief was pretty direct that rounding the decimal degrees wouldn't work, and once I thought about why, it made sense: two plots sitting right next to each other across a sector boundary would round to different numbers even though they're basically in the same spot, while two plots far apart inside the SAME sector could also round differently. Rounding is keyed to the number itself, not to which sector a plot is actually in - so it just doesn't match what the requirement is actually asking for.

What I did instead: `Sector.centroid()` averages the lat/lng of every plot currently sitting in that sector, calculated fresh each time it's asked for rather than stored anywhere. So every plot in sector S returns the exact same point (that sector's average), and a different sector averages a different set of plots, so it returns something different. That's actually keyed to the administrative unit, which is what was asked for.

The honest trade-off: this means an extra database query every time a plot gets serialized for an exporter, since I'm recalculating the average instead of just reading a stored number. On the pilot's small amount of data this is completely invisible. But if I'm honest about what happens at the scale F1 described (400 deliveries a day, a lot of plots), recalculating this per plot instead of once per request is going to add up. I know the fix - compute each sector's average once per request and reuse it for every plot in that sector, or cache it and invalidate when a plot's coordinates change - I just didn't build it yet. I'd rather admit that's unfinished than pretend I solved performance I didn't actually solve.

I did consider just storing a second set of coordinates on the Sector itself and updating it whenever a plot changes. It would be faster to read. But then there'd be two numbers that could disagree with each other - if someone adds a plot and the stored centroid doesn't get refreshed in time, now the system is telling Solange something that isn't actually true anymore. That felt like exactly the kind of problem her whole audit is trying to catch, so I'd rather be a little slower and always correct than fast and occasionally wrong.

## Task 3, answered directly: where's enforcement, and what does a 4th role cost?

Enforcement lives entirely in `core/rbac.py`. `ROLE_RULES` is the table of what each role gets; `scope_plot_queryset` and `scope_delivery_queryset` handle the row-level filtering (field_agent only seeing their own station); serializers call `get_role()`/`rules_for()` to decide what fields to actually show. Views just call into this module - they don't contain role names themselves.

Adding a fourth role next season costs: one new entry in `ROLE_RULES`, and maybe one more branch in the two scope functions if it needs the kind of row-filtering field_agent has. That's it. Views, serializers, and urls.py stay untouched. Whatever location precision the new role should get is just another value in its `ROLE_RULES` entry, handled by the same `if` in `PlotSerializer` that already handles `"full"` vs `"coarsened_sector"`.

## Task 4: how the audit log avoids becoming the thing it's auditing

`AccessLogEntry` records who looked at something, what role they had, what action they took, and what precision they actually got shown (`"full"`, `"coarsened_sector"`, `"masked"`) - but never the actual coordinate or ID value. That was a deliberate choice: if the audit log stored the real values, it would just be a second copy of the exact sensitive data it's supposed to be watching, which defeats the point. Logging happens right inside the serializers, at the moment a field is actually put into a response - so a request that never touches a sensitive field never creates a log row. The log reflects what actually got disclosed, not just how many requests came in.

What I haven't built: there's no retention policy and no "give me this season's summary" report - right now it's just a table you can filter (`GET /api/access-log/` with `action`/`role`/`user` filters). Answering Solange's actual question ("who's looked at identity data this season") means someone querying that table by date range right now, not clicking a button. Building that summary view felt like it should wait until there's real usage data to summarize against.