# Provider manifest templates

Pull-on-demand, like every other directory under `templates/`: a project copies
one of these into its own `providers:` declaration and edits it, rather than
this pack shipping a registry a project reads from directly (D31).

Each file here is `runtime-pack-provider-1`, validated by
`tools/provider_manifest.py`. A template is **dormant by construction**: no
credential reference, `billing.authorised_by: null`. Registering it unchanged
adds a validated record and routes nothing — `fingerprint` and `routability`
still return `NOT_ROUTABLE_UNAUTHORISED` for it, because registration is not
authorisation (D31, D34). Activating a template is a founder decision that
edits its billing and credential fields deliberately; this directory does not
do that for anyone.

`moonshot-kimi-code.dormant.json` is retained at negligible cost to exercise
the `anthropic-compatible` seam a second time; it carries no credential, no
qualification campaign and no private source (D34).
