#pragma once

// Pip-Boy screen source seam & shared wrist gate constants (Round 15 Wave A Item 1 / G5):
// Isolates how FO4SFPipboyMenu opens the Pip-Boy UI (2D IMenu overlay vs future 3D RTT surface)
// behind INI ScreenSource=2d_imenu|3d_rtt and 3-state GLOB FO4SF_PipboyScreenSource
// (0 = follow INI, 1 = force 2D IMenu, 2 = force 3D RTT) plus shared wrist keyword FO4SF_Kw_Pipboy
// in FO4SFCoreValues.esm (0x867 / 0x868), so shared DLL headers hold zero NewGame-plugin constants.

#include <cctype>
#include <cmath>
#include <cstdint>
#include <optional>
#include <string>
#include <string_view>
#include <utility>

namespace fo4sf::pipboy
{
	inline constexpr std::uint32_t    kPipboyKeywordLocalId = 0x867;
	inline constexpr std::string_view kPipboyKeywordPlugin = "FO4SFCoreValues.esm";
	inline constexpr std::string_view kPipboyKeywordEdid = "FO4SF_Kw_Pipboy";

	inline constexpr std::uint32_t    kPipboyScreenSourceGlobLocalId = 0x868;
	inline constexpr std::string_view kPipboyScreenSourcePlugin = "FO4SFCoreValues.esm";
	inline constexpr std::string_view kPipboyScreenSourceGlobEdid = "FO4SF_PipboyScreenSource";

	enum class ScreenSourceMode : std::uint8_t
	{
		k2DIMenu = 0,
		k3DRTT = 1,
	};

	struct ScreenOpenResult
	{
		ScreenSourceMode mode{ ScreenSourceMode::k2DIMenu };
		bool opened{ false };
		bool fellBackTo2D{ false };
		const char* reason{ "uninitialized" };
	};

	inline std::string_view TrimAsciiWhitespace(std::string_view a_text) noexcept
	{
		while (!a_text.empty() && std::isspace(static_cast<unsigned char>(a_text.front()))) {
			a_text.remove_prefix(1);
		}
		while (!a_text.empty() && std::isspace(static_cast<unsigned char>(a_text.back()))) {
			a_text.remove_suffix(1);
		}
		return a_text;
	}

	inline std::string ToLowerAscii(std::string_view a_text)
	{
		std::string out;
		out.reserve(a_text.size());
		for (const char ch : a_text) {
			out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
		}
		return out;
	}

	inline constexpr const char* ScreenSourceModeName(ScreenSourceMode a_mode) noexcept
	{
		return a_mode == ScreenSourceMode::k3DRTT ? "3d_rtt" : "2d_imenu";
	}

	// Parse ScreenSource=2d_imenu|3d_rtt from INI. Empty string defaults to k2DIMenu.
	// Returns std::nullopt on unrecognized tokens so INI loading can refuse cleanly.
	inline std::optional<ScreenSourceMode> ParseScreenSourceIni(std::string_view a_raw)
	{
		const auto trimmed = TrimAsciiWhitespace(a_raw);
		if (trimmed.empty()) {
			return ScreenSourceMode::k2DIMenu;
		}
		const auto low = ToLowerAscii(trimmed);
		if (low == "2d_imenu" || low == "2d" || low == "0") {
			return ScreenSourceMode::k2DIMenu;
		}
		if (low == "3d_rtt" || low == "3d" || low == "1") {
			return ScreenSourceMode::k3DRTT;
		}
		return std::nullopt;
	}

	// Resolve effective screen source from INI config and runtime 3-state FO4SF_PipboyScreenSource global:
	//   0 (or absent / < 0.5)  -> follow INI ScreenSource= (lets INI force 2D or 3D)
	//   1 (0.5 <= v < 1.5)     -> force 2D IMenu
	//   2 (v >= 1.5)           -> force 3D RTT
	inline ScreenSourceMode ResolvePipboyScreenSource(
		ScreenSourceMode a_iniMode,
		std::optional<float> a_globalValue = std::nullopt) noexcept
	{
		if (a_globalValue.has_value() && std::isfinite(*a_globalValue)) {
			if (*a_globalValue >= 1.5f) {
				return ScreenSourceMode::k3DRTT;
			}
			if (*a_globalValue >= 0.5f) {
				return ScreenSourceMode::k2DIMenu;
			}
		}
		return a_iniMode == ScreenSourceMode::k3DRTT ? ScreenSourceMode::k3DRTT : ScreenSourceMode::k2DIMenu;
	}

	// Single seam invoked by FO4SFPipboyMenu when opening the Pip-Boy screen.
	// Attempts 3D RTT when requested; falls back cleanly to 2D IMenu if 3D RTT returns false.
	template <typename Open2DFn, typename Open3DFn>
	inline ScreenOpenResult OpenPipboyScreenViaSource(
		ScreenSourceMode a_mode,
		Open2DFn&& a_open2D,
		Open3DFn&& a_open3D)
	{
		if (a_mode == ScreenSourceMode::k3DRTT) {
			if (std::forward<Open3DFn>(a_open3D)()) {
				return ScreenOpenResult{ ScreenSourceMode::k3DRTT, true, false, "ok_3d_rtt" };
			}
			const bool ok2d = std::forward<Open2DFn>(a_open2D)();
			return ScreenOpenResult{
				ScreenSourceMode::k2DIMenu,
				ok2d,
				true,
				ok2d ? "fallback_2d_imenu" : "failed_3d_and_2d"
			};
		}
		const bool ok2d = std::forward<Open2DFn>(a_open2D)();
		return ScreenOpenResult{
			ScreenSourceMode::k2DIMenu,
			ok2d,
			false,
			ok2d ? "ok_2d_imenu" : "failed_2d_imenu"
		};
	}
}
