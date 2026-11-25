#pragma once

// Round 14 Task 2: Remove-menu hide switches (HideMenus) and generic Jobs Step 1 reader (DATA > QUESTS formID=0 group).
// Header-only to keep xmake.lua target globs zero-maintenance.

#include <array>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace fo4sf::menus_r14
{
	inline constexpr std::uint32_t kJobRowFormIdBase = 0xF0000001u;
	inline constexpr std::size_t   kHideMenuCount = 8;

	struct HideMenuSwitchSpec
	{
		const wchar_t* iniKey;
		const char*    menuName;
	};

	inline constexpr std::array<HideMenuSwitchSpec, kHideMenuCount> kHideMenuSpecs{ {
		{ L"HidePowersMenu", "PowersMenu" },
		{ L"HideAlmanacMenu", "AlmanacMenu" },
		{ L"HideResearchMenu", "ResearchMenu" },
		{ L"HideShipCrewMenu", "ShipCrewMenu" },
		{ L"HideShipCrewAssignMenu", "ShipCrewAssignMenu" },
		{ L"HideTakeoffMenu", "TakeoffMenu" },
		{ L"HideShipRefuelMenu", "ShipRefuelMenu" },
		{ L"HideWeaponGroupAssignmentMenu", "WeaponGroupAssignmentMenu" },
	} };

	struct JobRecord
	{
		std::string id;
		std::string title;
		std::string giver;
		std::string target;
		std::string rewardText;
		std::string status{ "available" };
		bool        active = true;
		bool        completed = false;
	};

	namespace detail
	{
		inline void SkipWs(std::string_view a_src, std::size_t& a_pos)
		{
			while (a_pos < a_src.size() && std::isspace(static_cast<unsigned char>(a_src[a_pos]))) {
				++a_pos;
			}
		}

		inline bool ParseJsonString(std::string_view a_src, std::size_t& a_pos, std::string& a_out)
		{
			a_out.clear();
			SkipWs(a_src, a_pos);
			if (a_pos >= a_src.size() || a_src[a_pos] != '"') {
				return false;
			}
			++a_pos;
			while (a_pos < a_src.size()) {
				const char c = a_src[a_pos++];
				if (c == '"') {
					return true;
				}
				if (c == '\\') {
					if (a_pos >= a_src.size()) {
						return false;
					}
					const char esc = a_src[a_pos++];
					switch (esc) {
					case '"': a_out.push_back('"'); break;
					case '\\': a_out.push_back('\\'); break;
					case '/': a_out.push_back('/'); break;
					case 'b': a_out.push_back('\b'); break;
					case 'f': a_out.push_back('\f'); break;
					case 'n': a_out.push_back('\n'); break;
					case 'r': a_out.push_back('\r'); break;
					case 't': a_out.push_back('\t'); break;
					case 'u':
						if (a_pos + 4 <= a_src.size()) {
							a_pos += 4;
							a_out.push_back('?');
						}
						break;
					default:
						a_out.push_back(esc);
						break;
					}
				} else {
					a_out.push_back(c);
				}
			}
			return false;
		}

		inline bool SkipJsonValue(std::string_view a_src, std::size_t& a_pos);

		inline bool SkipJsonComposite(std::string_view a_src, std::size_t& a_pos, char a_open, char a_close)
		{
			if (a_pos >= a_src.size() || a_src[a_pos] != a_open) {
				return false;
			}
			++a_pos;
			SkipWs(a_src, a_pos);
			if (a_pos < a_src.size() && a_src[a_pos] == a_close) {
				++a_pos;
				return true;
			}
			while (a_pos < a_src.size()) {
				if (a_open == '{') {
					std::string k;
					if (!ParseJsonString(a_src, a_pos, k)) {
						return false;
					}
					SkipWs(a_src, a_pos);
					if (a_pos >= a_src.size() || a_src[a_pos] != ':') {
						return false;
					}
					++a_pos;
				}
				if (!SkipJsonValue(a_src, a_pos)) {
					return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos < a_src.size() && a_src[a_pos] == ',') {
					++a_pos;
					continue;
				}
				if (a_pos < a_src.size() && a_src[a_pos] == a_close) {
					++a_pos;
					return true;
				}
				return false;
			}
			return false;
		}

		inline bool SkipJsonValue(std::string_view a_src, std::size_t& a_pos)
		{
			SkipWs(a_src, a_pos);
			if (a_pos >= a_src.size()) {
				return false;
			}
			const char c = a_src[a_pos];
			if (c == '"') {
				std::string dummy;
				return ParseJsonString(a_src, a_pos, dummy);
			}
			if (c == '{') {
				return SkipJsonComposite(a_src, a_pos, '{', '}');
			}
			if (c == '[') {
				return SkipJsonComposite(a_src, a_pos, '[', ']');
			}
			const std::size_t startPos = a_pos;
			while (a_pos < a_src.size()) {
				const char p = a_src[a_pos];
				if (p == ',' || p == '}' || p == ']' || std::isspace(static_cast<unsigned char>(p))) {
					break;
				}
				++a_pos;
			}
			return a_pos > startPos;
		}

		inline bool CaseEqual(std::string_view a_lhs, std::string_view a_rhs)
		{
			if (a_lhs.size() != a_rhs.size()) {
				return false;
			}
			for (std::size_t i = 0; i < a_lhs.size(); ++i) {
				if (std::tolower(static_cast<unsigned char>(a_lhs[i])) != std::tolower(static_cast<unsigned char>(a_rhs[i]))) {
					return false;
				}
			}
			return true;
		}

		inline bool ParseJobObject(std::string_view a_src, std::size_t& a_pos, JobRecord& a_out)
		{
			SkipWs(a_src, a_pos);
			if (a_pos >= a_src.size() || a_src[a_pos] != '{') {
				return false;
			}
			++a_pos;
			SkipWs(a_src, a_pos);
			if (a_pos < a_src.size() && a_src[a_pos] == '}') {
				++a_pos;
				return false;
			}
			while (a_pos < a_src.size()) {
				std::string key;
				if (!ParseJsonString(a_src, a_pos, key)) {
					return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos >= a_src.size() || a_src[a_pos] != ':') {
					return false;
				}
				++a_pos;
				SkipWs(a_src, a_pos);
				if (a_pos < a_src.size() && a_src[a_pos] == '"') {
					std::string val;
					if (!ParseJsonString(a_src, a_pos, val)) {
						return false;
					}
					if (key == "id") {
						a_out.id = std::move(val);
					} else if (key == "title") {
						a_out.title = std::move(val);
					} else if (key == "giver") {
						a_out.giver = std::move(val);
					} else if (key == "target") {
						a_out.target = std::move(val);
					} else if (key == "reward_text" || key == "rewardText" || key == "reward") {
						a_out.rewardText = std::move(val);
					} else if (key == "status") {
						a_out.status = std::move(val);
					}
				} else if (!SkipJsonValue(a_src, a_pos)) {
					return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos < a_src.size() && a_src[a_pos] == ',') {
					++a_pos;
					continue;
				}
				if (a_pos < a_src.size() && a_src[a_pos] == '}') {
					++a_pos;
					a_out.completed = CaseEqual(a_out.status, "completed") || CaseEqual(a_out.status, "done");
					a_out.active = !a_out.completed && !CaseEqual(a_out.status, "inactive");
					return !a_out.title.empty() || !a_out.id.empty();
				}
				return false;
			}
			return false;
		}
	}   // namespace detail

	// Parses either a top-level JSON array ([{...}, ...]) or {"jobs": [{...}, ...]}.
	// Unknown fields and extra wrapper keys are skipped cleanly so Claude's upcoming job schema drops straight in.
	inline std::vector<JobRecord> ParseJobsJsonText(std::string_view a_src)
	{
		std::vector<JobRecord> out;
		std::size_t pos = 0;
		detail::SkipWs(a_src, pos);
		if (pos >= a_src.size()) {
			return out;
		}
		if (a_src[pos] == '{') {
			++pos;
			bool foundArray = false;
			while (pos < a_src.size()) {
				detail::SkipWs(a_src, pos);
				if (pos < a_src.size() && a_src[pos] == '}') {
					break;
				}
				std::string key;
				if (!detail::ParseJsonString(a_src, pos, key)) {
					return out;
				}
				detail::SkipWs(a_src, pos);
				if (pos >= a_src.size() || a_src[pos] != ':') {
					return out;
				}
				++pos;
				detail::SkipWs(a_src, pos);
				if (key == "jobs" && pos < a_src.size() && a_src[pos] == '[') {
					foundArray = true;
					break;
				}
				if (!detail::SkipJsonValue(a_src, pos)) {
					return out;
				}
				detail::SkipWs(a_src, pos);
				if (pos < a_src.size() && a_src[pos] == ',') {
					++pos;
				}
			}
			if (!foundArray) {
				return out;
			}
		}
		if (pos >= a_src.size() || a_src[pos] != '[') {
			return out;
		}
		++pos;
		while (pos < a_src.size() && out.size() < 128) {
			const std::size_t loopStart = pos;
			detail::SkipWs(a_src, pos);
			if (pos >= a_src.size() || a_src[pos] == ']') {
				break;
			}
			JobRecord rec;
			if (a_src[pos] == '{') {
				if (detail::ParseJobObject(a_src, pos, rec)) {
					out.push_back(std::move(rec));
				}
			} else if (!detail::SkipJsonValue(a_src, pos)) {
				break;
			}
			detail::SkipWs(a_src, pos);
			if (pos < a_src.size() && a_src[pos] == ',') {
				++pos;
			} else if (pos < a_src.size() && a_src[pos] != ']' && pos == loopStart) {
				break;
			}
			if (pos <= loopStart) {
				break;
			}
		}
		return out;
	}

	inline std::vector<JobRecord> LoadJobsFromJsonFile(const std::filesystem::path& a_path)
	{
		std::ifstream in(a_path, std::ios::binary);
		if (!in) {
			return {};
		}
		std::ostringstream ss;
		ss << in.rdbuf();
		return ParseJobsJsonText(ss.str());
	}

	inline std::string FormatJobObjectiveLine(const JobRecord& a_job)
	{
		std::string line = !a_job.title.empty() ? a_job.title : a_job.id;
		if (!a_job.giver.empty()) {
			line += " — " + a_job.giver;
		}
		if (!a_job.target.empty()) {
			line += " (" + a_job.target + ")";
		}
		if (!a_job.rewardText.empty()) {
			line += " [" + a_job.rewardText + "]";
		}
		return line;
	}
}   // namespace fo4sf::menus_r14
