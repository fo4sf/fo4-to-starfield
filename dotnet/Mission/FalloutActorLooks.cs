// FalloutActorLooks: Round 10 C5 + Round 11 D2 & A2.3 actor looks & spacesuit stripping for FO4SFMission.esm.
//
// 1. Why Preston (0x000801) and the 5 Concord raiders (FO4ActorRaider.esm:0xF04800) wore Starfield spacesuits in 2f:
//    - Preston duplicated Starfield.esm:0x01169C (UC_NA_PapaKatz), leaving SpaceOutfit (SOFT) = Null,
//      UseTemplateActors = 0x6C12 non-zero, and ActorShouldForceHideSpacesuit_AV (0x000B120E) unset (0.0).
//      In Starfield.esm, DFOB 0x001A76BD (DefaultSpaceSuitOutfit_DO) supplies OTFT 0x0016D5E5
//      (Outfit_Spacesuit_DefaultNPC_NoBoostpack_NOTPLAYABLE) whenever a HumanRace NPC has SpaceOutfit = Null,
//      and on MarsPlanetWorld (PNDT 0x0003F59A, non-breathable CO2) CNDF 0x00194ABF + CNDF 0x000BEA53 evaluate TRUE.
//    - FO4ActorRaider.esm:0xF04800 (FO4_LvlRaider) explicitly authored SpaceOutfit (SOFT) = 0x003D094D
//      (Outfit_Spacesuit_Spacer_AssaultOrNoRole) with ActorShouldForceHideSpacesuit_AV unset.
//    -> Passed in candidate-2g: spacesuits and helmets stripped on Preston and all 5 Concord raiders; Preston's
//       converted FO4 Minuteman duster and Starfield chargen face approximation rendered in dialogue (Stills 07 & 08).
//
// 2. Round 11 D2 — Why Preston's hat (0x000985 / ARMA 0x000984) was missing in candidate-2g Stills 07 & 08:
//    - ARMA 0x000984 (FO4_AA_PrestonHat) duplicated Starfield.esm:0x211140 (AA_Clothes_First_Mercenary_01_Hat),
//      whose Male/Female Model subrecords carry MO2F = 0x01 / MO3F = 0x01 (HasFaceBonesModel) + XFLG = 0x01.
//      Because SetWorldModels mutated Model.File in place without replacing the SF.Model wrapper, Starfield's
//      FaceBone actor loader appended "_facebones" and requested "prestongarveyhat_m_facebones.nif" (absent from BA2)
//      instead of "prestongarveyhat_m.nif" (whereas ARMA 0x000981 duplicated AA_Naked_Body 0x012204, which had no
//      MO2F/MO3F flags, so prestongarveyoutfit_m.nif loaded directly).
//    - Fix: SetWorldModels constructs clean SF.Model instances (Flags = null -> zero MO2F/MO3F/XFLG subrecords),
//      aligns hat FirstPersonFlags (BO64) to 0x10 (ARMO) / 0x12 (ARMA) matching companion hat 0x1C8E0A -> 0x25DEEB,
//      and sets 0x68 (BODY | UpperBody | Hands, matching gloved outfits 0x21BBF2 / 0x25E8D4) on 0x981/0x983/0x989/0x98A
//      so HumanRace's default AA_Naked_Hands (0x030580, BO64 = 0x40) no longer draws duplicate bare fingers behind
//      Preston's leather gloves (seen in Still 07).
//
// 3. Round 11 A2.3 + Review #7 — Scoped Concord Raider NPC_ (0x000986 FO4_ConcordRaider) + later raider clones:
//    - Clones FO4ActorRaider.esm:0xF04800 (FO4_LvlRaider) to local FO4SFMission.esm:0x000986 (FO4_ConcordRaider,
//      FormVersion = 581) with FO4_Outfit_ConcordRaider (0x988) + ActorShouldForceHideSpacesuit_AV = 1.0, and rebind-points
//      ONLY Concord's placed raider ACHRs (0x803..0x80F) to 0x000986. FO4ActorRaider.esm:0xF04800 stays untouched
//      (0 foreign NPC_ overrides in FO4SFMission.esm).
//    - Strips 0x003D094D Spacer spacesuit outfits (DOFT = SOFT = 0x988 + ActorShouldForceHideSpacesuit_AV = 1.0) on
//      later-mission FO4_LvlRaider-cloned NPCs in FO4SFMission.esm (0x0A23 FO4_CorvegaBoss, 0x0AD1 FO4_Kellogg,
//      0x0B31 FO4_CourserZ247) so zero NPC_ records in FO4SFMission.esm carry 0x003D094D.

using Mutagen.Bethesda;
using Mutagen.Bethesda.Plugins;
using Mutagen.Bethesda.Plugins.Assets;
using Mutagen.Bethesda.Plugins.Binary.Parameters;
using Mutagen.Bethesda.Plugins.Records;
using Mutagen.Bethesda.Starfield;
using Mutagen.Bethesda.Starfield.Assets;
using Noggog;
using SF = Mutagen.Bethesda.Starfield;

public static class FalloutActorLooks
{
    public static readonly ModKey SfEsm = ModKey.FromFileName("Starfield.esm");

    // Starfield.esm spacesuit / apparel / face / body FormIDs (verified against Starfield.esm)
    public const uint SfForceHideSpacesuitAvId = 0x000B120E; // ActorShouldForceHideSpacesuit_AV
    public const string SfForceHideSpacesuitAvEdid = "ActorShouldForceHideSpacesuit_AV";

    public const uint SfDefaultNpcSpacesuitOutfitId = 0x0016D5E5; // Outfit_Spacesuit_DefaultNPC_NoBoostpack_NOTPLAYABLE (DFOB 0x1A76BD)
    public const uint SfSpacerSpacesuitOutfitId = 0x003D094D;     // Outfit_Spacesuit_Spacer_AssaultOrNoRole

    public const uint SfSpacesuitBodyKwId = 0x0023C7C0;     // ArmorTypeSpacesuitBody
    public const uint SfSpacesuitHelmetKwId = 0x0023C7C1;   // ArmorTypeSpacesuitHelmet
    public const uint SfSpacesuitBackpackKwId = 0x0023C7C2; // ArmorTypeSpacesuitBackpack
    public const uint SfApparelCategoryKwId = 0x001F0A14;   // InventoryCategoryApparel
    public const uint SfApparelBodyKwId = 0x000E048C;       // ArmorTypeApparelOrNakedBody
    public const uint SfApparelHeadKwId = 0x000E048B;       // ArmorTypeApparelHead

    // Vanilla Starfield.esm HumanRace (0x00347D) ARMA / ARMO templates duplicated for FO4 outfits
    public const uint SfNakedBodyArmaId = 0x00012204;       // AA_Naked_Body (HumanRace 0x00347D, 41 SkinAttach bones)
    public const string SfNakedBodyArmaEdid = "AA_Naked_Body";
    public const uint SfFirstMercBodyArmoId = 0x00228826;   // Clothes_First_Mercenary_01 (HumanRace apparel ARMO)
    public const string SfFirstMercBodyArmoEdid = "Clothes_First_Mercenary_01";
    public const uint SfFirstMercHatArmaId = 0x00211140;    // AA_Clothes_First_Mercenary_01_Hat (HumanRace C_Head ARMA)
    public const string SfFirstMercHatArmaEdid = "AA_Clothes_First_Mercenary_01_Hat";
    public const uint SfFirstMercHatArmoId = 0x0021113E;    // Clothes_First_Mercenary_01_Hat (HumanRace hat ARMO)
    public const string SfFirstMercHatArmoEdid = "Clothes_First_Mercenary_01_Hat";
    public const uint SfMechanicOutfitId = 0x0005B422;      // Outfit_Clothes_Mechanic_Tanktop_Brown

    // Biped body-part slot bitmasks (BO64) verified against Starfield.esm:
    //   - 0x68 (0x08 BODY | 0x20 UpperBody | 0x40 Hands): gloved full-body outfits (0x21BBF2 Clothes_NewAtlantis_Security,
    //     0x25E8D4 Clothes_UCPolice), hiding both AA_Naked_Body (0x08) and AA_Naked_Hands (0x40).
    //   - 0x10 (HairTop) on ARMO + 0x12 (Hair | HairTop) on ARMA: companion NonPlayable hat 0x1C8E0A -> 0x25DEEB
    //     (Clothes_Colonist_Adventurous_Hat_SamCoe_NOTPLAYABLE), activating Hair_Afro cap-mask without HEAD (0x01) conflict.
    public const SF.FirstPersonFlag GlovedFullBodyFlags = (SF.FirstPersonFlag)0x68;
    public const SF.FirstPersonFlag BareHandedBodyFlags = (SF.FirstPersonFlag)0x28;
    public const SF.FirstPersonFlag HatArmoFlags = (SF.FirstPersonFlag)0x10;
    public const SF.FirstPersonFlag HatArmaFlags = (SF.FirstPersonFlag)0x12;

    // Vanilla Starfield.esm young African-American male face sources matching Fallout4.esm 0x00019FD9 PrestonGarvey
    public const uint SfPrestonFacePrimaryId = 0x000ED1C4;  // EncFreestarSecurityFaceM04 (STON=7, African_Male_yo1_Sk6, Black, Brown)
    public const string SfPrestonFacePrimaryEdid = "EncFreestarSecurityFaceM04";
    public const uint SfPrestonFaceFallbackId = 0x0017961B; // ChargenPresetMale12 (STON=7, African_Male_md1_Sk6, Black, Brown)
    public const uint SfClassicBeardHdptId = 0x0015F5A6;    // Human_Male_Beard_ClassicBeard (matches FO4 Beard01 0x0E12A4)
    public const string SfClassicBeardHdptEdid = "Human_Male_Beard_ClassicBeard";
    public const uint SfShortAfroHdptId = 0x00141E60;       // Human_Male_Hair_Short_Afro (matches FO4 HairMale04 0x0821DC)
    public const string SfShortAfroHdptEdid = "Human_Male_Hair_Short_Afro";

    // Fallout4.esm 0x00019FD9 PrestonGarvey body proportions
    public const float PrestonWeightThin = 0.3566f;
    public const float PrestonWeightMuscular = 0.3468f;
    public const float PrestonWeightFat = 0.2966f;
    public const byte PrestonMinSkinToneIndex = 5;

