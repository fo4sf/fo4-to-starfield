using System.Text.Json.Serialization;

namespace AuditBundle;

sealed class AuditReport
{
    [JsonPropertyName("bundle_dir")] public string BundleDir { get; init; } = "";
    [JsonPropertyName("port_esm")] public string PortEsm { get; init; } = "";
    [JsonPropertyName("map_markers_esm")] public string MapMarkersEsm { get; init; } = "";
    [JsonPropertyName("sf_data_dir")] public string? SfDataDir { get; init; }
    [JsonPropertyName("load_order")] public List<PluginHeaderInfo> LoadOrder { get; init; } = new();
    [JsonPropertyName("official_plugins")] public List<PluginHeaderInfo> OfficialPlugins { get; init; } = new();
    [JsonPropertyName("overrides")] public OverridesSection Overrides { get; init; } = new();
    [JsonPropertyName("shared_records")] public SharedRecordsSection SharedRecords { get; init; } = new();
    [JsonPropertyName("script_bindings")] public ScriptBindingsSection ScriptBindings { get; init; } = new();
    [JsonPropertyName("unprompted_execution")] public UnpromptedSection UnpromptedExecution { get; init; } = new();
    [JsonPropertyName("persistent_references")] public PersistentRefsSection PersistentReferences { get; init; } = new();
    [JsonPropertyName("starfield_leftovers")] public StarfieldLeftoversSection StarfieldLeftovers { get; init; } = new();
}

sealed class PluginHeaderInfo
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("category")] public string Category { get; init; } = "";
    [JsonPropertyName("slot_hex")] public string SlotHex { get; init; } = "";
    [JsonPropertyName("master_style")] public string MasterStyle { get; init; } = "";
    [JsonPropertyName("raw_header_flags")] public string RawHeaderFlags { get; init; } = "";
    [JsonPropertyName("size_bytes")] public long SizeBytes { get; init; }
    [JsonPropertyName("masters")] public List<string> Masters { get; init; } = new();
    [JsonPropertyName("missing_or_late_masters")] public List<string> MissingOrLateMasters { get; init; } = new();
    [JsonPropertyName("defining_records")] public int DefiningRecords { get; init; }
    [JsonPropertyName("override_records")] public int OverrideRecords { get; init; }
}

sealed class OverridesSection
{
    [JsonPropertyName("official_override_count")] public int OfficialOverrideCount { get; set; }
    [JsonPropertyName("our_cross_plugin_override_count")] public int OurCrossPluginOverrideCount { get; set; }
    [JsonPropertyName("by_plugin")] public Dictionary<string, int> ByPlugin { get; init; } = new();
    [JsonPropertyName("official_overrides")] public List<OverrideEntry> OfficialOverrides { get; init; } = new();
    [JsonPropertyName("our_cross_plugin_overrides")] public List<OverrideEntry> OurCrossPluginOverrides { get; init; } = new();
}

sealed class OverrideEntry
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("record_type")] public string RecordType { get; init; } = "";
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("target_owner")] public string TargetOwner { get; init; } = "";
    [JsonPropertyName("changes")] public List<string> Changes { get; init; } = new();
}

sealed class SharedRecordsSection
{
    [JsonPropertyName("focus_forms")] public List<SharedRecordEntry> FocusForms { get; init; } = new();
    [JsonPropertyName("all_shared_count")] public int AllSharedCount { get; set; }
    [JsonPropertyName("shared")] public List<SharedRecordEntry> Shared { get; init; } = new();
    [JsonPropertyName("map_marker_inventory")] public MapMarkerInventory MapMarkerInventory { get; init; } = new();
}

sealed class SharedRecordEntry
{
    [JsonPropertyName("label")] public string? Label { get; init; }
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("resolved_type")] public string? ResolvedType { get; init; }
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("detail")] public string? Detail { get; init; }
    [JsonPropertyName("defined_in")] public string? DefinedIn { get; init; }
    [JsonPropertyName("overridden_in")] public List<string> OverriddenIn { get; init; } = new();
    [JsonPropertyName("referenced_by_plugins")] public List<string> ReferencedByPlugins { get; init; } = new();
    [JsonPropertyName("script_getform_plugins")] public List<string> ScriptGetFormPlugins { get; init; } = new();
    [JsonPropertyName("plugin_touch_count")] public int PluginTouchCount { get; init; }
    [JsonPropertyName("reference_sites")] public List<string> ReferenceSites { get; init; } = new();
}

sealed class MapMarkerInventory
{
    [JsonPropertyName("core_marker_count")] public int CoreMarkerCount { get; set; }
    [JsonPropertyName("map_markers_plugin_own_count")] public int MapMarkersPluginOwnCount { get; set; }
    [JsonPropertyName("map_markers_quest_count")] public int MapMarkersQuestCount { get; set; }
    [JsonPropertyName("total_quest_array_slots")] public int TotalQuestArraySlots { get; set; }
    [JsonPropertyName("other_plugin_marker_count")] public int OtherPluginMarkerCount { get; set; }
    [JsonPropertyName("non_map_markers_in_quest_arrays")] public List<string> NonMapMarkersInQuestArrays { get; init; } = new();
    [JsonPropertyName("markers")] public List<MapMarkerDetail> Markers { get; init; } = new();
}

