# Contributing

For a bug report, include the app/backend version, Android and WebView versions, Linux distribution, and steps to reproduce it. Expected and actual behavior help more than a screenshot alone. Remove pairing codes, tokens, desktop passwords, private addresses and process command lines before sharing diagnostics.

Keep pull requests focused on one problem. Explain the resulting behavior and how it was checked. Run the tests listed in the [README](README.md); changes to an Android-only path should also say whether they were tested on a device.

Tests must use temporary directories and disposable child processes. Do not stop existing services, containers, desktop sessions or VPN connections. Keep the backend in the Python standard library unless a dependency has a clear benefit.

Changes to authentication, privileged helpers or file handling need regression tests for the affected permission and cleanup boundaries. Root helpers must remain limited to their documented operations. UI changes should work with touch input, dark mode, fullscreen and reduced motion.

Keep third-party headers and notices. Document the source and license of new dependencies or assets. Contributions are distributed under Apache-2.0, except assets covered by separate terms.

Before publishing an archive, run `python3 -B scripts/check_release.py`. Keep local configuration, runtime data, signing files and downloaded tools out of commits. For a vulnerability, use the [private reporting channel](SECURITY.md).
