# Trusted distribution and antivirus review

[Documentation home](../README.md) · [Branding](branding.md)

Das Kreb is the product/vendor branding. A trusted Windows publisher is a separately validated legal signing identity. Branding alone cannot replace Authenticode signing or establish a clean antivirus result.

## Status

Version 0.13.0 downloads are unsigned. The 0.14.0 work adds vendor/version resources, the approved icon, per-user installer/uninstaller, signature verification and a signed-release workflow. Until the owner completes signing enrollment and a signed run passes, do not claim the new workflow has produced a verified-publisher release. Ordinary CI builds remain explicitly unsigned test artifacts.

## Owner setup

Use [Azure Artifact Signing](https://learn.microsoft.com/en-us/azure/artifact-signing/quickstart) with Public Trust identity validation. Individual validation uses the legal name on your identity/billing account; Das Kreb can appear as a verified organization publisher only if the provider accepts that organization identity. Enrollment, identity documents and any subscription purchase are performed by the owner, not entered into this repository or chat.

Create an Entra application with a federated OIDC credential for `repo:myke239/garmin-connect-mcp:environment:signed-release`. Assign only Certificate Profile Signer permissions scoped to the selected profile. Configure GitHub's `signed-release` environment to allow main and require owner review. Add `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_SUBSCRIPTION_ID` secrets and `SIGNING_ACCOUNT`, `SIGNING_PROFILE`, `SIGNING_ENDPOINT`, `SIGNING_PUBLISHER` variables. SIGNING_PUBLISHER is the exact validated certificate name, not an arbitrary label.

[Microsoft's action](https://github.com/Azure/artifact-signing-action) uses workload identity; no PFX/private key is committed. Dispatch Signed Windows release from main only after reviewed tests pass. The workflow refuses missing signing configuration and has no unsigned publication fallback. Inno Setup builds the installer and signed uninstaller using Microsoft's signing client. The signing runner needs a current x64 Windows SDK/SignTool (22621 or newer with current servicing) and .NET 8. The client MSI supplies the signing plugin, not SignTool; missing SDK tools stop publication. Local signing integration is not established until these prerequisites and owner credentials are present. Review [Inno's licensing](https://jrsoftware.org/isinfo.php) for your use; commercial use may require a compiler license. No signing/compiler subscription is purchased automatically.

## Release verification

The bundle's executable/DLL/PYD files must have valid trusted signatures, timestamps and the expected publisher. Installer and generated uninstaller are signed too. Run:

```powershell
./scripts/verify_signatures.ps1 -Path '<bundle directory>' -ExpectedPublisher '<validated certificate name>' -Recursive
```

`build_windows_installer.ps1` accepts `-UnsignedTest` only for development checks. The normal path requires signing tools and publisher verification. Tests install in an isolated application directory, verify launch and CompanyName, then uninstall while preserving a private-data sentinel. Installer registration refuses paths outside the standard versioned application root. Each version has its own uninstall entry; removing an older version cannot remove a newer receipt. Existing credentials/journals and other releases remain separate. Stop services using a version before uninstalling it. Reinstall Codex registration deliberately when moving to a new runtime.

Public release records include SHA256SUMS and release-integrity.json: final file hashes, source commit and an explicitly labeled build-environment package inventory. The inventory is not a claim that every development dependency ships. No Garmin private data is collected. Public executables exclude Garmin's separately licensed FIT SDK.

## Antivirus false positives

Publisher/reputation warnings and malware detections are separate. Even a signed new app may receive SmartScreen warnings; self-signed certificates do not establish public trust. [Microsoft guidance](https://learn.microsoft.com/en-us/windows/apps/package-and-deploy/smartscreen-reputation).

For an actual malware detection, record the exact security product/version, detection name, affected filename, SHA-256 and release URL. Submit only publicly shipped files to [Avast review](https://support.avast.com/avast/en/ww/home/current/solutions/submit-file-url) or [Microsoft's developer submission portal](https://www.microsoft.com/en-us/wdsi/filesubmission). Never upload credential folders, private journals, account recordings or logs with tokens. Keep the vendor case ID/status; a submission is not proof of clearance. Rebuild only for reviewed code/packaging changes, not to evade detection. Keep antivirus and TLS verification enabled.

The public evidence needed for a report is reproducible from the release checksums and integrity manifest. An exact detection and owner signing configuration are still needed to complete external review; no vendor clearance is claimed here.

Prepare the public review facts with `python scripts/antivirus_report.py <published executable or zip> --product <antivirus> --detection <exact detection> --release-url <project release URL>`. It prints a report and does not upload anything. Only submit the actual public release file and exact recorded detection to the vendor portal.


## Portable releases from 0.19.0

Run **Portable release** on main with the successful exact-commit **CI** run ID.
The workflow verifies the branch, source SHA, workflow identity and conclusion;
then builds Windows x64 and Ubuntu 22.04 x86-64 executables, verifies real MCP
handshakes and desktop construction, and creates platform archives and integrity
records. All builds must succeed before the publishing job runs. A tag that
already exists fails publication rather than silently replacing its assets.

Portable releases are explicitly **unsigned**. They do not publish the unsigned
development installer. `SHA256SUMS` covers both archives and integrity JSON.
The manifest inspects embedded Python archives on both platforms for the
restricted FIT SDK. Build-environment inventory is not a shipped-component SBOM.
Signed Windows releases continue to require the separate owner-enrolled workflow.


Linux PyInstaller bundles retain relative internal symbolic links. Portable
integrity records list each link and its target alongside hashes of the physical
files. Absolute, broken, cyclic or out-of-bundle targets are refused before
archive inspection. Windows/signed bundles retain the no-link restriction.
Normal frozen CI also runs production packaging, so release-only layout failures
are covered before a merge.