sealed class MapMarkerDetail
{
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("marker_name")] public string? MarkerName { get; init; }
    [JsonPropertyName("flags")] public string? Flags { get; init; }
    [JsonPropertyName("position")] public float[] Position { get; init; } = Array.Empty<float>();
    [JsonPropertyName("quest_owners")] public List<string> QuestOwners { get; init; } = new();
    [JsonPropertyName("other_script_refs")] public List<string> OtherScriptRefs { get; init; } = new();
}

sealed class ScriptBindingsSection
{
    [JsonPropertyName("total_script_entries")] public int TotalScriptEntries { get; set; }
    [JsonPropertyName("total_properties")] public int TotalProperties { get; set; }
    [JsonPropertyName("none_property_count")] public int NonePropertyCount { get; set; }
    [JsonPropertyName("unresolved_count")] public int UnresolvedCount { get; set; }
    [JsonPropertyName("cross_plugin_count")] public int CrossPluginCount { get; set; }
    [JsonPropertyName("missing_master_cross_plugin_count")] public int MissingMasterCrossPluginCount { get; set; }
    [JsonPropertyName("wrong_type_count")] public int WrongTypeCount { get; set; }
    [JsonPropertyName("flagged_bindings")] public List<ScriptBindingEntry> FlaggedBindings { get; init; } = new();
    [JsonPropertyName("all_scripts")] public List<ScriptSummaryEntry> AllScripts { get; init; } = new();
}

sealed class ScriptSummaryEntry
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("host_form_key")] public string HostFormKey { get; init; } = "";
    [JsonPropertyName("host_runtime_id")] public string HostRuntimeId { get; init; } = "";
    [JsonPropertyName("host_type")] public string HostType { get; init; } = "";
    [JsonPropertyName("host_editor_id")] public string? HostEditorId { get; init; }
    [JsonPropertyName("context")] public string Context { get; init; } = "";
    [JsonPropertyName("script_name")] public string ScriptName { get; init; } = "";
    [JsonPropertyName("property_count")] public int PropertyCount { get; init; }
    [JsonPropertyName("properties")] public List<ScriptPropertyEntry> Properties { get; init; } = new();
}

sealed class ScriptPropertyEntry
{
    [JsonPropertyName("name")] public string Name { get; init; } = "";
    [JsonPropertyName("kind")] public string Kind { get; init; } = "";
    [JsonPropertyName("declared_psc_type")] public string? DeclaredPscType { get; init; }
    [JsonPropertyName("value")] public string? Value { get; init; }
    [JsonPropertyName("targets")] public List<ScriptObjectTarget> Targets { get; init; } = new();
}

sealed class ScriptObjectTarget
{
    [JsonPropertyName("index")] public int? Index { get; init; }
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("alias")] public short Alias { get; init; }
    [JsonPropertyName("resolved_type")] public string? ResolvedType { get; init; }
    [JsonPropertyName("resolved_editor_id")] public string? ResolvedEditorId { get; init; }
    [JsonPropertyName("target_plugin")] public string TargetPlugin { get; init; } = "";
    [JsonPropertyName("flags")] public List<string> Flags { get; init; } = new();
}

sealed class ScriptBindingEntry
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("host_form_key")] public string HostFormKey { get; init; } = "";
    [JsonPropertyName("host_editor_id")] public string? HostEditorId { get; init; }
    [JsonPropertyName("context")] public string Context { get; init; } = "";
    [JsonPropertyName("script_name")] public string ScriptName { get; init; } = "";
    [JsonPropertyName("property_name")] public string PropertyName { get; init; } = "";
    [JsonPropertyName("declared_psc_type")] public string? DeclaredPscType { get; init; }
    [JsonPropertyName("index")] public int? Index { get; init; }
    [JsonPropertyName("target_form_key")] public string TargetFormKey { get; init; } = "";
    [JsonPropertyName("target_runtime_id")] public string TargetRuntimeId { get; init; } = "";
    [JsonPropertyName("target_plugin")] public string TargetPlugin { get; init; } = "";
    [JsonPropertyName("resolved_type")] public string? ResolvedType { get; init; }
    [JsonPropertyName("resolved_editor_id")] public string? ResolvedEditorId { get; init; }
    [JsonPropertyName("flags")] public List<string> Flags { get; init; } = new();
}

sealed class UnpromptedSection
{
    [JsonPropertyName("start_game_enabled_quests")] public List<StartQuestEntry> StartGameEnabledQuests { get; init; } = new();
    [JsonPropertyName("startup_quest_override")] public string? StartupQuestOverride { get; set; }
    [JsonPropertyName("attached_unprompted_scripts")] public List<UnpromptedScriptEntry> AttachedUnpromptedScripts { get; init; } = new();
    [JsonPropertyName("unattached_repo_scripts_with_hooks")] public List<UnpromptedScriptEntry> UnattachedRepoScriptsWithHooks { get; init; } = new();
}