    // Reserved local FormIDs in FO4SFMission.esm: 0x980..0x98A (disjoint from 0x800..0x979 and A4 0xA00..0xBF0)
    public const uint PrestonOutfitId = 0x980;
    public const string PrestonOutfitEdid = "FO4_Outfit_PrestonMinuteman";
    public const uint PrestonDusterArmaId = 0x981;
    public const string PrestonDusterArmaEdid = "FO4_AA_PrestonDuster";
    public const uint PrestonDusterArmoId = 0x983;
    public const string PrestonDusterArmoEdid = "FO4_Armor_PrestonMinuteman";
    public const uint PrestonHatArmaId = 0x984;
    public const string PrestonHatArmaEdid = "FO4_AA_PrestonHat";
    public const uint PrestonHatArmoId = 0x985;
    public const string PrestonHatArmoEdid = "FO4_Armor_PrestonHat";

    // Round 11 A2.3: Dedicated local Concord raider NPC_ (replaces global override of FO4ActorRaider.esm:0xF04800)
    public const uint ConcordRaiderNpcId = 0x986;
    public const string ConcordRaiderNpcEdid = "FO4_ConcordRaider";

    // Review #7: Later-mission FO4_LvlRaider-cloned NPCs in FO4SFMission.esm that otherwise inherit SOFT=0x003D094D
    public const uint CorvegaBossNpcId = 0x0A23;
    public const string CorvegaBossNpcEdid = "FO4_CorvegaBoss";
    public const uint KelloggNpcId = 0x0AD1;
    public const string KelloggNpcEdid = "FO4_Kellogg";
    public const uint CourserZ247NpcId = 0x0B31;
    public const string CourserZ247NpcEdid = "FO4_CourserZ247";
    public static readonly (uint Id, string Edid)[] LaterRaiderClonedNpcs =
    {
        (CorvegaBossNpcId, CorvegaBossNpcEdid),
        (KelloggNpcId, KelloggNpcEdid),
        (CourserZ247NpcId, CourserZ247NpcEdid),
    };

    public const uint RaiderOutfitId = 0x988;
    public const string RaiderOutfitEdid = "FO4_Outfit_ConcordRaider";
    public const uint RaiderBodyArmaId = 0x989;
    public const string RaiderBodyArmaEdid = "FO4_AA_ConcordRaider";
    public const uint RaiderBodyArmoId = 0x98A;
    public const string RaiderBodyArmoEdid = "FO4_Armor_ConcordRaider";
    public const uint MaxAllocatedId = 0x98B;

    // Default staged relative NIF paths written by scripts/actors/stage_c5_actor_looks.py
    public const string StagedPrestonOutfitModel = "fo4port/armor/preston_garvey/prestongarveyoutfit_m.nif";
    public const string StagedPrestonHatModel = "fo4port/armor/preston_garvey/prestongarveyhat_m.nif";
    public const string StagedRaiderOutfitModel = "fo4core/armor/raider04/concord_raider_m.nif";

    public sealed record ActorLooksModels(
        string? PrestonOutfitModel = null,
        string? PrestonHatModel = null,
        string? RaiderOutfitModel = null)
    {
        public static ActorLooksModels FromDirectoryOrArgs(
            string? actorLooksDir = null,
            string? prestonOutfitModel = null,
            string? prestonHatModel = null,
            string? raiderOutfitModel = null)
        {
            string? dir = string.IsNullOrWhiteSpace(actorLooksDir)
                ? Environment.GetEnvironmentVariable("FO4SF_C5_ACTOR_LOOKS_DIR")
                : actorLooksDir;
            if (!string.IsNullOrWhiteSpace(dir))
            {
                string pBody = Path.Combine(dir, "meshes", "fo4port", "armor", "preston_garvey", "prestongarveyoutfit_m.nif");
                string pHat = Path.Combine(dir, "meshes", "fo4port", "armor", "preston_garvey", "prestongarveyhat_m.nif");
                string rBody = Path.Combine(dir, "meshes", "fo4core", "armor", "raider04", "concord_raider_m.nif");
                prestonOutfitModel ??= File.Exists(pBody) ? StagedPrestonOutfitModel : null;
                prestonHatModel ??= File.Exists(pHat) ? StagedPrestonHatModel : null;
                raiderOutfitModel ??= File.Exists(rBody) ? StagedRaiderOutfitModel : null;
            }
            return new ActorLooksModels(prestonOutfitModel, prestonHatModel, raiderOutfitModel);
        }
    }

    /// <summary>
    /// Applies Fallout 4 outfits, Preston's Fallout 4 face/hair/beard/weight traits + D2 hat fix, dedicated
    /// FO4_ConcordRaider (0x000986) scoped strictly to Concord raider ACHRs (0x803..0x80F, Round 11 A2.3),
    /// and Triple-Lock Starfield spacesuit/helmet stripping.
    /// Call once in Mission.Write after NPCs and placed ACHRs are populated and before mod.BeginWrite.
    /// </summary>
    public static void ApplyActorLooks(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        SF.IStarfieldModGetter raiderMod,
        ActorLooksModels? models = null)
    {
        models ??= ActorLooksModels.FromDirectoryOrArgs();
        var modKey = mod.ModKey;
        var humanRaceKey = new FormKey(SfEsm, Mission.SfHumanRaceId);
        var forceHideAvKey = new FormKey(SfEsm, SfForceHideSpacesuitAvId);

        // 1. Build Preston's Fallout 4 Minuteman Outfit (0x980..0x985) and Concord Raider Outfit (0x988..0x98A)
        var prestonOutfit = BuildPrestonOutfit(mod, sfMod, humanRaceKey, models.PrestonOutfitModel, models.PrestonHatModel);
        var raiderOutfit = BuildRaiderOutfit(mod, sfMod, humanRaceKey, models.RaiderOutfitModel);

        // 2. Configure Preston Garvey (0x000801): face traits first, then Minuteman outfit + spacesuit strip
        var preston = mod.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(modKey, Mission.PrestonNpcId))
                      ?? throw new InvalidOperationException($"FO4SFMission missing Preston NPC_ 0x{Mission.PrestonNpcId:X}");
        ApplyPrestonFalloutFace(preston, sfMod);
        preston.DefaultOutfit.SetTo(prestonOutfit.FormKey);
        preston.SpaceOutfit.SetTo(prestonOutfit.FormKey);
        EnforceNoStarfieldSpacesuit(preston, sfMod, forceHideAvKey, prestonOutfit.FormKey);

        // 3. Round 11 A2.3: Create dedicated local FO4SFMission.esm:0x000986 (FO4_ConcordRaider) cloned from
        //    FO4ActorRaider.esm:0xF04800 (FO4_LvlRaider) instead of overriding 0xF04800 globally.
        //    Rebind ONLY Concord's placed raider ACHRs (0x803..0x80F) to 0x000986 so non-Concord raiders
        //    (e.g. Corvega / Fort Hagen in A7cd) and rebuilt FO4ActorRaider.esm remain untouched.
        var baseRaider = raiderMod.Npcs.FirstOrDefault(n => n.FormKey.ID == Mission.RaiderId && n.EditorID == "FO4_LvlRaider")
                         ?? throw new InvalidOperationException($"{raiderMod.ModKey} missing 0x{Mission.RaiderId:X6} FO4_LvlRaider");
        mod.Npcs.Remove(new FormKey(raiderMod.ModKey, Mission.RaiderId));

        var concordRaider = (SF.Npc)baseRaider.Duplicate(new FormKey(modKey, ConcordRaiderNpcId));
        concordRaider.EditorID = ConcordRaiderNpcEdid;
        concordRaider.FormVersion = 581;
        concordRaider.DefaultOutfit.SetTo(raiderOutfit.FormKey);
        concordRaider.SpaceOutfit.SetTo(raiderOutfit.FormKey);
        EnforceNoStarfieldSpacesuit(concordRaider, sfMod, forceHideAvKey, raiderOutfit.FormKey, preserveIntentionalTemplates: true);
        // R13 E3: Clear TemplateActorType.Inventory so EncSpacer01Template cannot inject vanilla full-damage Spacer guns,
        // and clear baseRaider's inherited Coachman (0x26D96B) CNTO entry so Concord raiders carry only Min00's stand-ins.
        // R14 2g-fix6: Clear TemplateActorType.AiData so Concord raiders never inherit empty/passive AIDT and explicitly attack the player.
        concordRaider.UseTemplateActors &= ~(SF.Npc.TemplateActorType.Inventory | SF.Npc.TemplateActorType.AiData);
        concordRaider.Aggression = SF.Npc.AggressionType.Aggressive;
        concordRaider.Confidence = SF.Npc.ConfidenceType.Brave;
        concordRaider.Assistance = SF.Npc.AssistanceType.HelpsAllies;
        concordRaider.Items?.Clear();
        concordRaider.Items = null;
        mod.Npcs.Remove(concordRaider.FormKey);
        mod.Npcs.Add(concordRaider);

        foreach (var r in Mission.PersistentNpcRefsMutable(mod))
        {
            if (IsConcordRaiderRefId(r.FormKey, modKey))
                r.Base.SetTo(concordRaider.FormKey);
        }

        // 4. Review #7: Strip 0x003D094D Spacer spacesuit outfits on all later-mission FO4_LvlRaider-cloned local NPCs
        //    in FO4SFMission.esm (0x0A23 FO4_CorvegaBoss, 0x0AD1 FO4_Kellogg, 0x0B31 FO4_CourserZ247), while keeping
        //    FO4ActorRaider.esm:0xF04800 untouched (0 foreign NPC_ overrides) and non-raider NPCs (FO4_Sturges, etc.) untouched.
        var spacerSuitKey = new FormKey(SfEsm, SfSpacerSpacesuitOutfitId);
        var laterRaiderIds = LaterRaiderClonedNpcs.Select(x => x.Id).ToHashSet();
        foreach (var npc in mod.Npcs)
        {
            if (npc.FormKey.ModKey != modKey || npc.FormKey.ID is Mission.PrestonNpcId or ConcordRaiderNpcId)
                continue;
            if (laterRaiderIds.Contains(npc.FormKey.ID) ||
                npc.DefaultOutfit.FormKey == spacerSuitKey ||
                npc.SpaceOutfit.FormKey == spacerSuitKey)
            {
                npc.DefaultOutfit.SetTo(raiderOutfit.FormKey);
                npc.SpaceOutfit.SetTo(raiderOutfit.FormKey);
                EnforceNoStarfieldSpacesuit(npc, sfMod, forceHideAvKey, raiderOutfit.FormKey, preserveIntentionalTemplates: true);
            }
        }

