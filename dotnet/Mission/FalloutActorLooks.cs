// FalloutActorLooks: Round 10 C5 actor looks & spacesuit stripping for FO4SFMission.esm.
//
// Why Preston (0x000801) and the 5 Concord raiders (FO4ActorRaider.esm:0xF04800) wore Starfield spacesuits in 2f:
//   1. Preston duplicated Starfield.esm:0x01169C (UC_NA_PapaKatz), leaving SpaceOutfit (SOFT) = Null,
//      UseTemplateActors = 0x6C12 non-zero, and ActorShouldForceHideSpacesuit_AV (0x000B120E) unset (0.0).
//      In Starfield.esm, DFOB 0x001A76BD (DefaultSpaceSuitOutfit_DO) supplies OTFT 0x0016D5E5
//      (Outfit_Spacesuit_DefaultNPC_NoBoostpack_NOTPLAYABLE) whenever a HumanRace NPC has SpaceOutfit = Null,
//      and on MarsPlanetWorld (PNDT 0x0003F59A, non-breathable CO2) CNDF 0x00194ABF + CNDF 0x000BEA53 evaluate TRUE.
//   2. FO4ActorRaider.esm:0xF04800 (FO4_LvlRaider) explicitly authored SpaceOutfit (SOFT) = 0x003D094D
//      (Outfit_Spacesuit_Spacer_AssaultOrNoRole) with ActorShouldForceHideSpacesuit_AV unset.
//
// C5 Triple-Lock Spacesuit Strip + Fallout 4 Outfit & Face Architecture (local FormIDs 0x980..0x98A):
//   - Sets AVIF 0x000B120E (ActorShouldForceHideSpacesuit_AV) = 1.0f in NPC_.Properties (PRPS), making CNDF 0x00194ABF
//     condition [1] (GetValue(0x0B120E) != 1) evaluate FALSE on MarsPlanetWorld and every non-breathable world.
//   - Sets BOTH DefaultOutfit (DOFT) and SpaceOutfit (SOFT) explicitly to non-spacesuit clothes Outfits (defeating
//     DFOB 0x001A76BD and preventing any ArmorTypeSpacesuitBody/Helmet/Backpack item from entering NPC inventory).
//   - Clears stale UseTemplateActors bits on standalone NPCs and emits an override of FO4ActorRaider.esm:0xF04800
//     (FO4_LvlRaider, FormVersion 581) in FO4SFMission.esm so all 5 placed Concord raiders (0x803..0x807) keep their
//     exact Base FormKey while switching from Spacer spacesuits to FO4_Outfit_ConcordRaider (0x988).
//   - Applies Preston Garvey's Fallout 4 (0x00019FD9) young African-American male face/hair/beard/weight traits
//     (sourced from Starfield.esm 0x0ED1C4 EncFreestarSecurityFaceM04 + 0x15F5A6 Human_Male_Beard_ClassicBeard) and
//     dedicated Minuteman duster + hat records (0x980..0x985), followed by FO4_Outfit_ConcordRaider (0x988..0x98A).

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
    /// Applies C5 Fallout 4 outfits, Preston's Fallout 4 face/hair/beard/weight traits, FO4_LvlRaider (0xF04800)
    /// override, and Triple-Lock Starfield spacesuit/helmet stripping across FO4SFMission.esm.
    /// Call once in Mission.Write after NPCs are populated and before mod.BeginWrite.
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

        // 3. Override FO4ActorRaider.esm:0xF04800 (FO4_LvlRaider) in FO4SFMission.esm so all 5 Concord raiders
        //    keep their exact Base FormKey while switching from Spacer spacesuits to FO4_Outfit_ConcordRaider (0x988)
        var baseRaider = raiderMod.Npcs.FirstOrDefault(n => n.FormKey.ID == Mission.RaiderId && n.EditorID == "FO4_LvlRaider")
                         ?? throw new InvalidOperationException($"{raiderMod.ModKey} missing 0x{Mission.RaiderId:X6} FO4_LvlRaider");
        var raiderOverrideKey = new FormKey(raiderMod.ModKey, Mission.RaiderId);
        mod.Npcs.Remove(raiderOverrideKey);
        var raiderOverride = baseRaider.DeepCopy();
        raiderOverride.FormVersion = 581;
        raiderOverride.DefaultOutfit.SetTo(raiderOutfit.FormKey);
        raiderOverride.SpaceOutfit.SetTo(raiderOutfit.FormKey);
        EnforceNoStarfieldSpacesuit(raiderOverride, sfMod, forceHideAvKey, raiderOutfit.FormKey, preserveIntentionalTemplates: true);
        mod.Npcs.Add(raiderOverride);

        // 4. Enforce Triple-Lock spacesuit/helmet stripping across every remaining HumanRace NPC in FO4SFMission.esm
        var fallbackFriendlyOutfitKey = prestonOutfit.FormKey;
        if (sfMod.Outfits.TryGetValue(new FormKey(SfEsm, Mission.SfPrestonOutfitId), out var rangerOutfit))
            fallbackFriendlyOutfitKey = rangerOutfit.FormKey;

        foreach (var otherNpc in mod.Npcs)
        {
            if (otherNpc.FormKey == preston.FormKey || otherNpc.FormKey == raiderOverride.FormKey)
                continue;
            if (otherNpc.Race.FormKey != humanRaceKey)
                continue;

            bool isRaiderBoss = (otherNpc.EditorID ?? "").Contains("Raider", StringComparison.OrdinalIgnoreCase) ||
                                (otherNpc.EditorID ?? "").Contains("CorvegaBoss", StringComparison.OrdinalIgnoreCase);
            FormKey desiredClothes = isRaiderBoss
                ? raiderOutfit.FormKey
                : (!otherNpc.DefaultOutfit.IsNull && !IsSpacesuitOutfit(otherNpc.DefaultOutfit.FormKey, sfMod, mod)
                    ? otherNpc.DefaultOutfit.FormKey
                    : fallbackFriendlyOutfitKey);

            EnforceNoStarfieldSpacesuit(otherNpc, sfMod, forceHideAvKey, desiredClothes);
        }

        if (mod.ModHeader.Stats.NextFormID < MaxAllocatedId)
            mod.ModHeader.Stats.NextFormID = MaxAllocatedId;
    }

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

        var raiderArma = DuplicateOrCreateBodyArma(mod, sfMod, RaiderBodyArmaId, RaiderBodyArmaEdid, humanRaceKey, raiderOutfitModel);
        var raiderArmo = DuplicateOrCreateApparelArmo(
            mod, sfMod, RaiderBodyArmoId, RaiderBodyArmoEdid, "Raider Scavenger Outfit", humanRaceKey,
            isHeadwear: false, raiderArma.FormKey);

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
        string? customNifRelPath)
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
                FirstPersonFlags = SF.FirstPersonFlag.BODY,
                WorldModel = new GenderedItem<SF.Model?>(
                    new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Actors\\Human\\Mesh\\Naked_Body\\Naked_M.nif") },
                    new SF.Model { File = new AssetLink<StarfieldModelAssetType>("Actors\\Human\\Mesh\\Naked_Body\\Naked_F.nif") }),
            };
        }

        arma.EditorID = edid;
        arma.Race.SetTo(humanRaceKey);
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
        if (!string.IsNullOrWhiteSpace(customHatNifRelPath))
            SetWorldModels(arma, customHatNifRelPath);

        mod.ArmorAddons.Remove(key);
        mod.ArmorAddons.Add(arma);
        return arma;
    }

    static void SetWorldModels(SF.ArmorAddon arma, string maleRel, string? femaleRel = null)
    {
        arma.WorldModel ??= new GenderedItem<SF.Model?>(new SF.Model(), new SF.Model());
        arma.WorldModel.Male ??= new SF.Model();
        arma.WorldModel.Female ??= new SF.Model();
        string baseGiven = arma.WorldModel.Male.File?.GivenPath ?? "";
        arma.WorldModel.Male.File = new AssetLink<StarfieldModelAssetType>(Mission.ModelPath(baseGiven, maleRel));
        arma.WorldModel.Female.File = new AssetLink<StarfieldModelAssetType>(Mission.ModelPath(baseGiven, femaleRel ?? maleRel));
    }

    static SF.Armor DuplicateOrCreateApparelArmo(
        SF.StarfieldMod mod,
        SF.IStarfieldModGetter sfMod,
        uint localId,
        string edid,
        string displayName,
        FormKey humanRaceKey,
        bool isHeadwear,
        FormKey armaKey)
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
                FirstPersonFlags = isHeadwear ? (SF.FirstPersonFlag)0 : SF.FirstPersonFlag.BODY,
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
    /// Validates all C5 binary invariants on the written FO4SFMission.esm plugin.
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

        // 1. Local Fallout 4 Outfit / Armor / ArmorAddon records (0x980..0x98A)
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

        // 3. FO4ActorRaider.esm:0xF04800 (FO4_LvlRaider) override in FO4SFMission.esm
        var raiderKey = new FormKey(raiderModKey, Mission.RaiderId);
        var raiderOverride = plug.Npcs.FirstOrDefault(n => n.FormKey == raiderKey);
        Need(raiderOverride is { EditorID: "FO4_LvlRaider", FormVersion: 581 },
             $"FO4SFMission.esm lacks FormVersion=581 override for {raiderKey} (FO4_LvlRaider)");
        if (raiderOverride is not null)
        {
            Need(raiderOverride.DefaultOutfit.FormKey == new FormKey(key, RaiderOutfitId),
                 $"FO4_LvlRaider override DefaultOutfit ({raiderOverride.DefaultOutfit.FormKey}) != 0x{RaiderOutfitId:X}");
            Need(raiderOverride.SpaceOutfit.FormKey == new FormKey(key, RaiderOutfitId),
                 $"FO4_LvlRaider override SpaceOutfit ({raiderOverride.SpaceOutfit.FormKey}) != 0x{RaiderOutfitId:X}");
            Need(HasForceHideSpacesuitProperty(raiderOverride, forceHideAvKey),
                 $"FO4_LvlRaider override lacks {SfForceHideSpacesuitAvEdid} (0x{SfForceHideSpacesuitAvId:X6}) == 1.0");
        }

        // 4. Global rule across all HumanRace NPCs in FO4SFMission.esm: zero spacesuits on MarsPlanetWorld
        foreach (var npc in plug.Npcs)
        {
            if (npc.Race.FormKey != humanRaceKey)
                continue;
            Need(!npc.DefaultOutfit.IsNull && !IsSpacesuitOutfit(npc.DefaultOutfit.FormKey, sfMod, plug),
                 $"HumanRace NPC {npc.EditorID} ({npc.FormKey}) has null or spacesuit DefaultOutfit ({npc.DefaultOutfit.FormKey})");
            Need(!npc.SpaceOutfit.IsNull && !IsSpacesuitOutfit(npc.SpaceOutfit.FormKey, sfMod, plug),
                 $"HumanRace NPC {npc.EditorID} ({npc.FormKey}) has null or spacesuit SpaceOutfit ({npc.SpaceOutfit.FormKey})");
            Need(HasForceHideSpacesuitProperty(npc, forceHideAvKey),
                 $"HumanRace NPC {npc.EditorID} ({npc.FormKey}) lacks {SfForceHideSpacesuitAvEdid} == 1.0");
            if (npc.Items is not null)
            {
                Need(!npc.Items.Any(i => IsSpacesuitItem(i.Item.Item.FormKey, sfMod, plug)),
                     $"HumanRace NPC {npc.EditorID} ({npc.FormKey}) carries a Starfield spacesuit item in inventory");
            }
        }
    }

    public static bool HasForceHideSpacesuitProperty(SF.INpcGetter npc, FormKey forceHideAvKey)
        => npc.Properties is not null &&
           npc.Properties.Any(p => p.ActorValue.FormKey == forceHideAvKey && MathF.Abs(p.Value - 1.0f) < 1e-4f);

    /// <summary>
    /// Seeds synthetic Starfield.esm & FO4ActorRaider.esm records needed to test C5 spacesuit stripping & Preston face.
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
        yield return ("FO4_LvlRaider override reverted to Spacer spacesuit",
            m => m.Npcs[new FormKey(raiderModKey, Mission.RaiderId)].SpaceOutfit.SetTo(new FormKey(SfEsm, SfSpacerSpacesuitOutfitId)));
        yield return ("FO4_LvlRaider override missing from FO4SFMission.esm",
            m => m.Npcs.Remove(new FormKey(raiderModKey, Mission.RaiderId)));
    }

    /// <summary>
    /// Standalone C5 self-test callable from unit tests without modifying Program.cs:
    /// 1. Proves the 2f/9b5327ff state (Preston SpaceOutfit=Null + PapaKatz face, Raider SpaceOutfit=0x3D094D) FAILS CheckActorLooks.
    /// 2. Applies ApplyActorLooks (with staged FO4 NIF model paths), writes binary FO4SFMission.esm, re-opens as BinaryOverlay,
    ///    and proves CheckActorLooks PASSES with 0 problems.
    /// 3. Proves every negative mutation in GetSelfTestMutations is caught by CheckActorLooks.
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
        var lo = new[] { sfKey, raiderKey };
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

        // Now apply C5 fix on a clean FO4SFMission.esm with staged Fallout 4 NIF paths + companion Sturges & CorvegaBoss NPCs
        var modFixed = new SF.StarfieldMod(missionKey, rel);
        modFixed.ModHeader.Flags |= SF.StarfieldModHeader.HeaderFlag.Master;
        var prestonFixed = (SF.Npc)papa.Duplicate(new FormKey(missionKey, Mission.PrestonNpcId));
        prestonFixed.EditorID = Mission.PrestonEdid;
        prestonFixed.DefaultOutfit.SetTo(new FormKey(sfKey, Mission.SfPrestonOutfitId));
        modFixed.Npcs.Add(prestonFixed);

        var sturges = (SF.Npc)papa.Duplicate(new FormKey(missionKey, 0xA00));
        sturges.EditorID = "FO4_Sturges";
        modFixed.Npcs.Add(sturges);

        var corvegaBoss = (SF.Npc)papa.Duplicate(new FormKey(missionKey, 0xA23));
        corvegaBoss.EditorID = "FO4_CorvegaBoss";
        modFixed.Npcs.Add(corvegaBoss);

        var models = new ActorLooksModels(StagedPrestonOutfitModel, StagedPrestonHatModel, StagedRaiderOutfitModel);
        ApplyActorLooks(modFixed, sf, raider, models);

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
                    throw new InvalidOperationException("Fixed FO4SFMission.esm failed C5 CheckActorLooks: " + string.Join("; ", probsFixed));
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
                    throw new InvalidOperationException($"C5 mutation '{label}' unexpectedly passed CheckActorLooks");
            }
        }
    }
}