sealed class StartQuestEntry
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("flags")] public string Flags { get; init; } = "";
    [JsonPropertyName("scripts")] public List<string> Scripts { get; init; } = new();
    [JsonPropertyName("alias_scripts")] public List<string> AliasScripts { get; init; } = new();
    [JsonPropertyName("stage_count")] public int StageCount { get; init; }
}

sealed class UnpromptedScriptEntry
{
    [JsonPropertyName("script_name")] public string ScriptName { get; init; } = "";
    [JsonPropertyName("psc_path")] public string? PscPath { get; init; }
    [JsonPropertyName("attached_to")] public List<string> AttachedTo { get; init; } = new();
    [JsonPropertyName("hooks")] public List<string> Hooks { get; init; } = new();
}

sealed class PersistentRefsSection
{
    [JsonPropertyName("total_persistent_refs")] public int TotalPersistentRefs { get; set; }
    [JsonPropertyName("by_plugin")] public Dictionary<string, int> ByPlugin { get; init; } = new();
    [JsonPropertyName("by_frame")] public Dictionary<string, int> ByFrame { get; init; } = new();
    [JsonPropertyName("refs")] public List<PersistentRefEntry> Refs { get; init; } = new();
}

sealed class PersistentRefEntry
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("is_override")] public bool IsOverride { get; init; }
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("record_kind")] public string RecordKind { get; init; } = "";
    [JsonPropertyName("base_form_key")] public string? BaseFormKey { get; init; }
    [JsonPropertyName("base_type")] public string? BaseType { get; init; }
    [JsonPropertyName("base_editor_id")] public string? BaseEditorId { get; init; }
    [JsonPropertyName("cell_form_key")] public string CellFormKey { get; init; } = "";
    [JsonPropertyName("cell_editor_id")] public string? CellEditorId { get; init; }
    [JsonPropertyName("worldspace_form_key")] public string? WorldspaceFormKey { get; init; }
    [JsonPropertyName("worldspace_editor_id")] public string? WorldspaceEditorId { get; init; }
    [JsonPropertyName("position")] public float[] Position { get; init; } = Array.Empty<float>();
    [JsonPropertyName("rotation")] public float[] Rotation { get; init; } = Array.Empty<float>();
    [JsonPropertyName("frame")] public string Frame { get; init; } = "";
    [JsonPropertyName("initially_disabled")] public bool InitiallyDisabled { get; init; }
    [JsonPropertyName("is_map_marker")] public bool IsMapMarker { get; init; }
    [JsonPropertyName("teleport_dest")] public string? TeleportDest { get; init; }
    [JsonPropertyName("script_count")] public int ScriptCount { get; init; }
}

sealed class StarfieldLeftoversSection
{
    [JsonPropertyName("official_lscr_total")] public int OfficialLscrTotal { get; set; }
    [JsonPropertyName("official_lscr_unconditional")] public int OfficialLscrUnconditional { get; set; }
    [JsonPropertyName("lscr_by_plugin")] public List<LscrPluginCount> LscrByPlugin { get; init; } = new();
    [JsonPropertyName("locations")] public List<NamedRecordInfo> Locations { get; init; } = new();
    [JsonPropertyName("worldspaces")] public List<NamedRecordInfo> Worldspaces { get; init; } = new();
    [JsonPropertyName("planets")] public List<NamedRecordInfo> Planets { get; init; } = new();
    [JsonPropertyName("messages")] public List<MessageRecordInfo> Messages { get; init; } = new();
    [JsonPropertyName("cells_named")] public List<NamedRecordInfo> CellsNamed { get; init; } = new();
}

sealed class LscrPluginCount
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("category")] public string Category { get; init; } = "";
    [JsonPropertyName("total")] public int Total { get; init; }
    [JsonPropertyName("unconditional")] public int Unconditional { get; init; }
    [JsonPropertyName("conditioned")] public int Conditioned { get; init; }
    [JsonPropertyName("overridden_by_ours")] public int OverriddenByOurs { get; init; }
}

sealed class NamedRecordInfo
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("is_override")] public bool IsOverride { get; init; }
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("name")] public string? Name { get; init; }
    [JsonPropertyName("detail")] public string? Detail { get; init; }
}

sealed class MessageRecordInfo
{
    [JsonPropertyName("plugin")] public string Plugin { get; init; } = "";
    [JsonPropertyName("form_key")] public string FormKey { get; init; } = "";
    [JsonPropertyName("runtime_id")] public string RuntimeId { get; init; } = "";
    [JsonPropertyName("is_override")] public bool IsOverride { get; init; }
    [JsonPropertyName("editor_id")] public string? EditorId { get; init; }
    [JsonPropertyName("title")] public string? Title { get; init; }
    [JsonPropertyName("description_preview")] public string? DescriptionPreview { get; init; }
    [JsonPropertyName("buttons")] public List<string> Buttons { get; init; } = new();
}
