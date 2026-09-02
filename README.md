# pragmaticBIM Public Swiss

Public Swiss [Elementplan](https://elementplan.pragmaticbim.ch) master template.

It follows the [abstract use case classification](https://schema.pragmaticbim.ch/classification/usecase.html) and keeps information requirements small enough for early design with [abstractBIM](https://www.abstractbim.com/).

## Use cases

Parent workflows use the official classification codes:

| Code | Role |
| --- | --- |
| BES | Ordering |
| CON | Construction |
| DEC | Deconstruction |
| DES | Design |
| HOV | Handover |
| OPR | Operation |
| QAS | Quality assurance |

Three project workflows sit under that structure:

| Workflow | Parent | Purpose |
| --- | --- | --- |
| DES-COST | DES | Element-based cost calculation from abstractBIM quantities |
| DES-BPS | DES | Building performance simulation from abstractBIM |
| QAS-COORD | QAS | Coordination and model checking |

## Domains

- **Architecture** — source model for abstractBIM (spatial structure, spaces, windows, doors)
- **MEP** — uses the same spatial structure and interior/exterior spaces for simulation and coordination

Models (Teilmodelle) are project-specific and are not part of this template.

## Elements

For **DES-COST** and **DES-BPS**:

- Project (`IfcProject`)
- Site (`IfcSite`)
- Building (`IfcBuilding`)
- Storey (`IfcBuildingStorey`, with `Elevation`)
- Interior spaces (`IfcSpace`, `PredefinedType=INTERNAL`)
- Exterior spaces (`IfcSpace`, `PredefinedType=EXTERNAL`)
- Windows (`IfcWindow`)
- Doors (`IfcDoor`)
- Room name in `LongName`
- Optional room number in `Name`

abstractBIM derives walls, slabs, and quantities from correctly modelled spaces and openings. Model interior spaces as volumes from the top of the finished floor to the underside of the structural ceiling.

For **QAS-COORD**, the same elements also require:

- Named spatial structure (`IfcProject`, `IfcSite`, `IfcBuilding`, `IfcBuildingStorey`)
- IFC entity and `PredefinedType` on spaces, windows, and doors
- The entity `Pset_*Common` properties used here (`Reference` and `IsExternal` on spaces, windows, and doors, `Status` on windows and doors, plus `ThermalTransmittance` on windows)

Existing versus new work is expressed through `Status` (`NEW`, `EXISTING`, `DEMOLISH`, `TEMPORARY`) on windows and doors. `Pset_SpaceCommon` has no `Status` property, so spaces carry no element status.

## Phases

Attributes are requested in SIA design phases `31`, `32`, and `33`. The phase catalogue also lists the other SIA codes so projects can extend later.

## Schema

Entities follow the [pragmaticBIM Elementplan schema](https://github.com/pragmaticBIM/elementplan-data-schema). IDs use the `pragmaticbim:` prefix.

## Syncing from add-ons

This free master is a published copy. The source of truth lives in `elementplan_pragmaticbim_swiss_data_add_ons`. Refresh entity YAML from there with:

```bash
python scripts/sync_free_from_addons.py
```

`project.yaml`, this README, `LICENSE`, and `.github/` are left unchanged.
