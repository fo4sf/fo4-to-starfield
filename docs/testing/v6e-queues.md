# The v6e test queues (staged plan; nothing planned on the PC yet)

Claude-cloud (bridge thread), 2026-10-19. The campaign is `scripts/game/campaigns/v6e.json`. It is armed only through
`scripts/game/campaign_arm.py` (#391). Labels: **verified**, **supported**, **unresolved**.

## When
Only after the owner's v6e swap line and their own Red Rocket, Sanctuary and museum test of v6e. Until then nothing
here is planned, armed or run. The walk starts at the Red Rocket arrival, so it stays held (`holds.red_rocket`) until
the owner says that area is safe. It then runs only with `"released": ["red_rocket"]` written in the campaign.

## The queues
Interior queues come first and the walk comes last. Each runs with one launch, stops at the first crash or dead start,
and keeps 43 GB free on D:.

| Queue | Made from | What a PASS shows |
|---|---|---|
| doors_out | the 8 OUT legs of doors_out at least 1500 m from Red Rocket, re-staged on the installed v6e core | each interior door lands within 3 m of its exterior marker |
| stairs_bpl | the 20 BostonPublicLibrary02 stair routes | the player climbs at least 80% of each flight |
| movable | the 11 QASmoke items of movable_control_1013b | converted items move like their vanilla controls |
| walk | Red Rocket to Sanctuary and back, re-planned on the v6e core | the whole route is walked with no fall, block or boundary |

## PC steps, after the swap (the install thread; paths as on Oct 19)
1. Read the load indices: `door_rounds.py order --plugins-txt <Plugins.txt>`. The doors_out plan used core 02 and port 06.
2. doors_out:
   - `door_rounds.py stage --core <the v6e core build folder> --core-plugin <Data\FO4TerrainCore.esm> --port D:\Modding\staging\integ_v6_specmask_doors_c --core-index 02 --port-index 06 --out D:\Modding\staging\rounds_v6e`
   - `door_out_legs.py D:\Modding\staging\rounds_v6e D:\Modding\staging\rounds_v6e_out 1500`
   - `testqueue.py plan-terrain --staging D:\Modding\staging\integ_v6_specmask_doors_c --exp-dir D:\Modding\staging\rounds_v6e_out --out D:\Modding\testqueue_v6e\doors_out --bridge C:\Modding\staging\bridge_t4`
   - Supported: the same 8 doors come back, since compare-ids for v6e against v6c reported identical ids. Re-staging
     checks each door's VMAD in the installed v6e core again rather than trusting that.
3. stairs_bpl: `testqueue.py plan --staging D:\Modding\staging\integ_v6_specmask_doors_c --out D:\Modding\testqueue_v6e\stairs_bpl --cells BostonPublicLibrary02 --kinds stairs --routes-prefix routesfull_ --routes-dir <routes re-planned on this port>`
   - The 1014 routes were planned on 2470f876. With them, a STUCK could be false.
4. movable: `testqueue.py plan-movable --staging D:\Modding\staging\integ_v6_specmask_doors_c --exp-dir C:\Modding\staging\movable_control_1013b --out D:\Modding\testqueue_v6e\movable`
5. walk:
   - `walk_route.py plan --fo4 <Fallout4.esm> --core <the v6e core build folder> --out D:\Modding\staging\walk_v6e`
   - `testqueue.py plan-walk --staging D:\Modding\staging\integ_v6_specmask_doors_c --exp-dir D:\Modding\staging\walk_v6e --install-exp D:\Modding\staging\terrain_core64v6e_l125_mission_wfc10 --plugins FO4TerrainCore.esm,FO4TerrainCore_Mars.esm,FO4ActorRaider.esm,FO4SFMission.esm --bridge C:\Modding\staging\bridge_t4 --out D:\Modding\testqueue_v6e\walk --time-of-day 12`
   - No `--fresh` on any queue: the campaign has one launch, and campaign_arm refuses a fresh test outside the
     first queue's first test.
   - The walk queue's pre-launch re-installs exactly the installed v6e set, so it changes nothing. campaign_arm
     refuses any other experiment or plugin list.
   - Unresolved: the four plugin names here. Copy them from swap_v6e.ps1 before planning. A mismatch is refused, not run.
6. Arm and check, from the campaign checkout `D:\Modding\wt_nightrun` with nothing uncommitted:
   - `campaign_arm.py pin --campaign scripts\game\campaigns\v6e.json --out D:\Modding\testqueue_v6e\v6e.armed.json`
     writes a copy pinned to the checkout's commit (a shipped manifest can not name its own commit, and the checkout
     must stay clean, so the armed copy lives outside it);
   - `campaign_arm.py check --campaign D:\Modding\testqueue_v6e\v6e.armed.json`. It should list the walk as held and
     the rest as OK.
7. Run, with the game closed:
   - stop the crashwatch loop first, never while ProcDump is attached to a live game. Its attach ended every
     short-lived start since Oct 18 with exit 0x54, Steam's "error 84" (supported, docs/ai/test-queue.md);
   - run `campaign_arm.py run --campaign D:\Modding\testqueue_v6e\v6e.armed.json`. Never run a queue with
     `testqueue.py run` directly: only campaign_arm enforces the Red Rocket hold;
   - afterwards, restart crashwatch and put FO4Port back first in the owner's order.
