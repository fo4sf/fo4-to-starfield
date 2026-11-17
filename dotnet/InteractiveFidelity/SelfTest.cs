using System.Text.Json;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Noggog;
using F4 = Mutagen.Bethesda.Fallout4;
using SF = Mutagen.Bethesda.Starfield;
using SfActivator = Mutagen.Bethesda.Starfield.Activator;
using F4Activator = Mutagen.Bethesda.Fallout4.Activator;

public static class SelfTest
{
    private static void Require(bool ok, string msg)
    {
        if (!ok) throw new InvalidOperationException("selftest failed: " + msg);
    }

    public static int Run(string scratchDir)
    {
        var work = Path.Combine(Path.GetFullPath(scratchDir), "ifid-selftest-" + Guid.NewGuid().ToString("N"));
        Directory.CreateDirectory(work);
        try
        {
            var fo4Path = Path.Combine(work, "Fallout4.esm");
            var sfPath = Path.Combine(work, "Starfield.esm");
            var corePath = Path.Combine(work, "FO4TerrainCore.esm");
            var coreIdsPath = Path.Combine(work, "core_formids.json");
            var portPath = Path.Combine(work, "FO4Port.esm");
            var portIdsPath = Path.Combine(work, "port_formids.json");
            var outDir = Path.Combine(work, "out");

            // 1. Build synthetic Starfield.esm with vanilla marker/door bases & LinkCustom02.
            var sfKey = OverlayBuilder.SfModKey;
            var sfMod = new SF.StarfieldMod(sfKey, SF.StarfieldRelease.Starfield);
            sfMod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
            sfMod.Statics.Add(new SF.Static(OverlayBuilder.EnableMarkerBase, SF.StarfieldRelease.Starfield) { EditorID = "EnableMarker" });
            sfMod.Statics.Add(new SF.Static(OverlayBuilder.XMarkerBase, SF.StarfieldRelease.Starfield) { EditorID = "XMarker" });
            sfMod.Statics.Add(new SF.Static(OverlayBuilder.XMarkerHeadingBase, SF.StarfieldRelease.Starfield) { EditorID = "XMarkerHeading" });
            sfMod.Statics.Add(new SF.Static(OverlayBuilder.LightBoxBase, SF.StarfieldRelease.Starfield) { EditorID = "LightBox" });
            sfMod.Doors.Add(new SF.Door(OverlayBuilder.AutoloadDoorCaveBase, SF.StarfieldRelease.Starfield)
            {
                EditorID = "AutoloadDoor_Cave",
                Flags = SF.Door.Flag.Automatic,
            });
            sfMod.Keywords.Add(new SF.Keyword(OverlayBuilder.LegacyLinkCustom02, SF.StarfieldRelease.Starfield) { EditorID = "LinkCustom02" });
            sfMod.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

            // 2. Build synthetic Fallout4.esm (one interior cell 0x001000 SynthInt01 + Commonwealth worldspace 0x00003C with grid (-10, 11)).
            var fo4Key = ModKey.FromNameAndExtension("Fallout4.esm");
            FormKey Fk4(uint id) => new(fo4Key, id);
            var fo4Mod = new F4.Fallout4Mod(fo4Key, F4.Fallout4Release.Fallout4);
            fo4Mod.ModHeader.Flags |= F4.Fallout4ModHeader.HeaderFlag.Master;

            var f4EnableMarker = new F4.Static(Fk4(0x00001F), F4.Fallout4Release.Fallout4) { EditorID = "EnableMarker" };
            var f4Wall = new F4.Static(Fk4(0x000800), F4.Fallout4Release.Fallout4) { EditorID = "SynthWall" };
            var f4Door = new F4.Door(Fk4(0x000801), F4.Fallout4Release.Fallout4) { EditorID = "SynthDoor" };
            var f4AutoDoor = new F4.Door(Fk4(0x01ED77), F4.Fallout4Release.Fallout4) { EditorID = "AutoloadDoor", Flags = F4.Door.Flag.Automatic };
            var f4NoTextDoor = new F4.Door(Fk4(0x062624), F4.Fallout4Release.Fallout4) { EditorID = "AutoloadDoorNoText", Flags = F4.Door.Flag.Automatic | F4.Door.Flag.DoNotOpenInCombatSearch };
            var f4Cont = new F4.Container(Fk4(0x000802), F4.Fallout4Release.Fallout4) { EditorID = "SynthCont" };
            var f4Term = new F4.Terminal(Fk4(0x000803), F4.Fallout4Release.Fallout4) { EditorID = "SynthTerm" };
            var f4Acti = new F4Activator(Fk4(0x000804), F4.Fallout4Release.Fallout4) { EditorID = "SynthButton" };
            var f4Key = new F4.Key(Fk4(0x000805), F4.Fallout4Release.Fallout4) { EditorID = "SynthKey" };
            var f4UnmappedKey = new F4.Key(Fk4(0x000806), F4.Fallout4Release.Fallout4) { EditorID = "SynthUnmappedKey" };
            var f4Kw = new F4.Keyword(Fk4(0x000807), F4.Fallout4Release.Fallout4)
            {
                EditorID = "SynthGenericKw",
                Type = F4.Keyword.TypeEnum.None,
                Name = "MustNotCopyText",
                Notes = "MustNotCopyNotes",
            };
            var f4LodKw = new F4.Keyword(Fk4(0x195411), F4.Fallout4Release.Fallout4) { EditorID = "MultirefLOD", Type = F4.Keyword.TypeEnum.None };
            fo4Mod.Statics.Add(f4EnableMarker); fo4Mod.Statics.Add(f4Wall);
            fo4Mod.Doors.Add(f4Door); fo4Mod.Doors.Add(f4AutoDoor); fo4Mod.Doors.Add(f4NoTextDoor);
            fo4Mod.Containers.Add(f4Cont); fo4Mod.Terminals.Add(f4Term); fo4Mod.Activators.Add(f4Acti);
            fo4Mod.Keys.Add(f4Key); fo4Mod.Keys.Add(f4UnmappedKey);
            fo4Mod.Keywords.Add(f4Kw); fo4Mod.Keywords.Add(f4LodKw);

            // Interior cell 0x001000 SynthInt01
            var f4IntCell = new F4.Cell(Fk4(0x001000), F4.Fallout4Release.Fallout4) { EditorID = "SynthInt01", Flags = F4.Cell.Flag.IsInteriorCell };
            // 0x001100: EnableMarker (unplaced in port; recreated by overlay)
            var rIntMarker = new F4.PlacedObject(Fk4(0x001100), F4.Fallout4Release.Fallout4) { Position = new P3Float(70, 0, 0) };
            rIntMarker.Base.SetTo(f4EnableMarker.FormKey); rIntMarker.MajorRecordFlagsRaw |= 0x400;
            f4IntCell.Persistent.Add(rIntMarker);
            // 0x001101: Wall with XESP opposite(0x01) + popin(0x02) -> rIntMarker, and XLKR -> 0x001102 + dangling 0x00DEAD + MultirefLOD
            var rIntWall1 = new F4.PlacedObject(Fk4(0x001101), F4.Fallout4Release.Fallout4) { Position = new P3Float(140, 0, 0) };
            rIntWall1.Base.SetTo(f4Wall.FormKey);
            rIntWall1.EnableParent = new F4.EnableParent { Flags = (F4.EnableParent.Flag)3u };
            rIntWall1.EnableParent.Reference.SetTo(rIntMarker.FormKey);
            var lr1 = new F4.LinkedReferences(); lr1.KeywordOrReference.SetTo(f4Kw.FormKey); lr1.Reference.SetTo(Fk4(0x001102));
            var lr2 = new F4.LinkedReferences(); lr2.KeywordOrReference.SetTo(f4LodKw.FormKey); lr2.Reference.SetTo(Fk4(0x001102));
            var lr3 = new F4.LinkedReferences(); lr3.KeywordOrReference.SetTo(f4Kw.FormKey); lr3.Reference.SetTo(Fk4(0x00DEAD));
            rIntWall1.LinkedReferences.Add(lr1); rIntWall1.LinkedReferences.Add(lr2); rIntWall1.LinkedReferences.Add(lr3);
            f4IntCell.Temporary.Add(rIntWall1);

            // 0x001199: Unplaced non-marker controller (enabled) + 0x001102: Wall with XESP opposite -> 0x001199 (folds 0x800!)
            var rUnplacedCtrl = new F4.PlacedObject(Fk4(0x001199), F4.Fallout4Release.Fallout4) { Position = new P3Float(0, 0, 0) };
            rUnplacedCtrl.Base.SetTo(f4Acti.FormKey);
            f4IntCell.Temporary.Add(rUnplacedCtrl);
            var rIntWall2 = new F4.PlacedObject(Fk4(0x001102), F4.Fallout4Release.Fallout4) { Position = new P3Float(210, 0, 0) };
            rIntWall2.Base.SetTo(f4Wall.FormKey);
            rIntWall2.EnableParent = new F4.EnableParent { Flags = (F4.EnableParent.Flag)1u };
            rIntWall2.EnableParent.Reference.SetTo(rUnplacedCtrl.FormKey);
            f4IntCell.Temporary.Add(rIntWall2);

            // 0x001103: Door with mapped KEYM lock (50, Leveled) + XAPR ParentActivateOnly driven by 0x001106 (delay 0.75)
            var rIntDoor = new F4.PlacedObject(Fk4(0x001103), F4.Fallout4Release.Fallout4) { Position = new P3Float(280, 0, 0) };
            rIntDoor.Base.SetTo(f4Door.FormKey);
            rIntDoor.Lock = new F4.LockData { Level = F4.LockLevel.Advanced, Flags = F4.LockData.Flag.LeveledLock };
            rIntDoor.Lock.Key.SetTo(f4Key.FormKey);
            rIntDoor.ActivateParents = new F4.ActivateParents { Flags = F4.ActivateParents.Flag.ParentActivateOnly };
            var ap1 = new F4.ActivateParent { Delay = 0.75f }; ap1.Reference.SetTo(Fk4(0x001106));
            rIntDoor.ActivateParents.Parents.Add(ap1);
            f4IntCell.Temporary.Add(rIntDoor);

            // 0x001104: Door with RequiresKey(255) + unmapped key -> must NOT write XLOC; also second XAPR child of 0x001106 (delay 0.0)
            var rIntDoorUnopenable = new F4.PlacedObject(Fk4(0x001104), F4.Fallout4Release.Fallout4) { Position = new P3Float(350, 0, 0) };
            rIntDoorUnopenable.Base.SetTo(f4Door.FormKey);
            rIntDoorUnopenable.Lock = new F4.LockData { Level = F4.LockLevel.RequiresKey };
            rIntDoorUnopenable.Lock.Key.SetTo(f4UnmappedKey.FormKey);
            rIntDoorUnopenable.ActivateParents = new F4.ActivateParents { Flags = 0 };
            var ap2 = new F4.ActivateParent { Delay = 0f }; ap2.Reference.SetTo(Fk4(0x001106));
            rIntDoorUnopenable.ActivateParents.Parents.Add(ap2);
            f4IntCell.Temporary.Add(rIntDoorUnopenable);

            // 0x001105: Terminal with Expert(75) lock + unmapped key -> pickable fallback (Key=Null)
            var rIntTerm = new F4.PlacedObject(Fk4(0x001105), F4.Fallout4Release.Fallout4) { Position = new P3Float(420, 0, 0) };
            rIntTerm.Base.SetTo(f4Term.FormKey);
            rIntTerm.Lock = new F4.LockData { Level = F4.LockLevel.Expert };
            rIntTerm.Lock.Key.SetTo(f4UnmappedKey.FormKey);
            f4IntCell.Temporary.Add(rIntTerm);

            // 0x001106: Switch driving both 0x001103 and 0x001104
            var rIntBtn = new F4.PlacedObject(Fk4(0x001106), F4.Fallout4Release.Fallout4) { Position = new P3Float(490, 0, 0) };
            rIntBtn.Base.SetTo(f4Acti.FormKey);
            f4IntCell.Temporary.Add(rIntBtn);

            // 0x001107: Interior AutoloadDoor <-> 0x002107 exterior AutoloadDoor; plus 0x001108 AutoloadDoorNoText (must NOT recreate!)
            var rIntAuto = new F4.PlacedObject(Fk4(0x001107), F4.Fallout4Release.Fallout4) { Position = new P3Float(-70, 140, 0), Scale = 0.9f };
            rIntAuto.Base.SetTo(f4AutoDoor.FormKey); rIntAuto.MajorRecordFlagsRaw |= 0x400;
            rIntAuto.TeleportDestination = new F4.TeleportDestination { Position = new P3Float(-69650, 77350, 6980), Rotation = new P3Float(0, 0, 1.2f) };
            rIntAuto.TeleportDestination.Door.SetTo(Fk4(0x002107));
            f4IntCell.Persistent.Add(rIntAuto);

            var rIntNoText = new F4.PlacedObject(Fk4(0x001108), F4.Fallout4Release.Fallout4) { Position = new P3Float(0, 0, 1400) };
            rIntNoText.Base.SetTo(f4NoTextDoor.FormKey); rIntNoText.MajorRecordFlagsRaw |= 0x400;
            rIntNoText.TeleportDestination = new F4.TeleportDestination { Position = new P3Float(-69650, 77350, 6980) };
            rIntNoText.TeleportDestination.Door.SetTo(Fk4(0x002108));
            f4IntCell.Persistent.Add(rIntNoText);

            var f4Blk = new F4.CellBlock { BlockNumber = 0, GroupType = F4.GroupTypeEnum.InteriorCellBlock };
            var f4Sub = new F4.CellSubBlock { BlockNumber = 0, GroupType = F4.GroupTypeEnum.InteriorCellSubBlock };
            f4Sub.Cells.Add(f4IntCell); f4Blk.SubBlocks.Add(f4Sub); fo4Mod.Cells.Records.Add(f4Blk);

            // FO4 Commonwealth worldspace 0x00003C at Starfield grid (-10, 11) => FO4 x in [-70000..-63000), y in [77000..84000)
            var f4World = new F4.Worldspace(Fk4(0x00003C), F4.Fallout4Release.Fallout4) { EditorID = "Commonwealth" };
            f4World.TopCell = new F4.Cell(Fk4(0x018AA2), F4.Fallout4Release.Fallout4);
            var rExtAuto = new F4.PlacedObject(Fk4(0x002107), F4.Fallout4Release.Fallout4) { Position = new P3Float(-69650, 77630, 6930), Scale = 0.25f };
            rExtAuto.Base.SetTo(f4AutoDoor.FormKey); rExtAuto.MajorRecordFlagsRaw |= 0x400;
            rExtAuto.TeleportDestination = new F4.TeleportDestination { Position = new P3Float(0, -420, 0), Rotation = new P3Float(0, 0, 2.7f) };
            rExtAuto.TeleportDestination.Door.SetTo(Fk4(0x001107));
            f4World.TopCell.Persistent.Add(rExtAuto);

            var rExtNoText = new F4.PlacedObject(Fk4(0x002108), F4.Fallout4Release.Fallout4) { Position = new P3Float(-69650, 77630, 6930) };
            rExtNoText.Base.SetTo(f4NoTextDoor.FormKey); rExtNoText.MajorRecordFlagsRaw |= 0x400;
            rExtNoText.TeleportDestination = new F4.TeleportDestination { Position = new P3Float(0, 0, 1400) };
            rExtNoText.TeleportDestination.Door.SetTo(Fk4(0x001108));
            f4World.TopCell.Persistent.Add(rExtNoText);

            var rExtMarker = new F4.PlacedObject(Fk4(0x002100), F4.Fallout4Release.Fallout4) { Position = new P3Float(-69500, 77500, 6900) };
            rExtMarker.Base.SetTo(f4EnableMarker.FormKey); rExtMarker.MajorRecordFlagsRaw |= 0x400;
            f4World.TopCell.Persistent.Add(rExtMarker);

            var f4ExtCell = new F4.Cell(Fk4(0x002000), F4.Fallout4Release.Fallout4) { Grid = new F4.CellGrid { Point = new P2Int(-17, 18) } };
            var rExtCont = new F4.PlacedObject(Fk4(0x002101), F4.Fallout4Release.Fallout4) { Position = new P3Float(-69440, 77560, 6900) };
            rExtCont.Base.SetTo(f4Cont.FormKey);
            rExtCont.EnableParent = new F4.EnableParent { Flags = (F4.EnableParent.Flag)1u };
            rExtCont.EnableParent.Reference.SetTo(rExtMarker.FormKey);
            rExtCont.Lock = new F4.LockData { Level = F4.LockLevel.Novice25 };
            f4ExtCell.Temporary.Add(rExtCont);

            var rExtBtn = new F4.PlacedObject(Fk4(0x002102), F4.Fallout4Release.Fallout4) { Position = new P3Float(-69370, 77560, 6900) };
            rExtBtn.Base.SetTo(f4Acti.FormKey);
            f4ExtCell.Temporary.Add(rExtBtn);

            var rExtGarage = new F4.PlacedObject(Fk4(0x002103), F4.Fallout4Release.Fallout4) { Position = new P3Float(-69300, 77560, 6900) };
            rExtGarage.Base.SetTo(f4Door.FormKey);
            rExtGarage.ActivateParents = new F4.ActivateParents { Flags = F4.ActivateParents.Flag.ParentActivateOnly };
            var apExt = new F4.ActivateParent { Delay = 0.25f }; apExt.Reference.SetTo(rExtBtn.FormKey);
            rExtGarage.ActivateParents.Parents.Add(apExt);
            f4ExtCell.Temporary.Add(rExtGarage);

            var wb4 = new F4.WorldspaceBlock { BlockNumberX = -1, BlockNumberY = 0, GroupType = F4.GroupTypeEnum.ExteriorCellBlock };
            var ws4 = new F4.WorldspaceSubBlock { BlockNumberX = -3, BlockNumberY = 2, GroupType = F4.GroupTypeEnum.ExteriorCellSubBlock };
            ws4.Items.Add(f4ExtCell); wb4.Items.Add(ws4); f4World.SubCells.Add(wb4);
            fo4Mod.Worldspaces.Add(f4World);
            fo4Mod.BeginWrite.ToPath(fo4Path).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();

            // 3. Build synthetic FO4Port.esm + port_formids.json (pre-fidelity baseline: XESP/XLOC/XLKR/XAPR stripped, markers unplaced).
            var portKey = ModKey.FromNameAndExtension("FO4Port.esm");
            FormKey FkP(uint id) => new(portKey, id);
            var portMod = new SF.StarfieldMod(portKey, SF.StarfieldRelease.Starfield);
            portMod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
            var pWall = new SF.Static(FkP(0x000800), SF.StarfieldRelease.Starfield) { EditorID = "FO4Port_Wall" };
            var pDoor = new SF.Door(FkP(0x000801), SF.StarfieldRelease.Starfield) { EditorID = "FO4Port_Door" };
            var pTerm = new SF.Terminal(FkP(0x000802), SF.StarfieldRelease.Starfield) { EditorID = "FO4Port_Term" };
            var pActi = new SfActivator(FkP(0x000803), SF.StarfieldRelease.Starfield) { EditorID = "FO4Port_Btn" };
            var pKey = new SF.Key(FkP(0x000804), SF.StarfieldRelease.Starfield) { EditorID = "FO4Port_Key", Name = "Key" };
            portMod.Statics.Add(pWall); portMod.Doors.Add(pDoor); portMod.Terminals.Add(pTerm); portMod.Activators.Add(pActi); portMod.Keys.Add(pKey);

            var pCell = new SF.Cell(FkP(0x000810), SF.StarfieldRelease.Starfield) { EditorID = "FO4Port_SynthInt01", Flags = SF.Cell.Flag.IsInteriorCell };
            SF.PlacedObject AddPortRef(uint id, FormKey b, float x)
            {
                var o = new SF.PlacedObject(FkP(id), SF.StarfieldRelease.Starfield) { Position = new P3Float(x, 0, 0) };
                o.Base.SetTo(b); pCell.Temporary.Add(o); return o;
            }
            AddPortRef(0x000811, pWall.FormKey, 2);
            AddPortRef(0x000812, pWall.FormKey, 3);
            AddPortRef(0x000813, pDoor.FormKey, 4);
            AddPortRef(0x000814, pDoor.FormKey, 5);
            AddPortRef(0x000815, pTerm.FormKey, 6);
            AddPortRef(0x000816, pActi.FormKey, 7);

            // Add one NavigationMesh in pCell so navmesh_door_triangles remapping to recreated 001107 AutoloadDoor is tested.
            var pNav = new SF.NavigationMesh(FkP(0x000820), SF.StarfieldRelease.Starfield)
            {
                NavmeshGeometry = new SF.NavmeshGeometry { NavmeshVersion = 17, CrcHash = 0xA5E9A03C, Unknown3 = 0x0008000C },
                PreCutMapEntries = new ExtendedList<SF.PreCutMapEntry>(),
                FormVersion = 581,
            };
            pNav.NavmeshGeometry.Vertices.Add(new SF.NavmeshVertex { Point = new P3Float(0, 0, 0) });
            pNav.NavmeshGeometry.Vertices.Add(new SF.NavmeshVertex { Point = new P3Float(1, 0, 0) });
            pNav.NavmeshGeometry.Vertices.Add(new SF.NavmeshVertex { Point = new P3Float(0, 1, 0) });
            pNav.NavmeshGeometry.Triangles.Add(new SF.NavmeshTriangle { Vertices = new P3Int16(0, 1, 2), EdgeLink_0_1 = -1, EdgeLink_1_2 = -1, EdgeLink_2_0 = -1 });
            pCell.NavigationMeshes.Add(pNav);

            var pb = new SF.CellBlock { BlockNumber = 6, GroupType = SF.GroupTypeEnum.InteriorCellBlock };
            var ps = new SF.CellSubBlock { BlockNumber = 7, GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
            ps.Cells.Add(pCell); pb.SubBlocks.Add(ps); portMod.Cells.Records.Add(pb);
            portMod.BeginWrite.ToPath(portPath).WithLoadOrder(sfKey).WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();

            File.WriteAllText(portIdsPath, JsonSerializer.Serialize(new Dictionary<string, uint>
            {
                ["CELL:FO4Port_SynthInt01"] = 0x000810,
                ["KEYM:000805:Fallout4.esm"] = 0x000804,
                ["REFR:FO4Port_SynthInt01:001101:Fallout4.esm"] = 0x000811,
                ["REFR:FO4Port_SynthInt01:001102:Fallout4.esm"] = 0x000812,
                ["REFR:FO4Port_SynthInt01:001103:Fallout4.esm"] = 0x000813,
                ["REFR:FO4Port_SynthInt01:001104:Fallout4.esm"] = 0x000814,
                ["REFR:FO4Port_SynthInt01:001105:Fallout4.esm"] = 0x000815,
                ["REFR:FO4Port_SynthInt01:001106:Fallout4.esm"] = 0x000816,
            }));

            // 4. Build synthetic FO4TerrainCore.esm + core_formids.json with legacy DefaultActivateLinkedRefOnActivate on 002102.
            var coreKey = ModKey.FromNameAndExtension("FO4TerrainCore.esm");
            FormKey FkC(uint id) => new(coreKey, id);
            var coreMod = new SF.StarfieldMod(coreKey, SF.StarfieldRelease.Starfield);
            coreMod.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
            var cCont = new SF.Container(FkC(0x000800), SF.StarfieldRelease.Starfield) { EditorID = "FO4Core_Cont", Items = new ExtendedList<SF.ContainerEntry>() };
            var cActi = new SfActivator(FkC(0x000801), SF.StarfieldRelease.Starfield) { EditorID = "FO4Core_Btn" };
            var cDoor = new SF.Door(FkC(0x000802), SF.StarfieldRelease.Starfield) { EditorID = "FO4Core_GarageDoor" };
            coreMod.Containers.Add(cCont); coreMod.Activators.Add(cActi); coreMod.Doors.Add(cDoor);

            var cWorld = new SF.Worldspace(FkC(0x000803), SF.StarfieldRelease.Starfield) { EditorID = "FO4Core_Commonwealth" };
            cWorld.TopCell = new SF.Cell(FkC(0x001805), SF.StarfieldRelease.Starfield) { Flags = SF.Cell.Flag.HasWater };
            var anchor = new SF.PlacedObject(FkC(0x000807), SF.StarfieldRelease.Starfield) { Position = new P3Float(0, 0, 0) };
            anchor.Base.SetTo(OverlayBuilder.XMarkerBase); anchor.MajorRecordFlagsRaw |= 0x400;
            cWorld.TopCell.Persistent.Add(anchor);

            var cExt = new SF.Cell(FkC(0x000DAF), SF.StarfieldRelease.Starfield) { Grid = new SF.CellGrid { Point = new P2Int(-10, 11) } };
            var crCont = new SF.PlacedObject(FkC(0x000901), SF.StarfieldRelease.Starfield) { Position = new P3Float(-992f, 1108f, 98.57f) };
            crCont.Base.SetTo(cCont.FormKey); cExt.Temporary.Add(crCont);

            var crGarage = new SF.PlacedObject(FkC(0x000903), SF.StarfieldRelease.Starfield) { Position = new P3Float(-990f, 1108f, 98.57f) };
            crGarage.Base.SetTo(cDoor.FormKey); cExt.Temporary.Add(crGarage);

            // Legacy DefaultActivateLinkedRefOnActivate on crBtn -> must be cleanly upgraded to FO4SF_ActivateChain without duplicate!
            var crBtn = new SF.PlacedObject(FkC(0x000902), SF.StarfieldRelease.Starfield) { Position = new P3Float(-991f, 1108f, 98.57f) };
            crBtn.Base.SetTo(cActi.FormKey);
            crBtn.VirtualMachineAdapter = new SF.VirtualMachineAdapter { Version = 6, ObjectFormat = 2 };
            crBtn.VirtualMachineAdapter.Scripts.Add(new SF.ScriptEntry { Name = OverlayBuilder.LegacySingleScriptName });
            var legacyLink = new SF.LinkedReferences();
            legacyLink.KeywordOrReference.SetTo(OverlayBuilder.LegacyLinkCustom02);
            legacyLink.Reference.SetTo(crGarage.FormKey);
            crBtn.LinkedReferences.Add(legacyLink);
            cExt.Temporary.Add(crBtn);

            var cwb = new SF.WorldspaceBlock { BlockNumberX = -1, BlockNumberY = 0, GroupType = SF.GroupTypeEnum.ExteriorCellBlock };
            var cws = new SF.WorldspaceSubBlock { BlockNumberX = -2, BlockNumberY = 1, GroupType = SF.GroupTypeEnum.ExteriorCellSubBlock };
            cws.Items.Add(cExt); cwb.Items.Add(cws); cWorld.SubCells.Add(cwb);
            coreMod.Worldspaces.Add(cWorld);
            coreMod.BeginWrite.ToPath(corePath).WithLoadOrder(sfKey).WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();

            File.WriteAllText(coreIdsPath, JsonSerializer.Serialize(new
            {
                plugin = "FO4TerrainCore.esm",
                world = "FO4Core_Commonwealth",
                refs = new Dictionary<string, string> { ["002103:Fallout4.esm"] = "000903" },
                containers = new Dictionary<string, object> { ["002101:Fallout4.esm"] = new { @base = "000800", @ref = "000901" } },
                activators = new Dictionary<string, object> { ["002102:Fallout4.esm"] = new { @base = "000801", @ref = "000902" } },
            }));

            // 5. Run OverlayBuilder.Run + FidelityCheck.Run on the synthetic inputs.
            var paramsPath = Path.Combine(work, "params.json");
            File.WriteAllText(paramsPath, JsonSerializer.Serialize(new
            {
                plugin = "FO4SFInteractiveFidelity.esm",
                fo4_esm = fo4Path,
                starfield_esm = sfPath,
                core_esm = corePath,
                core_formids = coreIdsPath,
                port_esm = portPath,
                port_formids = portIdsPath,
                out_dir = outDir,
                interior_cells = new[] { "001000" },
                exterior_cells = new[] { new[] { -10, 11 } },
                navmesh_door_triangles = new[]
                {
                    new { cell = "000810:FO4Port.esm", navmesh = "000820:FO4Port.esm", fo4_door = "001107:Fallout4.esm", triangle = 0 }
                }
            }));

            Require(OverlayBuilder.Run(paramsPath) == 0, "OverlayBuilder.Run failed");
            var builtPlugin = Path.Combine(outDir, "FO4SFInteractiveFidelity.esm");
            var checkReportPath = Path.Combine(outDir, "check_report.json");
            Require(FidelityCheck.Run(builtPlugin, sfPath, corePath, portPath, null, checkReportPath) == 0,
                "FidelityCheck failed on valid overlay build");

            var buildRep = JsonSerializer.Deserialize<OverlayBuildReport>(File.ReadAllText(Path.Combine(outDir, "fidelity_build_report.json")))!;
            Require(buildRep.XespWritten == 2 && buildRep.XespOppositeWritten == 2 && buildRep.XespPopInWritten == 1 &&
                    buildRep.XespFoldedInitialState == 1, "unexpected XESP counts in build report");
            Require(buildRep.XlocWritten == 3 && buildRep.XlocKeyMapped == 1 && buildRep.XlocUnmappedKeyFallback == 1 &&
                    buildRep.XlocUnopenableRequiresKeySkipped == 1, "unexpected XLOC counts in build report");
            Require(buildRep.XlkrWritten == 1 && buildRep.XlkrDanglingSkipped == 1 && buildRep.XlkrMultirefLodSkipped == 1,
                "unexpected XLKR counts in build report");
            Require(buildRep.XaprParentsWired == 2 && buildRep.XaprEdgesWired == 3 && buildRep.XaprDelaysPreserved == 2 &&
                    buildRep.XaprParentActivateOnlyApplied == 2 && buildRep.XaprUpgradedLegacySingleLinks == 1,
                "unexpected XAPR counts in build report");
            Require(buildRep.CreatedAutoloadDoors == 2 && buildRep.XtelCreatedLinks == 2 && buildRep.NavmeshDoorTrianglesVerified == 1,
                "unexpected XTEL / AutoloadDoor / DoorTriangle counts (or AutoloadDoorNoText was wrongly recreated)");

            // Repeat build must keep fidelity_formids.json identical.
            var formidsBefore = File.ReadAllText(Path.Combine(outDir, "fidelity_formids.json"));
            Require(OverlayBuilder.Run(paramsPath) == 0, "repeat OverlayBuilder.Run failed");
            Require(File.ReadAllText(Path.Combine(outDir, "fidelity_formids.json")) == formidsBefore, "repeat build changed fidelity_formids.json");

            // 6. Negative mutation tests: FidelityCheck MUST reject every bad mutation (exit 1).
            var masters = new[] { sfKey, coreKey, portKey };
            SF.StarfieldMod LoadMutableCopy() =>
                SF.StarfieldMod.CreateFromBinary(builtPlugin, SF.StarfieldRelease.Starfield,
                    new BinaryReadParameters { MasterFlagsLookup = OverlayBuilder.MasterStyles(masters) });

            void ExpectCheckFailure(string label, Action<SF.StarfieldMod> mutate)
            {
                var bad = LoadMutableCopy();
                mutate(bad);
                var badDir = Path.Combine(work, $"bad_{label}");
                Directory.CreateDirectory(badDir);
                var badPath = Path.Combine(badDir, "FO4SFInteractiveFidelity.esm");
                bad.BeginWrite.ToPath(badPath)
                    .WithLoadOrder(masters)
                    .WithKnownMasters(masters.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray())
                    .Write();
                var sw = new StringWriter();
                var origOut = Console.Out;
                int rc;
                try { Console.SetOut(sw); rc = FidelityCheck.Run(badPath, sfPath, corePath, portPath); }
                finally { Console.SetOut(origOut); }
                Require(rc == 1, $"FidelityCheck accepted invalid mutation '{label}':\n{sw}");
            }

            // (a) Exterior grid cell Persistent child (#712 crash guard)
            ExpectCheckFailure("ext_grid_persistent", m =>
            {
                var ec = m.Worldspaces.First().SubCells[0].Items[0].Items[0];
                var rogue = new SF.PlacedObject(new FormKey(m.ModKey, 0x9F0), SF.StarfieldRelease.Starfield);
                rogue.Base.SetTo(OverlayBuilder.XMarkerBase);
                rogue.MajorRecordFlagsRaw |= 0x400;
                ec.Persistent.Add(rogue);
            });

            // (b) Dangling XESP parent
            ExpectCheckFailure("dangling_xesp", m =>
            {
                var r = m.Cells.Records[0].SubBlocks[0].Cells[0].Temporary.OfType<SF.PlacedObject>().First(x => x.EnableParent != null);
                r.EnableParent!.Reference.SetTo(new FormKey(m.ModKey, 0xDEAD));
            });

            // (c) XLOC on a STAT base
            ExpectCheckFailure("xloc_on_stat", m =>
            {
                var r = m.Cells.Records[0].SubBlocks[0].Cells[0].Temporary.OfType<SF.PlacedObject>().First(x => x.Base.FormKey == pWall.FormKey);
                r.Lock = new SF.LockData { Level = SF.LockLevel.Novice25 };
            });

            // (d) RequiresKey (255) lock with null KEYM
            ExpectCheckFailure("requires_key_null", m =>
            {
                var r = m.Cells.Records[0].SubBlocks[0].Cells[0].Temporary.OfType<SF.PlacedObject>().First(x => x.Lock != null);
                r.Lock = new SF.LockData { Level = SF.LockLevel.RequiresKey };
            });

            // (e) Dangling XLKR target
            ExpectCheckFailure("dangling_xlkr", m =>
            {
                var r = m.Cells.Records[0].SubBlocks[0].Cells[0].Temporary.OfType<SF.PlacedObject>().First(x => x.LinkedReferences.Count > 0);
                r.LinkedReferences[0].Reference.SetTo(new FormKey(m.ModKey, 0xDEAD));
            });

            // (f) Negative delay in FO4SF_ActivateChain
            ExpectCheckFailure("negative_xapr_delay", m =>
            {
                var r = m.Cells.Records[0].SubBlocks[0].Cells[0].Temporary.OfType<SF.PlacedObject>()
                    .First(x => x.VirtualMachineAdapter?.Scripts.Any(s => s.Name == OverlayBuilder.ChainScriptName &&
                        s.Properties.Any(p => p.Name == "Delays")) == true);
                var dp = (SF.ScriptFloatListProperty)r.VirtualMachineAdapter!.Scripts.First(s => s.Name == OverlayBuilder.ChainScriptName)
                    .Properties.First(p => p.Name == "Delays");
                dp.Data[0] = -1f;
            });

            // (g) Dangling NAVM DoorTriangle
            ExpectCheckFailure("dangling_door_triangle", m =>
            {
                var nm = m.Cells.Records[0].SubBlocks[0].Cells[0].NavigationMeshes[0];
                nm.NavmeshGeometry!.DoorTriangles[0].Door.SetTo(new FormKey(m.ModKey, 0xDEAD));
            });

            Console.WriteLine("selftest pass");
            return 0;
        }
        finally
        {
            if (Directory.Exists(work))
                Directory.Delete(work, true);
        }
    }
}
