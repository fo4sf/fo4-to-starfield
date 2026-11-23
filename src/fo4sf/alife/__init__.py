"""Starfield A-Life Modder SDK: the data layer and offline preview simulator.

  schema         load / validate / normalize a modder's A-Life JSON config and export the writer payload
  graph_builder  build, import and contract node graphs (CSV/TSV coordinate tables, marker JSON) into configs
  sim_math       deterministic pure-Python multi-squad simulator for balance previews
  presets/       ready-to-use configs (vanilla_new_atlantis.json, fo4sf_commonwealth.json)

Nothing in this package reads or writes a game folder; preset FormIDs are plain data.
"""
from .schema import (AlifeConfigError, SCHEMA_VERSION, export_writer_payload, load_alife_config, load_preset,
                     normalize_alife_config, preset_path, template_config, validate_alife_config)

__all__ = ["AlifeConfigError", "SCHEMA_VERSION", "export_writer_payload", "load_alife_config", "load_preset",
           "normalize_alife_config", "preset_path", "template_config", "validate_alife_config"]
