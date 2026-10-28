#pragma once

// FOCCPing's name and version, as SFSE's version data and the log file name carry them (CommonLibSF names the log
// Documents\My Games\Starfield\SFSE\Logs\<plugin name>.log).
#include "SFSE/SFSE.h"

namespace Plugin
{
	using namespace std::string_view_literals;

	inline constexpr auto         NAME{ "FOCCPing"sv };
	inline constexpr auto         AUTHOR{ "fo4sf"sv };
	inline constexpr REL::Version VERSION{ 0, 1, 0, 0 };
}
