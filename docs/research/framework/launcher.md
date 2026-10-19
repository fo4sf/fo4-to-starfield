# Launcher phase: question framework

Owner: the Launcher thread (Claude-cloud). Started 2026-10-19 17:50Z on the owner's ask (17:41Z) to research modding
communities, tools and precedents and build a framework of questions for the next phases. The Next-phase research
framework thread folds this file into its README; edit requests go through it.
Labels: **verified** (source or measurement named), **supported hypothesis**, **unresolved**. A question is open until
a measured answer or the owner's decision closes it.

Builds on, does not repeat: research/next-phase/launcher-architecture.md, research/next-phase/launcher-gamma-model-and-community-tools.md,
docs/ai/launcher-backbone.md (PR #394: detect, manifest, resumable driver, snapshot and restore, same-ids, mod manifest draft).

## Status
Skeleton. Six research agents are out (precedent installers, the Starfield modding stack, the Fallout 4 source side,
launcher app engineering, distribution and community, build orchestration and load order). Sections fill as they return.

## What we already know (from PR #394 and the PC, verified)
- Same inputs give byte-identical core plugins on one PC (re-stage of v6e, 235 s, IDENTICAL).
- The owner's PC: Fallout 4 from Steam depots 377163/435871/435880 (only Automatron and Wasteland Workshop), Archive2
  and Creation Kit present, SFSE absent; a staged core costs 0.3 to 1 GiB new disk, a mission fold 4.5 GiB.
- Restore through our three installers plus a snapshot works on synthetic installs; not yet on the real one.

## Question areas (to be filled)
1. Sources: which Fallout 4 and Starfield versions, stores and languages we accept, and how we tell them apart
2. Build: time, disk, determinism across PCs, resume, what rebuilds when a converter changes
3. Install and restore: own folder, MO2, Vortex, Creations; keeping the player's Starfield clean
4. Game updates: what breaks when Starfield or Fallout 4 updates, and how the launcher pins or follows versions
5. The launcher app: UI, packaging, signing, antivirus, updates, logs and support bundles
6. Mods on the core: manifests, load order (LOOT), add-on fetching, save compatibility
7. Distribution, legal and community: hosting, licences, Bethesda and Nexus policy, support load
