#pragma once

// Shared Starfield registered blocking-menu guard (Task 1 step 1d).
// Included by both FO4SFPipboyMenu (F7, M, and open-menu cancel/navigation) and FO4SFCombat (V, N) so every hotkey
// checks ONE canonical list derived from Starfield 1.16.244.0's registered UIStringHolder / MENU_NAME strings.
// Note: FaderMenu is intentionally excluded because Starfield keeps FaderMenu open across normal gameplay transitions.

#include <array>
#include <atomic>
#include <string>
#include <vector>

namespace fo4sf
{
	inline constexpr const char* kOurPipboyMenuName = "FO4SF_PipboyMenu";
	inline constexpr const char* kOurSpecialMenuName = "FO4SF_SpecialMenu";
	inline constexpr const char* kOurStartCardMenuName = "FO4SF_StartCardMenu";
	inline constexpr const char* kOurSetupMenuName = "FO4SF_SetupMenu";

	// First kTopModalMenuCount entries are top-level modal / text-entry overlays that take priority even when
	// FO4SF_PipboyMenu is already open underneath them.
	inline constexpr std::size_t kTopModalMenuCount = 8;

	inline constexpr std::array<const char*, 38> kBlockingMenus{ {
		// Top modal & text-input overlays (indices 0 .. kTopModalMenuCount - 1)
		"Console",
		"ConsoleNativeUIMenu",
		"TextInputMenu",
		"MessageBoxMenu",
		"PauseMenu",
		"MainMenu",
		"LoadingMenu",
		"LoadingMenuNewLocation",
		// Character creation & dialogue (including FO4SF_SpecialMenu)
		"FO4SF_SpecialMenu",
		"ChargenMenu",
		"DialogueMenu",
		"ShipDialogueMenu",
		// Scanner, digipick, character/data/skills/status
		"MonocleMenu",
		"SecurityMenu",
		"SkillsMenu",
		"StatusMenu",
		"InventoryMenu",
		"DataMenu",
		"BSMissionMenu",
		// Containers, trade, interaction
		"ContainerMenu",
		"BarterMenu",
		"PickpocketMenu",
		// Workshop, ship builder, photo mode
		"WorkshopMenu",
		"WorkshopBuilderMenu",
		"WorkshopQuickMenu",
		"Workshop_BlueprintMenu",
		"PhotoModeMenu",
		"SpaceshipEditorMenu",
		// Starfield map menus
		"GalaxyStarMapMenu",
		"SurfaceMap",
		"MapMenu",
		// Everyday & terminal menus
		"SleepWaitMenu",
		"SitWaitMenu",
		"FavoritesMenu",
		"BookMenu",
		"GenesisTerminalMenu",
		"LockpickingMenu",
		"TerminalMenu",
	} };

	inline const std::vector<RE::BSFixedString>& BlockingMenusFixed()
	{
		static const auto* const list = [] {
			auto* out = new std::vector<RE::BSFixedString>();
			out->reserve(kBlockingMenus.size());
			for (const auto* name : kBlockingMenus) {
				out->emplace_back(name);
			}
			return out;
		}();
		return *list;
	}

	inline const RE::BSFixedString& OurPipboyMenuFixed()
	{
		static const auto* const s = new RE::BSFixedString(kOurPipboyMenuName);
		return *s;
	}

	inline const RE::BSFixedString& OurSetupMenuFixed()
	{
		static const auto* const s = new RE::BSFixedString(kOurSetupMenuName);
		return *s;
	}

	inline void LogRegisteredMenusOnce(RE::UI* a_ui)
	{
		if (!a_ui) {
			return;
		}
		static std::atomic<bool> logged{ false };
		if (logged.exchange(true)) {
			return;
		}
		const auto& names = BlockingMenusFixed();
		std::string registered;
		std::size_t regCount = 0;
		for (std::size_t i = 0; i < names.size(); ++i) {
			if (a_ui->IsMenuRegistered(names[i])) {
				if (!registered.empty()) {
					registered += ',';
				}
				registered += kBlockingMenus[i];
				++regCount;
			}
		}
		REX::INFO("step=menu_guard registered={} count={}/{}",
			registered.empty() ? "none" : registered, regCount, kBlockingMenus.size());
	}

	inline const char* FindOpenBlockingMenu(RE::UI* a_ui, bool a_topModalOnly = false, bool a_includeOurPipboy = false)
	{
		if (!a_ui) {
			return nullptr;
		}
		LogRegisteredMenusOnce(a_ui);
		const auto&       names = BlockingMenusFixed();
		const std::size_t limit = a_topModalOnly ? kTopModalMenuCount : names.size();
		for (std::size_t i = 0; i < limit; ++i) {
			if (a_ui->IsMenuRegistered(names[i]) && a_ui->IsMenuOpen(names[i])) {
				return kBlockingMenus[i];
			}
		}
		if (!a_topModalOnly) {
			const auto& setup = OurSetupMenuFixed();
			if (a_ui->IsMenuRegistered(setup) && a_ui->IsMenuOpen(setup)) {
				return kOurSetupMenuName;
			}
		}
		if (!a_topModalOnly && a_includeOurPipboy) {
			const auto& our = OurPipboyMenuFixed();
			if (a_ui->IsMenuRegistered(our) && a_ui->IsMenuOpen(our)) {
				return kOurPipboyMenuName;
			}
		}
		return nullptr;
	}
}
