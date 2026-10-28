// FOCCPing: the B0 spike (docs/combined-core-cpp-port.md section 4, the owner's call of 28 Oct 2026: stack A first).
// One Papyrus native, FOCC.Ping(int v) -> v + 1, declared by scripts/combined_probes/FOCC.psc and called by
// FOCC_B0.Ping, bound here through CommonLibSF's Papyrus registration hook. It settles whether a value crosses from a
// quest script into our SFSE plugin and back on runtime 1.16.244, the link the C++ port stands on; it keeps no state.
//
// What it stands on (checked offline against CommonLibSF 9caec20, the commit on the PC):
//   - SFSE::Init loads the Address Library first (REL::IDDatabase: Data\SFSE\Plugins\versionlib-1-16-244-0.bin on
//     Steam; a missing file stops the game with a message box naming the path) and opens this plugin's log.
//   - SFSE::SetPapyrusCallback is a trampoline call hook at REL::ID(169912) + 0x514 inside GameVM::GameVM, the call
//     that binds everything to the script VM; the callback runs there with the VM. Whether that id resolves and the
//     offset holds on 1.16.244 is what the first launch tells (the library knows runtimes up to 1.14.74).
//   - A global native takes std::monostate in the self slot (RE/B/BSScriptUtil.h). BindNativeMethod's last two
//     arguments: callable from tasklets (true), latent (false).
// The kit's rule: a dll that keeps the game from the main menu is deleted at once (runbook section B0).

#include "Plugin.h"
#include "RE/Starfield.h"
#include "SFSE/SFSE.h"

namespace
{
	using namespace std::string_view_literals;

	// FOCC.psc: `int Function Ping(int v) global native`
	std::int32_t Ping(std::monostate, std::int32_t a_v)
	{
		SFSE::log::info("ping {} -> {}", a_v, a_v + 1);
		return a_v + 1;
	}

	void OnPapyrusInit(RE::BSScript::IVirtualMachine** a_vm)
	{
		if (!a_vm || !*a_vm) {
			SFSE::log::error("papyrus callback without a virtual machine: FOCC.Ping not bound");
			return;
		}
		(*a_vm)->BindNativeMethod("FOCC"sv, "Ping"sv, &Ping, true, false);
		SFSE::log::info("bound FOCC.Ping");
	}
}

SFSEPluginVersion = []() noexcept {
	SFSE::PluginVersionData data{};

	data.PluginVersion(Plugin::VERSION);
	data.PluginName(Plugin::NAME);
	data.AuthorName(Plugin::AUTHOR);
	data.UsesAddressLibrary(true);   // REL::ID in the Papyrus hook; the Address Library file is loaded by SFSE::Init
	data.IsLayoutDependent(true);    // CommonLibSF's game structures are the 1.14.70+ layout
	data.CompatibleVersions({ REL::Version{ 1, 16, 244, 0 } });

	return data;
}();

SFSEPluginLoad(const SFSE::LoadInterface* a_sfse)
{
	SFSE::Init(a_sfse);
	SFSE::log::info("{} {} loaded on runtime {}", Plugin::NAME, Plugin::VERSION.string(), a_sfse->RuntimeVersion().string());
	SFSE::SetPapyrusCallback(&OnPapyrusInit);
	SFSE::log::info("papyrus callback set; FOCC.Ping binds when the script VM starts");
	return true;
}
