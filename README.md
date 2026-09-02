# Swiss Starter Elementplan

Public Swiss master template for [pragmaticBIM Elementplan](https://pragmaticbim.ch).

## Problem

BIM requirements usually arrive as wishlists: long Excel sheets and 300-page manuals that nobody can check against a model. Every project reinvents the list, modelers guess which parameters matter, and owners cannot verify what they ordered.

## Solution

This repository is a **starting Elementplan** you can read, fork, or copy into a [pragmaticBIM](https://pragmaticbim.ch) project. Requirements are treated like code: goal levels activate workflows, elements carry IFC entities, attributes, and allowed values, and the same source becomes contract Excel, PDF reports, and machine-readable IDS.

Configure intensity per project goal instead of ticking a use-case checklist. Only order data with a clear benefit. See the [visual tour](https://pragmaticbim.ch/en/how-to/elementplan-visual-tour) for how owners and BIM managers use the same artifact end to end.

Open it in the [Elementplan editor](https://elementplan.pragmaticbim.ch).

## What is in this template

- **7 project goals** — cost/budget sensitivity, fit-out standard, sustainability, quality assurance, operations and handover focus, schedule criticality, and how the project deals with existing structures
- **40+ workflows** — mapped to those goals, following the [abstract use case classification](https://schema.pragmaticbim.ch/classification/usecase.html) (ordering, design, construction, handover, operation, quality assurance)
- **~80 elements** — architecture, structure, and MEP, each with IFC entity, attributes, property sets, allowed values, and SIA phases
- **No Teilmodelle** — model split is project-specific in the Information Delivery Plan

Several workflows lean on [abstractBIM](https://www.abstractbim.com/), which derives walls, slabs, and quantities from correctly modelled spaces and openings.

This is a starting point, not a Swiss standard. It does not replace KBOB or federal authority templates. If you find a mistake, open an issue.

## Schema

Entities follow the [pragmaticBIM Elementplan schema](https://github.com/pragmaticBIM/elementplan-data-schema). IDs use the `pragmaticbim:` prefix.
