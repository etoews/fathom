# Private fixtures

Drop your own dive footage here for manual validation runs against real content. This whole directory is gitignored — nothing here ends up in the public repo.

The test suite should treat the presence of files here as **optional**:

- If `private/*.mp4` exists, tests that need real content can use it.
- If not, those tests should skip (not fail) with a clear message.

The point of `private/` is the "did the heuristic actually do something useful?" sanity check on real footage that the public fixtures can only approximate.