        if (mod.ModHeader.Stats.NextFormID < MaxAllocatedId)
            mod.ModHeader.Stats.NextFormID = MaxAllocatedId;
    }

    public static bool IsConcordRaiderRefId(FormKey refKey, ModKey missionModKey)
        => refKey.ModKey == missionModKey &&
           refKey.ID >= Mission.FirstRaiderRefId &&
           refKey.ID < Mission.CodsworthNpcId;

    public static void EnforceNoStarfieldSpacesuit(
        SF.Npc npc,
        SF.IStarfieldModGetter sfMod,
        FormKey forceHideAvKey,
        FormKey nonSpacesuitOutfitKey,
        bool preserveIntentionalTemplates = false)
    {
        if (!preserveIntentionalTemplates)
        {
            npc.DefaultTemplate.Clear();
            npc.TemplateActors = null;
            npc.UseTemplateActors = (SF.Npc.TemplateActorType)0;
        }

        if (npc.DefaultOutfit.IsNull || IsSpacesuitOutfit(npc.DefaultOutfit.FormKey, sfMod, null))
            npc.DefaultOutfit.SetTo(nonSpacesuitOutfitKey);

        // Never leave SpaceOutfit == Null (which triggers DFOB 0x001A76BD -> 0x0016D5E5) or any Outfit_Spacesuit_*
        npc.SpaceOutfit.SetTo(npc.DefaultOutfit.FormKey);

        npc.Properties ??= new ExtendedList<SF.ObjectProperty>();
        var existing = npc.Properties.FirstOrDefault(p => p.ActorValue.FormKey == forceHideAvKey);
        if (existing is not null)
        {
            existing.Value = 1.0f;
        }
        else
        {
            npc.Properties.Add(new SF.ObjectProperty
            {
                ActorValue = new FormLink<SF.IActorValueInformationGetter>(forceHideAvKey),
                Value = 1.0f,
            });
        }

        if (npc.Items is { Count: > 0 })
        {
            for (int i = npc.Items.Count - 1; i >= 0; i--)
            {
                var itemKey = npc.Items[i].Item.Item.FormKey;
                if (IsSpacesuitItem(itemKey, sfMod))
                    npc.Items.RemoveAt(i);
            }
        }
    }

    public static void ApplyPrestonFalloutFace(SF.Npc preston, SF.IStarfieldModGetter sfMod)
    {
        SF.INpcGetter? faceSrc = null;
        foreach (uint candidateId in new[] { SfPrestonFacePrimaryId, SfPrestonFaceFallbackId, 0x00005787u })
        {
            if (sfMod.Npcs.TryGetValue(new FormKey(SfEsm, candidateId), out var found))
            {
                faceSrc = found;
                break;
            }
        }

        preston.Tints ??= new ExtendedList<SF.NpcTint>();

        if (faceSrc is not null)
        {
            preston.HeadParts.Clear();
            bool hasClassicBeard = sfMod.HeadParts.ContainsKey(new FormKey(SfEsm, SfClassicBeardHdptId));
            bool addedBeard = false;
            foreach (var hpLink in faceSrc.HeadParts)
            {
                string hpEdid = sfMod.HeadParts.TryGetValue(hpLink.FormKey, out var hpRec) ? (hpRec.EditorID ?? "") : "";
                if (hpEdid.Contains("Jewelry", StringComparison.OrdinalIgnoreCase))
                    continue;
                if (hasClassicBeard && hpEdid.Contains("Beard_", StringComparison.OrdinalIgnoreCase))
                {
                    if (!addedBeard)
                    {
                        preston.HeadParts.Add(new FormLink<SF.IHeadPartGetter>(new FormKey(SfEsm, SfClassicBeardHdptId)));
                        addedBeard = true;
                    }
                    continue;
                }
                preston.HeadParts.Add(new FormLink<SF.IHeadPartGetter>(hpLink.FormKey));
            }
            if (hasClassicBeard && !addedBeard)
                preston.HeadParts.Add(new FormLink<SF.IHeadPartGetter>(new FormKey(SfEsm, SfClassicBeardHdptId)));

            preston.Tints.Clear();
            if (faceSrc.Tints is not null)
            {
                foreach (var tint in faceSrc.Tints)
                    preston.Tints.Add(tint.DeepCopy());
            }

            preston.FaceDialPositions.Clear();
            if (faceSrc.FaceDialPositions is not null)
            {
                foreach (var dial in faceSrc.FaceDialPositions)
                    preston.FaceDialPositions.Add(dial.DeepCopy());
            }

            preston.FaceMorphs.Clear();
            if (faceSrc.FaceMorphs is not null)
            {
                foreach (var fm in faceSrc.FaceMorphs)
                    preston.FaceMorphs.Add(fm.DeepCopy());
            }

            preston.MorphBlends.Clear();
            if (faceSrc.MorphBlends is not null)
            {
                foreach (var mb in faceSrc.MorphBlends)
                {
                    if ((mb.BlendName ?? "").Contains("_ol1_", StringComparison.OrdinalIgnoreCase))
                        continue;
                    preston.MorphBlends.Add(mb.DeepCopy());
                }
            }

            if (faceSrc.BodyMorphRegionValues is { } bmr)
                preston.BodyMorphRegionValues = bmr.DeepCopy();

            preston.SkinToneIndex = faceSrc.SkinToneIndex >= PrestonMinSkinToneIndex ? faceSrc.SkinToneIndex : (byte)7;
        }
        else
        {
            // Synthetic selftest master fallback when full Starfield.esm Chargen/NPC face pool is not present
            preston.SkinToneIndex = 7;
            preston.MorphBlends.Clear();
            preston.MorphBlends.Add(new SF.NpcMorphBlend { BlendName = "male_af_yo1_Jaw", Intensity = 0.85f });
            preston.MorphBlends.Add(new SF.NpcMorphBlend { BlendName = "male_af_yo1_Eyes", Intensity = 0.75f });
            preston.Tints.Clear();
            preston.Tints.Add(new SF.NpcTint
            {
                TintGroup = "Dermaesthetic",
                TintName = "African_Male_yo1_Sk6",
                TintTexture = "textures/actors/human/faces/chargen/postblenddetails/dermaesthetic/male_af_yo1_sk6_derm_color.dds",
                TintIntensity = 64,
            });
        }

        // Exact Fallout4.esm 0x00019FD9 (PrestonGarvey) hair/beard/eye colors & body proportions
        preston.HairColor = "Black";
        preston.FacialHairColor = "Black";
        preston.EyebrowColor = "Black";
        preston.EyeColor = "Brown";
        preston.HeightMin = 1.0f;
        preston.HeightMax = 1.0f;
        preston.Weight = new SF.NpcWeight
        {
            Thin = PrestonWeightThin,
            Muscular = PrestonWeightMuscular,
            Fat = PrestonWeightFat,
        };
    }

    static SF.Outfit BuildPrestonOutfit(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        FormKey humanRaceKey,
        string? prestonOutfitModel,
        string? prestonHatModel)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;

        var dusterArma = DuplicateOrCreateBodyArma(mod, sfMod, PrestonDusterArmaId, PrestonDusterArmaEdid, humanRaceKey, prestonOutfitModel);
        var dusterArmo = DuplicateOrCreateApparelArmo(
            mod, sfMod, PrestonDusterArmoId, PrestonDusterArmoEdid, "Minuteman Duster", humanRaceKey,
            isHeadwear: false, dusterArma.FormKey);

        var hatArma = DuplicateOrCreateHatArma(mod, sfMod, PrestonHatArmaId, PrestonHatArmaEdid, humanRaceKey, prestonHatModel);
        var hatArmo = DuplicateOrCreateApparelArmo(
            mod, sfMod, PrestonHatArmoId, PrestonHatArmoEdid, "Minuteman Hat", humanRaceKey,
            isHeadwear: true, hatArma.FormKey);

        var otft = new SF.Outfit(new FormKey(modKey, PrestonOutfitId), rel)
        {
            EditorID = PrestonOutfitEdid,
            FormVersion = 581,
            Items = new ExtendedList<IFormLinkGetter<SF.IOutfitTargetGetter>>
            {
                new FormLink<SF.IOutfitTargetGetter>(dusterArmo.FormKey),
                new FormLink<SF.IOutfitTargetGetter>(hatArmo.FormKey),
            },
        };
        mod.Outfits.Remove(otft.FormKey);
        mod.Outfits.Add(otft);
        return otft;
    }

    static SF.Outfit BuildRaiderOutfit(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        FormKey humanRaceKey,
        string? raiderOutfitModel)
    {
        var modKey = mod.ModKey;
        var rel = SF.StarfieldRelease.Starfield;

        var raiderArma = DuplicateOrCreateBodyArma(
            mod, sfMod, RaiderBodyArmaId, RaiderBodyArmaEdid, humanRaceKey, raiderOutfitModel, BareHandedBodyFlags);
        var raiderArmo = DuplicateOrCreateApparelArmo(
            mod, sfMod, RaiderBodyArmoId, RaiderBodyArmoEdid, "Raider Scavenger Outfit", humanRaceKey,
            isHeadwear: false, raiderArma.FormKey, BareHandedBodyFlags);

        var otft = new SF.Outfit(new FormKey(modKey, RaiderOutfitId), rel)
        {
            EditorID = RaiderOutfitEdid,
            FormVersion = 581,
            Items = new ExtendedList<IFormLinkGetter<SF.IOutfitTargetGetter>>
            {
                new FormLink<SF.IOutfitTargetGetter>(raiderArmo.FormKey),
            },
        };
        mod.Outfits.Remove(otft.FormKey);
        mod.Outfits.Add(otft);
        return otft;
    }

    static SF.ArmorAddon DuplicateOrCreateBodyArma(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        uint localId,
        string edid,
        FormKey humanRaceKey,
        string? customNifRelPath,
        SF.FirstPersonFlag? slotFlagsOverride = null)
    {
        var key = new FormKey(mod.ModKey, localId);
        SF.ArmorAddon arma;
        if (sfMod.ArmorAddons.TryGetValue(new FormKey(SfEsm, SfNakedBodyArmaId), out var srcArma))
        {
            arma = (SF.ArmorAddon)srcArma.Duplicate(key);
            arma.FirstPersonModel = null;
        }
        else
        {
            arma = new SF.ArmorAddon(key, SF.StarfieldRelease.Starfield)
            {
                FormVersion = 581,
                WorldModel = new GenderedItem<SF.Model?>(
                    new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Actors\\Human\\Mesh\\Naked_Body\\Naked_M.nif") },
                    new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Actors\\Human\\Mesh\\Naked_Body\\Naked_F.nif") }),
            };
        }

        arma.EditorID = edid;
        arma.Race.SetTo(humanRaceKey);
        arma.FirstPersonFlags = slotFlagsOverride ?? GlovedFullBodyFlags;
        if (!string.IsNullOrWhiteSpace(customNifRelPath))
        {
            SetWorldModels(arma, customNifRelPath);
        }
        else if (sfMod.Armors.TryGetValue(new FormKey(SfEsm, SfFirstMercBodyArmoId), out var mercArmo) &&
                 mercArmo.Armatures.FirstOrDefault()?.ArmorAddon.FormKey is { IsNull: false } mercArmaKey &&
                 sfMod.ArmorAddons.TryGetValue(mercArmaKey, out var mercArma) &&
                 mercArma.WorldModel?.Male?.File?.GivenPath is { Length: > 0 } mercPath)
        {
            SetWorldModels(arma, mercPath, mercArma.WorldModel?.Female?.File?.GivenPath);
        }
        else
        {
            string fallbackM = arma.WorldModel?.Male?.File?.GivenPath ?? "Actors\\Human\\Mesh\\Naked_Body\\Naked_M.nif";
            string fallbackF = arma.WorldModel?.Female?.File?.GivenPath ?? "Actors\\Human\\Mesh\\Naked_Body\\Naked_F.nif";
            SetWorldModels(arma, fallbackM, fallbackF);
        }

        mod.ArmorAddons.Remove(key);
        mod.ArmorAddons.Add(arma);
        return arma;
    }

    static SF.ArmorAddon DuplicateOrCreateHatArma(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        uint localId,
        string edid,
        FormKey humanRaceKey,
        string? customHatNifRelPath)
    {
        var key = new FormKey(mod.ModKey, localId);
        SF.ArmorAddon arma;
        if (sfMod.ArmorAddons.TryGetValue(new FormKey(SfEsm, SfFirstMercHatArmaId), out var srcHat))
        {
            arma = (SF.ArmorAddon)srcHat.Duplicate(key);
            arma.FirstPersonModel = null;
        }
        else
        {
            arma = new SF.ArmorAddon(key, SF.StarfieldRelease.Starfield)
            {
                FormVersion = 581,
                WorldModel = new GenderedItem<SF.Model?>(
                    new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Clothes\\outfit_first_mercenary_01\\Outfit_First_Mercenary_01_Hat_M.nif") },
                    new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Clothes\\outfit_first_mercenary_01\\Outfit_First_Mercenary_01_Hat_F.nif") }),
            };
        }

        arma.EditorID = edid;
        arma.Race.SetTo(humanRaceKey);
        arma.FirstPersonFlags = HatArmaFlags;
        if (!string.IsNullOrWhiteSpace(customHatNifRelPath))
        {
            // Round 11 D2 fix: SetWorldModels replaces the duplicated SF.Model instances so MO2F/MO3F/XFLG
            // (HasFaceBonesModel = 0x01 on 0x211140) are stripped; Starfield loads prestongarveyhat_m.nif directly
            // instead of searching for a non-existent prestongarveyhat_m_facebones.nif.
            SetWorldModels(arma, customHatNifRelPath);
        }
        else
        {
            string fallbackM = arma.WorldModel?.Male?.File?.GivenPath ?? "Clothes\\outfit_first_mercenary_01\\Outfit_First_Mercenary_01_Hat_M.nif";
            string fallbackF = arma.WorldModel?.Female?.File?.GivenPath ?? "Clothes\\outfit_first_mercenary_01\\Outfit_First_Mercenary_01_Hat_F.nif";
            SetWorldModels(arma, fallbackM, fallbackF);
        }

        mod.ArmorAddons.Remove(key);
        mod.ArmorAddons.Add(arma);
        return arma;
    }

    static void SetWorldModels(SF.ArmorAddon arma, string maleRel, string? femaleRel = null)
    {
        string baseGiven = arma.WorldModel?.Male?.File?.GivenPath ?? "";
        // Construct brand-new SF.Model wrappers (Flags = null, Data = null) so template-specific MO2F/MO3F/XFLG
        // flags (such as HasFaceBonesModel = 0x01 on vanilla hat ARMAs) never leak onto converted FO4 C_Head NIFs.
        arma.WorldModel = new GenderedItem<SF.Model?>(
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(Mission.ModelPath(baseGiven, maleRel)) },
            new SF.Model { File = new AssetLink<StarfieldModelAssetType>(Mission.ModelPath(baseGiven, femaleRel ?? maleRel)) });
    }

    static SF.Armor DuplicateOrCreateApparelArmo(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        uint localId,
        string edid,
        string displayName,
        FormKey humanRaceKey,
        bool isHeadwear,
        FormKey armaKey,
        SF.FirstPersonFlag? slotFlagsOverride = null)
    {
        var key = new FormKey(mod.ModKey, localId);
        uint tplId = isHeadwear ? SfFirstMercHatArmoId : SfFirstMercBodyArmoId;
        SF.Armor armo;
        if (sfMod.Armors.TryGetValue(new FormKey(SfEsm, tplId), out var srcArmo))
        {
            armo = (SF.Armor)srcArmo.Duplicate(key);
        }
        else
        {
            armo = new SF.Armor(key, SF.StarfieldRelease.Starfield)
            {
                FormVersion = 581,
                Keywords = new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>>
                {
                    new FormLink<SF.IKeywordGetter>(new FormKey(SfEsm, SfApparelCategoryKwId)),
                    new FormLink<SF.IKeywordGetter>(new FormKey(SfEsm, isHeadwear ? SfApparelHeadKwId : SfApparelBodyKwId)),
                },
            };
        }

        armo.EditorID = edid;
        armo.Name = displayName;
        armo.Race.SetTo(humanRaceKey);
        armo.FirstPersonFlags = slotFlagsOverride ?? (isHeadwear ? HatArmoFlags : GlovedFullBodyFlags);
        armo.MajorFlags |= SF.Armor.MajorFlag.NonPlayable;
        if (armo.Keywords is not null)
        {
            for (int i = armo.Keywords.Count - 1; i >= 0; i--)
            {
                uint kid = armo.Keywords[i].FormKey.ID;
                if (kid is SfSpacesuitBodyKwId or SfSpacesuitHelmetKwId or SfSpacesuitBackpackKwId)
                    armo.Keywords.RemoveAt(i);
            }
        }
        armo.Armatures.Clear();
        armo.Armatures.Add(new SF.ArmorAddonModel
        {
            AddonIndex = 0,
            ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(armaKey),
        });

        mod.Armors.Remove(key);
        mod.Armors.Add(armo);
        return armo;
    }

    public static bool IsSpacesuitOutfit(FormKey outfitKey, SF.IStarfieldModGetter sfMod, SF.IStarfieldModGetter? localMod)
    {
        if (outfitKey.IsNull)
            return true;
        if (outfitKey.ModKey == SfEsm &&
            outfitKey.ID is SfDefaultNpcSpacesuitOutfitId or SfSpacerSpacesuitOutfitId)
            return true;

        SF.IOutfitGetter? otft = null;
        if (localMod is not null && localMod.Outfits.TryGetValue(outfitKey, out var localOtft))
            otft = localOtft;
        else if (sfMod.Outfits.TryGetValue(outfitKey, out var sfOtft))
            otft = sfOtft;

        if (otft is null)
            return false;

        if ((otft.EditorID ?? "").Contains("Spacesuit", StringComparison.OrdinalIgnoreCase))
            return true;

        if (otft.Items is not null)
        {
            foreach (var itemLink in otft.Items)
            {
                if (IsSpacesuitItem(itemLink.FormKey, sfMod, localMod))
                    return true;
            }
        }
        return false;
    }

    public static bool IsSpacesuitItem(FormKey itemKey, SF.IStarfieldModGetter sfMod, SF.IStarfieldModGetter? localMod = null)
    {
        SF.IArmorGetter? armo = null;
        if (localMod is not null && localMod.Armors.TryGetValue(itemKey, out var localArmo))
            armo = localArmo;
        else if (sfMod.Armors.TryGetValue(itemKey, out var sfArmo))
            armo = sfArmo;

        if (armo is not null)
        {
            if ((armo.EditorID ?? "").Contains("Spacesuit", StringComparison.OrdinalIgnoreCase))
                return true;
            if (armo.Keywords is not null && armo.Keywords.Any(k =>
                    k.FormKey.ModKey == SfEsm &&
                    k.FormKey.ID is SfSpacesuitBodyKwId or SfSpacesuitHelmetKwId or SfSpacesuitBackpackKwId))
                return true;
        }

        if (sfMod.LeveledItems.TryGetValue(itemKey, out var lvli) &&
            (lvli.EditorID ?? "").Contains("Spacer_", StringComparison.OrdinalIgnoreCase) &&
            ((lvli.EditorID ?? "").Contains("Body", StringComparison.OrdinalIgnoreCase) ||
             (lvli.EditorID ?? "").Contains("Helmet", StringComparison.OrdinalIgnoreCase) ||
             (lvli.EditorID ?? "").Contains("Backpack", StringComparison.OrdinalIgnoreCase) ||
             (lvli.EditorID ?? "").Contains("Spacesuit", StringComparison.OrdinalIgnoreCase)))
        {
            return true;
        }

        return false;
    }

    /// <summary>
    /// Validates all C5 + Round 11 D2 & A2.3 binary invariants on the written FO4SFMission.esm plugin.
    /// Appends human-readable failure descriptions to <paramref name="problems"/>.
    /// </summary>
    public static void CheckActorLooks(
        SF.IStarfieldModGetter plug,
        SF.IStarfieldModGetter sfMod,
        ModKey raiderModKey,
        List<string> problems,
        ActorLooksModels? expectedModels = null)
    {
        void Need(bool ok, string what) { if (!ok) problems.Add(what); }
        var key = plug.ModKey;
        var humanRaceKey = new FormKey(SfEsm, Mission.SfHumanRaceId);
        var forceHideAvKey = new FormKey(SfEsm, SfForceHideSpacesuitAvId);

        // 1. Local Fallout 4 Outfit / Armor / ArmorAddon records (0x980..0x98A) + D2 flags hygiene
        var prestonOtft = plug.Outfits.FirstOrDefault(o => o.FormKey == new FormKey(key, PrestonOutfitId));
        var prestonDusterArma = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, PrestonDusterArmaId));
        var prestonDusterArmo = plug.Armors.FirstOrDefault(a => a.FormKey == new FormKey(key, PrestonDusterArmoId));
        var prestonHatArma = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, PrestonHatArmaId));
        var prestonHatArmo = plug.Armors.FirstOrDefault(a => a.FormKey == new FormKey(key, PrestonHatArmoId));

        Need(prestonOtft is { EditorID: PrestonOutfitEdid } &&
             prestonOtft.Items is { Count: 2 } &&
             prestonOtft.Items.Any(i => i.FormKey == new FormKey(key, PrestonDusterArmoId)) &&
             prestonOtft.Items.Any(i => i.FormKey == new FormKey(key, PrestonHatArmoId)),
             $"OTFT 0x{PrestonOutfitId:X} ({PrestonOutfitEdid}) missing duster (0x{PrestonDusterArmoId:X}) or hat (0x{PrestonHatArmoId:X})");
        Need(prestonDusterArma is { EditorID: PrestonDusterArmaEdid } && prestonDusterArma.Race.FormKey == humanRaceKey,
             $"ARMA 0x{PrestonDusterArmaId:X} ({PrestonDusterArmaEdid}) missing or not HumanRace");
        Need(prestonHatArma is { EditorID: PrestonHatArmaEdid } && prestonHatArma.Race.FormKey == humanRaceKey,
             $"ARMA 0x{PrestonHatArmaId:X} ({PrestonHatArmaEdid}) missing or not HumanRace");
        Need(prestonDusterArmo is { EditorID: PrestonDusterArmoEdid } && !IsSpacesuitItem(prestonDusterArmo.FormKey, sfMod, plug),
             $"ARMO 0x{PrestonDusterArmoId:X} ({PrestonDusterArmoEdid}) missing or carries spacesuit keyword");
        Need(prestonHatArmo is { EditorID: PrestonHatArmoEdid } && !IsSpacesuitItem(prestonHatArmo.FormKey, sfMod, plug),
             $"ARMO 0x{PrestonHatArmoId:X} ({PrestonHatArmoEdid}) missing or carries spacesuit keyword");

        // D2 checks: zero HasFaceBonesModel (MO2F/MO3F) on custom ARMAs, exact hat BO64 (0x10/0x12), and gloved body BO64 (0x68)
        Need(prestonHatArma is not null &&
             (prestonHatArma.WorldModel?.Male?.Flags ?? 0) == 0 &&
             (prestonHatArma.WorldModel?.Female?.Flags ?? 0) == 0,
             $"D2: ARMA 0x{PrestonHatArmaId:X} ({PrestonHatArmaEdid}) retains Model.Flags (MO2F/MO3F HasFaceBonesModel), which redirects Starfield to a missing *_facebones.nif");
        Need(prestonDusterArma is not null &&
             (prestonDusterArma.WorldModel?.Male?.Flags ?? 0) == 0 &&
             (prestonDusterArma.WorldModel?.Female?.Flags ?? 0) == 0,
             $"ARMA 0x{PrestonDusterArmaId:X} ({PrestonDusterArmaEdid}) retains unexpected Model.Flags");
        Need(prestonHatArmo?.FirstPersonFlags == HatArmoFlags && prestonHatArma?.FirstPersonFlags == HatArmaFlags,
             $"D2: Preston hat BO64 mismatch (ARMO={prestonHatArmo?.FirstPersonFlags}, ARMA={prestonHatArma?.FirstPersonFlags}; expected 0x10 / 0x12)");
        Need(prestonDusterArma?.FirstPersonFlags == GlovedFullBodyFlags && prestonDusterArmo?.FirstPersonFlags == GlovedFullBodyFlags,
             $"D2: Preston duster BO64 lacks Hands (0x40) mask (ARMA={prestonDusterArma?.FirstPersonFlags}, ARMO={prestonDusterArmo?.FirstPersonFlags}; expected 0x68)");

        var raiderOtft = plug.Outfits.FirstOrDefault(o => o.FormKey == new FormKey(key, RaiderOutfitId));
        var raiderArma = plug.ArmorAddons.FirstOrDefault(a => a.FormKey == new FormKey(key, RaiderBodyArmaId));
        var raiderArmo = plug.Armors.FirstOrDefault(a => a.FormKey == new FormKey(key, RaiderBodyArmoId));
        Need(raiderOtft is { EditorID: RaiderOutfitEdid } &&
             raiderOtft.Items is { Count: >= 1 } &&
             raiderOtft.Items.Any(i => i.FormKey == new FormKey(key, RaiderBodyArmoId)),
             $"OTFT 0x{RaiderOutfitId:X} ({RaiderOutfitEdid}) missing raider armor (0x{RaiderBodyArmoId:X})");
        Need(raiderArma is { EditorID: RaiderBodyArmaEdid } && raiderArma.Race.FormKey == humanRaceKey,
             $"ARMA 0x{RaiderBodyArmaId:X} ({RaiderBodyArmaEdid}) missing or not HumanRace");
        Need(raiderArmo is { EditorID: RaiderBodyArmoEdid } && !IsSpacesuitItem(raiderArmo.FormKey, sfMod, plug),
             $"ARMO 0x{RaiderBodyArmoId:X} ({RaiderBodyArmoEdid}) missing or carries spacesuit keyword");
        Need(raiderArma is not null &&
             (raiderArma.WorldModel?.Male?.Flags ?? 0) == 0 &&
             (raiderArma.WorldModel?.Female?.Flags ?? 0) == 0 &&
             raiderArma.FirstPersonFlags == BareHandedBodyFlags &&
             raiderArmo?.FirstPersonFlags == BareHandedBodyFlags,
             $"Raider ARMA/ARMO retains Model.Flags or lacks 0x28 bare-handed body BO64");

        if (expectedModels?.PrestonOutfitModel is { Length: > 0 } wantPBody)
        {
            string got = prestonDusterArma?.WorldModel?.Male?.File?.GivenPath ?? "";
            Need(got.Replace('/', '\\').EndsWith(wantPBody.Replace('/', '\\'), StringComparison.OrdinalIgnoreCase),
                 $"Preston duster ARMA Male model '{got}' does not end with '{wantPBody}'");
        }
        if (expectedModels?.PrestonHatModel is { Length: > 0 } wantPHat)
        {
            string got = prestonHatArma?.WorldModel?.Male?.File?.GivenPath ?? "";
            Need(got.Replace('/', '\\').EndsWith(wantPHat.Replace('/', '\\'), StringComparison.OrdinalIgnoreCase),
                 $"Preston hat ARMA Male model '{got}' does not end with '{wantPHat}'");
        }
        if (expectedModels?.RaiderOutfitModel is { Length: > 0 } wantRBody)
        {
            string got = raiderArma?.WorldModel?.Male?.File?.GivenPath ?? "";
            Need(got.Replace('/', '\\').EndsWith(wantRBody.Replace('/', '\\'), StringComparison.OrdinalIgnoreCase),
                 $"Raider ARMA Male model '{got}' does not end with '{wantRBody}'");
        }

        // 2. Preston Garvey (0x000801) outfit, spacesuit strip, and Fallout 4 face traits
        var preston = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, Mission.PrestonNpcId));
        Need(preston is not null, $"Preston NPC_ 0x{Mission.PrestonNpcId:X} missing");
        if (preston is not null)
        {
            Need(preston.UseTemplateActors == 0, $"Preston retains non-zero UseTemplateActors ({preston.UseTemplateActors})");
            Need(preston.DefaultOutfit.FormKey == new FormKey(key, PrestonOutfitId),
                 $"Preston DefaultOutfit ({preston.DefaultOutfit.FormKey}) != 0x{PrestonOutfitId:X} ({PrestonOutfitEdid})");
            Need(preston.SpaceOutfit.FormKey == new FormKey(key, PrestonOutfitId),
                 $"Preston SpaceOutfit ({preston.SpaceOutfit.FormKey}) != 0x{PrestonOutfitId:X} ({PrestonOutfitEdid})");
            Need(HasForceHideSpacesuitProperty(preston, forceHideAvKey),
                 $"Preston lacks {SfForceHideSpacesuitAvEdid} (0x{SfForceHideSpacesuitAvId:X6}) == 1.0");
            Need(preston.SkinToneIndex >= PrestonMinSkinToneIndex,
                 $"Preston SkinToneIndex ({preston.SkinToneIndex}) < {PrestonMinSkinToneIndex} (retained pale PapaKatz skin tone)");
            Need(string.Equals(preston.HairColor, "Black", StringComparison.Ordinal) &&
                 string.Equals(preston.FacialHairColor, "Black", StringComparison.Ordinal) &&
                 string.Equals(preston.EyeColor, "Brown", StringComparison.Ordinal),
                 $"Preston HairColor='{preston.HairColor}', FacialHairColor='{preston.FacialHairColor}', EyeColor='{preston.EyeColor}' != Black/Black/Brown");
            Need(preston.Tints is not null &&
                 preston.Tints.Any(t => (t.TintName ?? "").Contains("African_Male", StringComparison.OrdinalIgnoreCase)) &&
                 !preston.Tints.Any(t => (t.TintName ?? "").Contains("European_Male", StringComparison.OrdinalIgnoreCase)),
                 "Preston Tints lack African_Male dermaesthetic or retain European_Male tint");
            Need(preston.MorphBlends is null ||
                 !preston.MorphBlends.Any(b => (b.BlendName ?? "").Contains("_ol1_", StringComparison.OrdinalIgnoreCase)),
                 "Preston MorphBlends retain old-age (*_ol1_*) morphs from PapaKatz");
            Need(preston.Weight is { } w &&
                 MathF.Abs(w.Thin - PrestonWeightThin) < 1e-3f &&
                 MathF.Abs(w.Muscular - PrestonWeightMuscular) < 1e-3f &&
                 MathF.Abs(w.Fat - PrestonWeightFat) < 1e-3f,
                 "Preston Weight does not match Fallout4.esm 0x00019FD9 (0.3566, 0.3468, 0.2966)");
        }

        // 3. Round 11 A2.3: Zero foreign overrides of FO4ActorRaider.esm + dedicated local 0x000986 FO4_ConcordRaider
        Need(!plug.Npcs.Any(n => n.FormKey.ModKey == raiderModKey),
             $"A2.3: FO4SFMission.esm still overrides shared {raiderModKey} NPCs globally instead of scoping to 0x{ConcordRaiderNpcId:X} ({ConcordRaiderNpcEdid})");

        var concordRaiderKey = new FormKey(key, ConcordRaiderNpcId);
        var concordRaider = plug.Npcs.FirstOrDefault(n => n.FormKey == concordRaiderKey);
        Need(concordRaider is { EditorID: ConcordRaiderNpcEdid, FormVersion: 581 },
             $"A2.3: FO4SFMission.esm lacks FormVersion=581 local NPC_ 0x{ConcordRaiderNpcId:X} ({ConcordRaiderNpcEdid})");
        if (concordRaider is not null)
        {
            Need(concordRaider.DefaultOutfit.FormKey == new FormKey(key, RaiderOutfitId),
                 $"FO4_ConcordRaider DefaultOutfit ({concordRaider.DefaultOutfit.FormKey}) != 0x{RaiderOutfitId:X}");
            Need(concordRaider.SpaceOutfit.FormKey == new FormKey(key, RaiderOutfitId),
                 $"FO4_ConcordRaider SpaceOutfit ({concordRaider.SpaceOutfit.FormKey}) != 0x{RaiderOutfitId:X}");
            Need(HasForceHideSpacesuitProperty(concordRaider, forceHideAvKey),
                 $"FO4_ConcordRaider lacks {SfForceHideSpacesuitAvEdid} (0x{SfForceHideSpacesuitAvId:X6}) == 1.0");
            Need(!concordRaider.UseTemplateActors.HasFlag(SF.Npc.TemplateActorType.Inventory),
                 "R13 E3: FO4_ConcordRaider retains TemplateActorType.Inventory (EncSpacer01Template weapon leak)");
            Need(!concordRaider.UseTemplateActors.HasFlag(SF.Npc.TemplateActorType.AiData),
                 "R14 2g-fix6: FO4_ConcordRaider retains TemplateActorType.AiData");
            Need(concordRaider.Aggression == SF.Npc.AggressionType.Aggressive &&
                 concordRaider.Confidence >= SF.Npc.ConfidenceType.Brave,
                 $"R14 2g-fix6: FO4_ConcordRaider AIDT not aggressive/brave ({concordRaider.Aggression}/{concordRaider.Confidence})");
            Need((concordRaider.Items?.Count ?? 0) == 0,
                 $"R13 E3: FO4_ConcordRaider retains {concordRaider.Items?.Count ?? 0} inventory item(s) instead of 0");
            Need(!IsSpacesuitOutfit(concordRaider.DefaultOutfit.FormKey, sfMod, plug) &&
                 !IsSpacesuitOutfit(concordRaider.SpaceOutfit.FormKey, sfMod, plug),
                 "FO4_ConcordRaider carries a Starfield spacesuit outfit");
        }

        var concordRefs = Mission.PersistentNpcRefs(plug)
            .Where(r => IsConcordRaiderRefId(r.FormKey, key))
            .ToList();
        if (concordRefs.Count > 0)
        {
            Need(concordRefs.All(r => r.Base.FormKey == concordRaiderKey),
                 $"A2.3: one or more Concord raider ACHRs (0x803..0x80F) do not point at 0x{ConcordRaiderNpcId:X} ({ConcordRaiderNpcEdid})");
        }

        // 4. Review #7: Zero NPC_ records in FO4SFMission.esm carry 0x003D094D Spacer spacesuit outfit, and all present
        //    later-mission FO4_LvlRaider-cloned NPCs (0x0A23, 0x0AD1, 0x0B31) wear 0x988 + ActorShouldForceHideSpacesuit_AV=1.0
        var spacerSuitKey = new FormKey(SfEsm, SfSpacerSpacesuitOutfitId);
        var spacerCarriers = plug.Npcs
            .Where(n => n.DefaultOutfit.FormKey == spacerSuitKey || n.SpaceOutfit.FormKey == spacerSuitKey)
            .Select(n => $"0x{n.FormKey.ID:X4}:{n.EditorID}")
            .ToList();
        Need(spacerCarriers.Count == 0,
             $"Review #7: FO4SFMission.esm NPC_ records still carry 0x{SfSpacerSpacesuitOutfitId:X6} Spacer spacesuit outfit: [{string.Join(", ", spacerCarriers)}]");

        foreach (var (laterId, laterEdid) in LaterRaiderClonedNpcs)
        {
            var laterNpc = plug.Npcs.FirstOrDefault(n => n.FormKey == new FormKey(key, laterId));
            if (laterNpc is null)
                continue;
            Need(laterNpc.DefaultOutfit.FormKey == new FormKey(key, RaiderOutfitId),
                 $"Review #7: {laterEdid} (0x{laterId:X4}) DefaultOutfit ({laterNpc.DefaultOutfit.FormKey}) != 0x{RaiderOutfitId:X}");
            Need(laterNpc.SpaceOutfit.FormKey == new FormKey(key, RaiderOutfitId),
                 $"Review #7: {laterEdid} (0x{laterId:X4}) SpaceOutfit ({laterNpc.SpaceOutfit.FormKey}) != 0x{RaiderOutfitId:X}");
            Need(HasForceHideSpacesuitProperty(laterNpc, forceHideAvKey),
                 $"Review #7: {laterEdid} (0x{laterId:X4}) lacks {SfForceHideSpacesuitAvEdid} (0x{SfForceHideSpacesuitAvId:X6}) == 1.0");
            Need(!IsSpacesuitOutfit(laterNpc.DefaultOutfit.FormKey, sfMod, plug) &&
                 !IsSpacesuitOutfit(laterNpc.SpaceOutfit.FormKey, sfMod, plug),
                 $"Review #7: {laterEdid} (0x{laterId:X4}) carries a Starfield spacesuit outfit");
            if (laterNpc.Items is not null)
            {
                Need(!laterNpc.Items.Any(i => IsSpacesuitItem(i.Item.Item.FormKey, sfMod, plug)),
                     $"Review #7: {laterEdid} (0x{laterId:X4}) carries a Starfield spacesuit item in inventory");
            }
        }
    }

    public static bool HasForceHideSpacesuitProperty(SF.INpcGetter npc, FormKey forceHideAvKey)
        => npc.Properties is not null &&
           npc.Properties.Any(p => p.ActorValue.FormKey == forceHideAvKey && MathF.Abs(p.Value - 1.0f) < 1e-4f);

    /// <summary>
    /// Seeds synthetic Starfield.esm & FO4ActorRaider.esm records needed to test C5 + Round 11 D2 & A2.3 offline.
    /// </summary>
    public static void SeedSyntheticMasters(SF.StarfieldMod sf, SF.StarfieldMod raider, FormKey humanRaceKey, FormKey maleVoiceKey)
    {
        var rel = SF.StarfieldRelease.Starfield;
        sf.ActorValueInformation.Add(new SF.ActorValueInformation(new FormKey(SfEsm, SfForceHideSpacesuitAvId), rel)
        {
            EditorID = SfForceHideSpacesuitAvEdid,
        });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, SfSpacesuitBodyKwId), rel) { EditorID = "ArmorTypeSpacesuitBody" });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, SfSpacesuitHelmetKwId), rel) { EditorID = "ArmorTypeSpacesuitHelmet" });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, SfApparelCategoryKwId), rel) { EditorID = "InventoryCategoryApparel" });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, SfApparelBodyKwId), rel) { EditorID = "ArmorTypeApparelOrNakedBody" });
        sf.Keywords.Add(new SF.Keyword(new FormKey(SfEsm, SfApparelHeadKwId), rel) { EditorID = "ArmorTypeApparelHead" });

        var spacerSuitOtft = new SF.Outfit(new FormKey(SfEsm, SfSpacerSpacesuitOutfitId), rel)
        {
            EditorID = "Outfit_Spacesuit_Spacer_AssaultOrNoRole",
        };
        sf.Outfits.Add(spacerSuitOtft);

        // Seed vanilla AA_Clothes_First_Mercenary_01_Hat (0x211140) WITH HasFaceBonesModel (0x01) + BO64=0x12,
        // and Clothes_First_Mercenary_01_Hat (0x21113E) WITH BO64=0x11, reproducing the exact 2g D2 input!
        var srcHatArma = new SF.ArmorAddon(new FormKey(SfEsm, SfFirstMercHatArmaId), rel)
        {
            EditorID = SfFirstMercHatArmaEdid,
            FormVersion = 581,
            FirstPersonFlags = (SF.FirstPersonFlag)0x12,
            Race = new FormLinkNullable<SF.IRaceGetter>(humanRaceKey),
            WorldModel = new GenderedItem<SF.Model?>(
                new SF.Model
                {
                    File = new AssetLink<StarfieldModelAssetType>("Clothes\\outfit_first_mercenary_01\\Outfit_First_Mercenary_01_Hat_M.nif"),
                    Flags = (SF.Model.Flag)1, // HasFaceBonesModel (MO2F = 0x01)
                },
                new SF.Model
                {
                    File = new AssetLink<StarfieldModelAssetType>("Clothes\\outfit_first_mercenary_01\\Outfit_First_Mercenary_01_Hat_F.nif"),
                    Flags = (SF.Model.Flag)1, // HasFaceBonesModel (MO3F = 0x01)
                }),
        };
        sf.ArmorAddons.Add(srcHatArma);

        var srcHatArmo = new SF.Armor(new FormKey(SfEsm, SfFirstMercHatArmoId), rel)
        {
            EditorID = SfFirstMercHatArmoEdid,
            FormVersion = 581,
            FirstPersonFlags = (SF.FirstPersonFlag)0x11,
            Race = new FormLinkNullable<SF.IRaceGetter>(humanRaceKey),
            Keywords = new ExtendedList<IFormLinkGetter<SF.IKeywordGetter>>
            {
                new FormLink<SF.IKeywordGetter>(new FormKey(SfEsm, SfApparelCategoryKwId)),
                new FormLink<SF.IKeywordGetter>(new FormKey(SfEsm, SfApparelHeadKwId)),
            },
        };
        srcHatArmo.Armatures.Add(new SF.ArmorAddonModel
        {
            AddonIndex = 0,
            ArmorAddon = new FormLinkNullable<SF.IArmorAddonGetter>(srcHatArma.FormKey),
        });
        sf.Armors.Add(srcHatArmo);

        // Seed PapaKatz with the exact 2f bugs (STON=4, SaltAndPepper, European_Male_Md2_Sk3, male_eu_ol1_Jaw, UseTemplateActors=0x6C12)
        if (sf.Npcs.TryGetValue(new FormKey(SfEsm, Mission.SfPapaKatzId), out var papa))
        {
            papa.SkinToneIndex = 4;
            papa.HairColor = "SaltAndPepper";
            papa.UseTemplateActors = (SF.Npc.TemplateActorType)0x6C12;
            papa.Tints ??= new ExtendedList<SF.NpcTint>();
            papa.Tints.Add(new SF.NpcTint
            {
                TintGroup = "Dermaesthetic",
                TintName = "European_Male_Md2_Sk3",
                TintIntensity = 64,
            });
            papa.MorphBlends.Add(new SF.NpcMorphBlend { BlendName = "male_eu_ol1_Jaw", Intensity = 1.0f });
        }

        // Seed young African-American male face source (0x0ED1C4 EncFreestarSecurityFaceM04) + ClassicBeard HDPT
        var beardHdpt = new SF.HeadPart(new FormKey(SfEsm, SfClassicBeardHdptId), rel) { EditorID = SfClassicBeardHdptEdid };
        var hairHdpt = new SF.HeadPart(new FormKey(SfEsm, SfShortAfroHdptId), rel) { EditorID = SfShortAfroHdptEdid };
        sf.HeadParts.Add(beardHdpt);
        sf.HeadParts.Add(hairHdpt);

        var afFace = new SF.Npc(new FormKey(SfEsm, SfPrestonFacePrimaryId), rel)
        {
            EditorID = SfPrestonFacePrimaryEdid,
            Race = new FormLink<SF.IRaceGetter>(humanRaceKey),
            Voice = new FormLinkNullable<SF.IVoiceTypeGetter>(maleVoiceKey),
            SkinToneIndex = 7,
            HairColor = "Black",
            FacialHairColor = "Black",
            EyebrowColor = "Black",
            EyeColor = "Brown",
            Tints = new ExtendedList<SF.NpcTint>
            {
                new SF.NpcTint
                {
                    TintGroup = "Dermaesthetic",
                    TintName = "African_Male_yo1_Sk6",
                    TintIntensity = 64,
                },
            },
            MorphBlends = new ExtendedList<SF.NpcMorphBlend>
            {
                new SF.NpcMorphBlend { BlendName = "male_af_yo1_Jaw", Intensity = 0.39f },
                new SF.NpcMorphBlend { BlendName = "male_af_md1_Chin", Intensity = 1.0f },
            },
        };
        afFace.HeadParts.Add(new FormLink<SF.IHeadPartGetter>(hairHdpt.FormKey));
        afFace.HeadParts.Add(new FormLink<SF.IHeadPartGetter>(beardHdpt.FormKey));
        sf.Npcs.Add(afFace);

        // Seed FO4_LvlRaider (0xF04800) with 2f's Spacer spacesuit SpaceOutfit so stripping is verified
        if (raider.Npcs.TryGetValue(new FormKey(raider.ModKey, Mission.RaiderId), out var lvlRaider))
        {
            lvlRaider.Race.SetTo(humanRaceKey);
            lvlRaider.SpaceOutfit.SetTo(spacerSuitOtft.FormKey);
            lvlRaider.UseTemplateActors |= SF.Npc.TemplateActorType.Inventory;
            (lvlRaider.Items ??= new ExtendedList<SF.ContainerEntry>()).Add(new SF.ContainerEntry
            {
                Item = new SF.ContainerItem
                {
                    Item = new FormLink<SF.IItemGetter>(new FormKey(sf.ModKey, Mission.SfRaiderWeaponId)),
                    Count = 1,
                },
            });
        }
    }

    public static IEnumerable<(string Label, Action<SF.StarfieldMod> Mutate)> GetSelfTestMutations(ModKey raiderModKey)
    {
        yield return ("Preston SpaceOutfit left Null (2f DFOB spacesuit bug)",
            m => m.Npcs[new FormKey(m.ModKey, Mission.PrestonNpcId)].SpaceOutfit.Clear());
        yield return ("Preston retains non-zero UseTemplateActors",
            m => m.Npcs[new FormKey(m.ModKey, Mission.PrestonNpcId)].UseTemplateActors = (SF.Npc.TemplateActorType)0x6C12);
        yield return ("Preston lacks ActorShouldForceHideSpacesuit_AV == 1",
            m => m.Npcs[new FormKey(m.ModKey, Mission.PrestonNpcId)].Properties?.Clear());
        yield return ("Preston reverted to PapaKatz European pale face",
            m => m.Npcs[new FormKey(m.ModKey, Mission.PrestonNpcId)].SkinToneIndex = 4);
        yield return ("D2: FO4_AA_PrestonHat retains HasFaceBonesModel MO2F=1 (2g missing-hat bug)",
            m => m.ArmorAddons[new FormKey(m.ModKey, PrestonHatArmaId)].WorldModel!.Male!.Flags = (SF.Model.Flag)1);
        yield return ("D2: FO4_Armor_PrestonHat reverted to BO64=0x11 HEAD conflict",
            m => m.Armors[new FormKey(m.ModKey, PrestonHatArmoId)].FirstPersonFlags = (SF.FirstPersonFlag)0x11);
        yield return ("D2: FO4_AA_PrestonDuster missing Hands 0x40 mask (2g Still 07 bare-hands overlap)",
            m => m.ArmorAddons[new FormKey(m.ModKey, PrestonDusterArmaId)].FirstPersonFlags = SF.FirstPersonFlag.BODY);
        yield return ("A2.3: FO4SFMission overrides shared FO4ActorRaider.esm:0xF04800 globally",
            m => m.Npcs.Add(new SF.Npc(new FormKey(raiderModKey, Mission.RaiderId), SF.StarfieldRelease.Starfield)
            {
                EditorID = "FO4_LvlRaider",
                FormVersion = 581,
            }));
        yield return ("A2.3: FO4_ConcordRaider (0x986) reverted to Spacer spacesuit",
            m => m.Npcs[new FormKey(m.ModKey, ConcordRaiderNpcId)].SpaceOutfit.SetTo(new FormKey(SfEsm, SfSpacerSpacesuitOutfitId)));
        yield return ("A2.3: FO4_ConcordRaider (0x986) missing from FO4SFMission.esm",
            m => m.Npcs.Remove(new FormKey(m.ModKey, ConcordRaiderNpcId)));
        yield return ("R13 E3: FO4_ConcordRaider (0x986) retains TemplateActorType.Inventory",
            m => m.Npcs[new FormKey(m.ModKey, ConcordRaiderNpcId)].UseTemplateActors |= SF.Npc.TemplateActorType.Inventory);
        yield return ("R14 2g-fix6: FO4_ConcordRaider (0x986) retains TemplateActorType.AiData",
            m => m.Npcs[new FormKey(m.ModKey, ConcordRaiderNpcId)].UseTemplateActors |= SF.Npc.TemplateActorType.AiData);
        yield return ("R13 E3: FO4_ConcordRaider (0x986) retains vanilla Coachman in Items",
            m => (m.Npcs[new FormKey(m.ModKey, ConcordRaiderNpcId)].Items ??= new ExtendedList<SF.ContainerEntry>()).Add(new SF.ContainerEntry
            {
                Item = new SF.ContainerItem
                {
                    Item = new FormLink<SF.IItemGetter>(new FormKey(SfEsm, Mission.SfRaiderWeaponId)),
                    Count = 1,
                },
            }));
        yield return ("A2.3: Concord raider ACHR left pointing at shared 0xF04800 instead of 0x986",
            m =>
            {
                var r = Mission.PersistentNpcRefsMutable(m)
                    .FirstOrDefault(x => IsConcordRaiderRefId(x.FormKey, m.ModKey));
                r?.Base.SetTo(new FormKey(raiderModKey, Mission.RaiderId));
            });
        yield return ("Review #7: FO4_CorvegaBoss (0x0A23) SpaceOutfit reverted to 0x3D094D Spacer spacesuit",
            m =>
            {
                if (m.Npcs.TryGetValue(new FormKey(m.ModKey, CorvegaBossNpcId), out var n))
                    n.SpaceOutfit.SetTo(new FormKey(SfEsm, SfSpacerSpacesuitOutfitId));
            });
        yield return ("Review #7: FO4_Kellogg (0x0AD1) lacks ActorShouldForceHideSpacesuit_AV == 1",
            m =>
            {
                if (m.Npcs.TryGetValue(new FormKey(m.ModKey, KelloggNpcId), out var n))
                    n.Properties?.Clear();
            });
        yield return ("Review #7: FO4_CourserZ247 (0x0B31) DefaultOutfit set to 0x3D094D Spacer spacesuit",
            m =>
            {
                if (m.Npcs.TryGetValue(new FormKey(m.ModKey, CourserZ247NpcId), out var n))
                    n.DefaultOutfit.SetTo(new FormKey(SfEsm, SfSpacerSpacesuitOutfitId));
            });
    }

    /// <summary>
    /// Standalone C5 + Round 11 D2, A2.3 & Review #7 self-test callable from unit tests without modifying Program.cs:
    /// 1. Proves the 2f/9b5327ff state FAILS CheckActorLooks.
    /// 2. Applies ApplyActorLooks (with staged FO4 NIF model paths, 5 Concord raider ACHRs 0x803..0x807, the 3
    ///    later-mission FO4_LvlRaider-cloned bosses 0x0A23/0x0AD1/0x0B31 starting with SOFT=0x003D094D, and 1
    ///    non-Concord Corvega raider ACHR 0xA24 + FO4_Sturges 0xA00), writes binary FO4SFMission.esm, re-opens as
    ///    BinaryOverlay, and proves CheckActorLooks PASSES with 0 problems while non-raider actors stay untouched.
    /// 3. Proves every negative mutation in GetSelfTestMutations (including D2 MO2F=1, A2.3 global override, and
    ///    Review #7 later-mission boss 0x3D094D spacesuit regressions) is caught.
    /// </summary>
    public static void RunStandaloneSelfTest(string scratchDir)
    {
        Directory.CreateDirectory(scratchDir);
        var rel = SF.StarfieldRelease.Starfield;
        var sfKey = SfEsm;
        var coreKey = ModKey.FromFileName("FO4TerrainCore.esm");
        var raiderKey = ModKey.FromFileName("FO4ActorRaider.esm");
        var missionKey = ModKey.FromFileName("FO4SFMission.esm");

        var sf = new SF.StarfieldMod(sfKey, rel);
        sf.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var humanRace = new SF.Race(new FormKey(sfKey, Mission.SfHumanRaceId), rel)
        {
            EditorID = Mission.SfHumanRaceEdid,
            Flags = SF.Race.Flag.AllowPcDialog,
        };
        sf.Races.Add(humanRace);
        var maleVoice = new SF.VoiceType(new FormKey(sfKey, 0x013AD2), rel)
        {
            EditorID = Mission.SfPrestonVoiceEdid,
            Flags = SF.VoiceType.Flag.AllowDefaultDialog,
        };
        sf.VoiceTypes.Add(maleVoice);
        sf.Outfits.Add(new SF.Outfit(new FormKey(sfKey, Mission.SfPrestonOutfitId), rel) { EditorID = Mission.SfPrestonOutfitEdid });
        sf.Npcs.Add(new SF.Npc(new FormKey(sfKey, Mission.SfPapaKatzId), rel)
        {
            EditorID = Mission.SfPapaKatzEdid,
            Name = "Papa Katz",
            Race = new FormLink<SF.IRaceGetter>(humanRace.FormKey),
            Voice = new FormLinkNullable<SF.IVoiceTypeGetter>(maleVoice.FormKey),
        });

        var core = new SF.StarfieldMod(coreKey, rel);
        core.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var coreWorld = new SF.Worldspace(new FormKey(coreKey, 0x803), rel)
        {
            EditorID = Mission.World,
            TopCell = new SF.Cell(new FormKey(coreKey, 0x900), rel),
        };
        core.Worldspaces.Add(coreWorld);

        var raider = new SF.StarfieldMod(raiderKey, rel);
        raider.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        raider.Npcs.Add(new SF.Npc(new FormKey(raiderKey, Mission.RaiderId), rel)
        {
            EditorID = "FO4_LvlRaider",
            Name = "Raider",
            FormVersion = 581,
            Flags = SF.Npc.Flag.Respawn,
        });

        SeedSyntheticMasters(sf, raider, humanRace.FormKey, maleVoice.FormKey);

        var sfPath = Path.Combine(scratchDir, sfKey.FileName);
        sf.BeginWrite.ToPath(sfPath).WithNoLoadOrder().NoCheckIfLowerRangeDisallowed().Write();
        var corePath = Path.Combine(scratchDir, coreKey.FileName);
        core.BeginWrite.ToPath(corePath).WithLoadOrder(sfKey)
            .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();
        var raiderPath = Path.Combine(scratchDir, raiderKey.FileName);
        raider.BeginWrite.ToPath(raiderPath).WithLoadOrder(sfKey)
            .WithKnownMasters(new KeyedMasterStyle(sfKey, MasterStyle.Full)).Write();

        // Build simulated 9b5327ff (2f) FO4SFMission.esm BEFORE ApplyActorLooks
        var mod2f = new SF.StarfieldMod(missionKey, rel);
        mod2f.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var papa = sf.Npcs[new FormKey(sfKey, Mission.SfPapaKatzId)];
        var preston2f = (SF.Npc)papa.Duplicate(new FormKey(missionKey, Mission.PrestonNpcId));
        preston2f.EditorID = Mission.PrestonEdid;
        preston2f.DefaultOutfit.SetTo(new FormKey(sfKey, Mission.SfPrestonOutfitId));
        mod2f.Npcs.Add(preston2f);

        var styles = new BinaryReadParameters
        {
            MasterFlagsLookup = new Cache<IModMasterStyledGetter, ModKey>(x => x.ModKey)
            {
                new KeyedMasterStyle(sfKey, MasterStyle.Full),
                new KeyedMasterStyle(coreKey, MasterStyle.Full),
                new KeyedMasterStyle(raiderKey, MasterStyle.Full),
            },
        };
        var lo = new[] { sfKey, coreKey, raiderKey };
        var dir2f = Path.Combine(scratchDir, "buggy2f");
        Directory.CreateDirectory(dir2f);
        var path2f = Path.Combine(dir2f, missionKey.FileName);
        mod2f.BeginWrite.ToPath(path2f).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();

        using (var sfOv = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, rel))
        using (var plug2f = SF.StarfieldMod.CreateFromBinaryOverlay(path2f, rel, styles))
        {
            var probs2f = new List<string>();
            CheckActorLooks(plug2f, sfOv, raiderKey, probs2f);
            if (probs2f.Count < 4)
                throw new InvalidOperationException($"Expected 9b5327ff buggy plugin to fail >=4 C5 checks, got {probs2f.Count}");
        }

        // Build clean FO4SFMission.esm with Preston (0x801), FO4_Sturges (0xA00), the 3 later-mission FO4_LvlRaider-cloned
        // bosses (0x0A23 FO4_CorvegaBoss, 0x0AD1 FO4_Kellogg, 0x0B31 FO4_CourserZ247 starting with SOFT=0x003D094D),
        // 5 Concord raiders (0x803..0x807), and 1 non-Concord Corvega raider (0xA24) starting on FO4ActorRaider.esm:0xF04800.
        var modFixed = new SF.StarfieldMod(missionKey, rel);
        modFixed.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var prestonFixed = (SF.Npc)papa.Duplicate(new FormKey(missionKey, Mission.PrestonNpcId));
        prestonFixed.EditorID = Mission.PrestonEdid;
        prestonFixed.DefaultOutfit.SetTo(new FormKey(sfKey, Mission.SfPrestonOutfitId));
        modFixed.Npcs.Add(prestonFixed);

        var sturges = (SF.Npc)papa.Duplicate(new FormKey(missionKey, 0xA00));
        sturges.EditorID = "FO4_Sturges";
        modFixed.Npcs.Add(sturges);

        var sharedRaiderKey = new FormKey(raiderKey, Mission.RaiderId);
        foreach (var (laterId, laterEdid) in LaterRaiderClonedNpcs)
        {
            var laterBoss = (SF.Npc)raider.Npcs[sharedRaiderKey].Duplicate(new FormKey(missionKey, laterId));
            laterBoss.EditorID = laterEdid;
            laterBoss.FormVersion = 581;
            modFixed.Npcs.Add(laterBoss);
        }

        var cellFixed = new SF.Cell(new FormKey(missionKey, Mission.MissionHoldingCellId), rel)
        {
            EditorID = Mission.MissionHoldingCellEdid,
            Flags = SF.Cell.Flag.IsInteriorCell,
        };
        var subFixed = new SF.CellSubBlock { BlockNumber = (int)((Mission.MissionHoldingCellId / 10) % 10), GroupType = SF.GroupTypeEnum.InteriorCellSubBlock };
        subFixed.Cells.Add(cellFixed);
        var blkFixed = new SF.CellBlock { BlockNumber = (int)(Mission.MissionHoldingCellId % 10), GroupType = SF.GroupTypeEnum.InteriorCellBlock };
        blkFixed.SubBlocks.Add(subFixed);
        modFixed.Cells.Records.Add(blkFixed);
        for (uint i = 0; i < 5; i++)
        {
            var r = new SF.PlacedNpc(new FormKey(missionKey, Mission.FirstRaiderRefId + i), rel)
            {
                EditorID = $"FO4SF_Min00_RaiderREF_{i + 1}",
                MajorRecordFlagsRaw = 0x400,
            };
            r.Base.SetTo(sharedRaiderKey);
            cellFixed.Persistent.Add(r);
        }
        var corvegaRaiderRef = new SF.PlacedNpc(new FormKey(missionKey, 0xA24), rel)
        {
            EditorID = "FO4SF_Corvega_RaiderBossREF",
            MajorRecordFlagsRaw = 0x400,
        };
        corvegaRaiderRef.Base.SetTo(sharedRaiderKey);
        cellFixed.Persistent.Add(corvegaRaiderRef);

        var models = new ActorLooksModels(StagedPrestonOutfitModel, StagedPrestonHatModel, StagedRaiderOutfitModel);
        ApplyActorLooks(modFixed, sf, raider, models);

        if (!modFixed.Npcs[new FormKey(missionKey, 0xA00)].DefaultOutfit.IsNull ||
            !modFixed.Npcs[new FormKey(missionKey, 0xA00)].SpaceOutfit.IsNull ||
            modFixed.Npcs[new FormKey(missionKey, 0xA00)].UseTemplateActors != (SF.Npc.TemplateActorType)0x6C12)
        {
            throw new InvalidOperationException("ApplyActorLooks mutated non-C5 NPC FO4_Sturges");
        }
        if (corvegaRaiderRef.Base.FormKey != sharedRaiderKey)
        {
            throw new InvalidOperationException($"A2.3: ApplyActorLooks mutated non-Concord raider ACHR 0xA24 ({corvegaRaiderRef.Base.FormKey})");
        }

        var pathFixed = Path.Combine(scratchDir, missionKey.FileName);
        modFixed.BeginWrite.ToPath(pathFixed).WithLoadOrder(lo)
            .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();

        using (var sfOv = SF.StarfieldMod.CreateFromBinaryOverlay(sfPath, rel))
        {
            using (var plugFixed = SF.StarfieldMod.CreateFromBinaryOverlay(pathFixed, rel, styles))
            {
                var probsFixed = new List<string>();
                CheckActorLooks(plugFixed, sfOv, raiderKey, probsFixed, models);
                if (probsFixed.Count > 0)
                    throw new InvalidOperationException("Fixed FO4SFMission.esm failed CheckActorLooks: " + string.Join("; ", probsFixed));
            }

            var mutDir = Path.Combine(scratchDir, "mut");
            Directory.CreateDirectory(mutDir);
            foreach (var (label, mutate) in GetSelfTestMutations(raiderKey))
            {
                var copy = SF.StarfieldMod.CreateFromBinary(pathFixed, rel, styles);
                mutate(copy);
                var mutPath = Path.Combine(mutDir, missionKey.FileName);
                copy.BeginWrite.ToPath(mutPath).WithLoadOrder(lo)
                    .WithKnownMasters(lo.Select(k => new KeyedMasterStyle(k, MasterStyle.Full)).ToArray()).Write();
                using var mutOv = SF.StarfieldMod.CreateFromBinaryOverlay(mutPath, rel, styles);
                var mutProbs = new List<string>();
                CheckActorLooks(mutOv, sfOv, raiderKey, mutProbs, models);
                if (mutProbs.Count == 0)
                    throw new InvalidOperationException($"Mutation '{label}' unexpectedly passed CheckActorLooks");
            }
        }
    }
}
