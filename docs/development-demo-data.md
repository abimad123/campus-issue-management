# Synthetic operational demo data

Run this command against the local Docker stack:

```powershell
docker compose exec backend python manage.py seed_operational_demo
```

On first creation, the command securely prompts for one development-only password used for accounts it creates in that run. It does not display, store in source, or reset existing passwords. Re-running the command does not prompt when all demo accounts already exist. If an institutional ID is already held by a non-demo account, the command chooses an unused `DEMO-`-prefixed variant and reports the actual ID. Accounts are matched by their synthetic `.test` email and ID; conflicts with non-demo account data abort the transaction.

The command creates these synthetic roles and IDs (with a numeric suffix only if a proposed ID is already occupied):

| Name | Role | Institutional ID | Login email |
| --- | --- | --- | --- |
| Demo Student 1 | Student | `DEMO-STU-001` | `demo-student1@example.test` |
| Demo Student 2 | Student | `DEMO-STU-002` | `demo-student2@example.test` |
| Demo Staff 1 | Staff | `DEMO-STAFF-001` | `demo-staff1@example.test` |
| Demo Staff 2 | Staff | `DEMO-STAFF-002` | `demo-staff2@example.test` |
| Demo IT Technician | Technical Staff · IT Support | `DEMO-TECH-001` | `demo-it-technician@example.test` |
| Demo Network Technician | Technical Staff · Network | `DEMO-TECH-002` | `demo-network-technician@example.test` |
| Demo Electrical Technician | Technical Staff · Electrical | `DEMO-TECH-003` | `demo-electrical-technician@example.test` |
| Demo Maintenance Technician | Technical Staff · Maintenance | `DEMO-TECH-004` | `demo-maintenance-technician@example.test` |
| Demo Admin | Admin | `DEMO-ADMIN-001` | `demo-admin@example.test` |

Login accepts either the institutional ID or the listed email, plus the password entered when that account was first created.

The seed reuses active campus categories, locations, and teams already in the database. It creates clearly named `DEMO-RULE-*` routing rules and one `DEMO - Standard campus response` SLA policy because the existing verification rules are inactive. Issues are submitted through the normal issue serializer and assignment/SLA pipeline. Work orders are created only for seeded issues that received a real eligible technician assignment. No network measurements are fabricated.

Six issues are tagged in their descriptions with stable `DEMO-ISSUE-*` references; work orders use `DEMO-WO-*` markers. The command uses a database transaction and is idempotent. It does not delete or rewrite existing issues, work orders, network measurements, or user passwords. A real assignment failure is reported and left in the Admin-visible unassigned queue rather than presented as a successful assignment.
