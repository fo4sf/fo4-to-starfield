-- FO4SFCombat: SFSE combat hotkey sidecar (VATS slow-time key + New Vegas ammo-subtype cycle key) as an xmake
-- project in the shape of libxse/commonlibsf-template.
-- lib/commonlibsf is the libxse CommonLibSF checkout (pinned in build.ps1: 9d090c4, with its submodule
-- lib/commonlib-shared at 9fbb74d). The commonlibsf.plugin rule writes the SFSE version data: AddressLibraryV2,
-- the 1.14.70+ layout, CompatibleVersions RUNTIME_LATEST. Nothing in src/ redeclares it.
includes("lib/commonlibsf")

set_project("FO4SFCombat")
set_version("0.1.0")
set_license("GPL-3.0")
set_languages("c++23")
set_warnings("allextra")

add_rules("mode.debug", "mode.releasedbg")

target("FO4SFCombat", function()
    add_rules("commonlibsf.plugin", {
        name = "FO4SFCombat",
        author = "fo4sf",
        description = "CF-8 combat core input bridge: VATS targeting key and ammo subtype cycle key to FO4SF_CombatInput"
    })
    set_values("commonlib.plugin.install", false)

    add_files("src/**.cpp")
    add_headerfiles("src/**.h")
    add_includedirs("src")
    set_pcxxheader("src/pch.h")
end)
