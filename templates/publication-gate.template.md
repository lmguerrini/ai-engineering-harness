# Publication gate — <project>

Instantiate per project. **Every step below is human-gated** (HITL row 2). The
coordinator prepares and verifies; it never pushes.

The invariant this protects, from `skills/core/public-safety.md`: a repository
is publishable when an **allowed source ref**, **reachability**, an **exact push
refspec** and a **verified remote postcondition** hold together. Three of those
are local claims. The fourth is the only observation of what actually happened.

## Order, and why the order is the content

A cleanup performed minutes before a push is a race against a writer that
re-creates refs in under a minute. Steps 1–4 therefore happen in the *same*
step as the push, not earlier in the session.

1. **Stop or scope out the writer.** If a known local service mutates git
   metadata (an IDE provenance service is the observed class), stop it first.
   No in-repo control outruns a daemon watching the repository, so this is a
   human step and cannot be delegated to a gate.
2. **Delete non-publishable refs.** Notes refs, recovery branches, agent
   worktree branches. Verify each is gone.
3. **Enumerate the namespace and judge it**, in the same step as the push:

   ```
   python3 <pack>/tools/publication_gate.py --project PROJECT.yaml \
       --public-ref refs/heads/<branch> \
       --author "<Name> <email>" \
       --push-command "git push <remote> refs/heads/<branch>:refs/heads/<branch>"
   ```

   Exit 0 is required before proceeding. A `COULD NOT CHECK` line is a failure,
   not an absence of findings.
4. **Full-history outgoing scan** at the exact revision being published:

   ```
   python3 <pack>/tools/outgoing_scan.py --project PROJECT.yaml refs/heads/<branch>
   ```

5. **Push exactly one refspec.** Never `--mirror`, `--all`, `--tags`, or
   `refs/*:refs/*`.

   ```
   git push <remote> refs/heads/<branch>:refs/heads/<branch>
   ```

6. **Verify the remote and fail closed:**

   ```
   python3 <pack>/tools/publication_gate.py --project PROJECT.yaml \
       --public-ref refs/heads/<branch> --verify-remote <remote>
   ```

7. **Allow the writer to resume.**

**If any non-publishable ref becomes reachable from the published branch: stop.**
A push cannot be taken back, and `--amend` does not reach an earlier blob.

## Record

| | |
|---|---|
| Revision published | |
| Refs enumerated / non-publishable found | |
| Writer stopped | |
| Push command, verbatim | |
| Remote refs after push | |
| Residual risk accepted, and by whom | |
