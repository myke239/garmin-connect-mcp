# Garmin Connect MCP documentation

Choose a guide by what you want to do. Start with installation; API details and historical test evidence have their own sections.

[Project and downloads](../README.md) · [Changelog](../CHANGELOG) · [Issues](https://github.com/myke239/garmin-connect-mcp/issues)

## Getting started

1. [Install](getting-started/installation.md): executable or managed runtime, standard paths, authentication, updates and removal.
2. [Connect Codex or another MCP client](getting-started/codex.md): registration, skills and stdio configuration.
3. [Connect ChatGPT and your phone](getting-started/chatgpt.md): personal HTTPS tunnel, OAuth and local consent.


## Task guides

| Goal | Guide |
| --- | --- |
| Create, verify and schedule a workout | [Workout workflow](guides/workouts.md) |
| Correct sleep times, naps and exact records | [Sleep and corrections](guides/sleep-and-corrections.md) |
| Save account changes with the right contract and consent | [Account writes](guides/account-writes.md) |
| Review strength preparedness, recovery and nutrition | [Coaching evidence](guides/coaching.md) |
| Read Lifestyle fields and historical amounts | [Lifestyle reports](guides/lifestyle.md) |
| Interpret recovery and use running/strength/swim builders | [Recovery and builders](guides/recovery.md) |
| Archive recordings, analyze samples and manage existing workouts | [Archive and analysis](guides/archive-and-analysis.md) |
| Restrict tools/operations or protect Linux storage | [Permissions and storage](guides/permissions-and-storage.md) |
| Diagnose login, scheduling, scopes or uncertain outcomes | [Troubleshooting](guides/troubleshooting.md) |

## Reference

- [MCP tool reference](reference/tools.md): all 58 default tools, parameters, annotations and descriptions.
- [Workout sports and completed activities](reference/sports.md): distinct schemas, verified sport IDs and unsupported fields.
- [Yoga poses](reference/yoga-poses.md): 85 exact identifiers, verification scope and [CSV](reference/catalogs/verified-yoga-poses.csv)/[JSON](reference/catalogs/verified-yoga-poses.json) catalogs.
- [Data, privacy, units and limits](reference/data-and-limits.md): storage, response boundaries and missing-data behavior.

## Development and evidence

- [Contributing](../CONTRIBUTING): issue/PR workflow and offline checks.
- [Coaching research](development/coaching-research.md): metric families, evidence and prospective-validation gates.
- [Verification history](development/verification-history.md): dated release gates and platform/account evidence.
- [Write audit](development/write-audit.md): historical live operation coverage and cleanup evidence.
- [Roadmap and current status](development/roadmap.md): shipped phases and remaining limits.
- [Trusted distribution](development/distribution.md): signing, installer verification and antivirus review.
- [Das Kreb branding](development/branding.md): approved vendor logo and usage rules.
- [Documentation maintenance](development/documentation.md): structure, reviewed examples and link checks.
- [Deferred partner API experiment](../gpt-actions/README.md): separate from the working personal MCP connection.

Query `get_garmin_write_schema` and `get_garmin_workout_schema` for the installed server's exact current contracts. Examples in the guides explain the workflow; they do not authorize account changes.

- [Write coverage and research gates](development/write-coverage.md): implemented corrections, noneditable metrics and contracts still awaiting verification.

See also [shared HTTPS hosting](getting-started/shared-hosting.md) for multiple connectors behind one ngrok origin.
