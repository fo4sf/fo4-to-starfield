# Playtest issues (the owner's "look" reports)

Each row: what the owner said, the snapshot (`scripts/game/snapshot.ps1`: screen, bridge position and cell, Papyrus
tail; nothing typed into the game), what the build's own records say, and the next step. Build under test:
`terrain_core64f` + the pinned interior build `FO4Port.esm` (integ_1011).

| # | When / where | Owner | Evidence | Cause | Next |
|---|---|---|---|---|---|
| 1 | 16 Oct 10:35, Vault 111 (FO4Port_Vault111Cryo, cell 020011F3, pos -3.83 -7.44 0.01) | "These doors don't work" | ![](../media/playtest/1016-01-vault111-door.jpg) facing `V111Door01b` (001977) | **verified** (manifest): 10 FO4 door bases, the Vault 111 doors among them, are converted with `door_not_opening: open animation not ported: passable` (placed as statics without collision so the player walks through); only 29 hinged door bases are rigged and open | Port the vault door animations (slide / cog) or rig them with a matching Starfield sliding-door graph; meanwhile walk through |
| 2 | 16 Oct 10:36, Vault 111 (same cell, pos 6.20 38.97 -1.81) | "This table doesn't show up" | ![](../media/playtest/1016-02-vault111-table.jpg) the leg frames of `NpcTableVaultSit02` (0AB570, 0AB56F; model `SetDressing\Vault\Vault_Table_02.nif`) render, the table tops do not | **supported hypothesis**: the converted NIF has one shape (`shapes 1`, no fallback material) and its collision converted (`fo4-native`, 1 body); the top's triangles are missing or culled in the converted geometry, not the reference | Owner check: jump onto where the top should be (collision there = a render-only loss); converter check: FO4 source triangle count vs the converted `.mesh`, normals/winding of the top faces |
