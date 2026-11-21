#pragma once

// Pure C++20 Start-Place Table parser and Variant (b) Setup Screen state machine (S1 / S3).
// Kept free of Starfield/SFSE headers so offline host tests can compile and verify 1:1 parity
// against `src/fo4sf/core/start_places.py` and `src/fo4sf/core/start_places.json`.

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <optional>
#include <sstream>
#include <string>
#include <string_view>
#include <vector>

namespace fo4sf::setup
{
	inline constexpr std::size_t kSetupRows = 5;
	inline constexpr std::array<std::string_view, 4> kDifficultyLabels{
		"EASY", "NORMAL", "HARD", "VERY HARD"
	};
	inline constexpr std::string_view kAllowedSetupGlyphs =
		" -.:/0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',()?!+%&_#=[]<>";

	struct StartPlaceRow
	{
		std::string id;
		std::string mode;            // "story" | "warfare"
		std::string storyId;         // e.g. "fo4_commonwealth" or "none"
		std::string storyLabel;      // e.g. "Fallout 4: Commonwealth"
		int         factionSlot = -1;
		std::string factionLabel;    // e.g. "Minutemen"
		std::string name;            // e.g. "Vault 111 (Commonwealth)"
		std::string warfareKey;
		int         minDifficulty = 0;
		int         maxDifficulty = 3;
		bool        available = false;
		std::string unavailableReason;
		int         warfareStartIndex = -1; // optional pre-resolved row index in warfare_starts.json
	};

	struct SetupCommitPayload
	{
		int         modeVal = 1;            // 1 = Story, 2 = Warfare -> FO4SF_GameMode (0x000870)
		std::string modeTag = "story";
		int         storyChoiceIdx = 0;     // 0..N-1 for Story, -1 for Warfare -> FO4SF_StoryLine (0x000878)
		std::string storyId = "fo4_commonwealth";
		int         survival = 0;           // 0 | 1 -> FO4SF_SurvivalStart (0x000871) & FO4SF_SurvivalLocked (0x000872)
		int         difficulty = 1;         // 0..3 -> FO4SF_StartDifficulty (0x000873)
		int         warfareFactionSlot = -1;// -1 for Story, 0..7 for Warfare -> FO4SF_WarfareFaction (0x000874)
		int         warfareStartIdx = -1;   // -1 for Story, canonical row index in warfare_starts.json (fallback: all warfare rows) -> FO4SF_WarfareStartIndex (0x000875)
		int         startPlaceRow = 0;      // 0..M-1 among available rows -> FO4SF_StartPlaceRow (0x000879)
		std::string placeId = "fo4_vault111";
	};

	inline std::string SanitizeSetupText(std::string_view a_raw, std::size_t a_maxCols = 68)
	{
		std::string out;
		out.reserve(std::min(a_raw.size(), a_maxCols));
		for (char ch : a_raw) {
			if (out.size() >= a_maxCols) {
				break;
			}
			const auto uc = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
			if (kAllowedSetupGlyphs.find(uc) != std::string_view::npos) {
				out.push_back(uc);
			} else {
				out.push_back(' ');
			}
		}
		return out;
	}

	namespace detail
	{
		inline void SkipWs(std::string_view a_src, std::size_t& a_pos)
		{
			while (a_pos < a_src.size() &&
			       (a_src[a_pos] == ' ' || a_src[a_pos] == '\t' || a_src[a_pos] == '\r' || a_src[a_pos] == '\n')) {
				++a_pos;
			}
		}

		inline bool ParseJsonString(std::string_view a_src, std::size_t& a_pos, std::string& a_out)
		{
			SkipWs(a_src, a_pos);
			if (a_pos >= a_src.size() || a_src[a_pos] != '"') {
				return false;
			}
			++a_pos;
			a_out.clear();
			while (a_pos < a_src.size()) {
				const char c = a_src[a_pos++];
				if (c == '"') {
					return true;
				}
				if (c == '\\' && a_pos < a_src.size()) {
					const char esc = a_src[a_pos++];
					switch (esc) {
					case '"': a_out.push_back('"'); break;
					case '\\': a_out.push_back('\\'); break;
					case '/': a_out.push_back('/'); break;
					case 'n': a_out.push_back(' '); break;
					case 'r': break;
					case 't': a_out.push_back(' '); break;
					default: a_out.push_back(esc); break;
					}
				} else {
					a_out.push_back(c);
				}
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
			if (c == '{' || c == '[') {
				const char open = c;
				const char close = (c == '{') ? '}' : ']';
				int        depth = 0;
				while (a_pos < a_src.size()) {
					const char ch = a_src[a_pos];
					if (ch == '"') {
						std::string dummy;
						if (!ParseJsonString(a_src, a_pos, dummy)) {
							return false;
						}
						continue;
					}
					++a_pos;
					if (ch == open) {
						++depth;
					} else if (ch == close) {
						if (--depth == 0) {
							return true;
						}
					}
				}
				return false;
			}
			while (a_pos < a_src.size() && a_src[a_pos] != ',' && a_src[a_pos] != '}' && a_src[a_pos] != ']' &&
			       a_src[a_pos] != ' ' && a_src[a_pos] != '\t' && a_src[a_pos] != '\r' && a_src[a_pos] != '\n') {
				++a_pos;
			}
			return true;
		}

		inline bool ParseJsonInt(std::string_view a_src, std::size_t& a_pos, int& a_out)
		{
			SkipWs(a_src, a_pos);
			const std::size_t start = a_pos;
			if (a_pos < a_src.size() && a_src[a_pos] == '-') {
				++a_pos;
			}
			while (a_pos < a_src.size() && std::isdigit(static_cast<unsigned char>(a_src[a_pos]))) {
				++a_pos;
			}
			if (a_pos == start || (a_pos == start + 1 && a_src[start] == '-')) {
				return false;
			}
			a_out = std::atoi(std::string(a_src.substr(start, a_pos - start)).c_str());
			return true;
		}

		inline bool ParseJsonBool(std::string_view a_src, std::size_t& a_pos, bool& a_out)
		{
			SkipWs(a_src, a_pos);
			if (a_src.substr(a_pos, 4) == "true") {
				a_out = true;
				a_pos += 4;
				return true;
			}
			if (a_src.substr(a_pos, 5) == "false") {
				a_out = false;
				a_pos += 5;
				return true;
			}
			return false;
		}

		inline bool ParsePlaceObject(std::string_view a_src, std::size_t& a_pos, StartPlaceRow& a_row)
		{
			SkipWs(a_src, a_pos);
			if (a_pos >= a_src.size() || a_src[a_pos] != '{') {
				return false;
			}
			++a_pos;
			a_row = StartPlaceRow{};
			for (;;) {
				SkipWs(a_src, a_pos);
				if (a_pos >= a_src.size()) {
					return false;
				}
				if (a_src[a_pos] == '}') {
					++a_pos;
					break;
				}
				std::string key;
				if (!ParseJsonString(a_src, a_pos, key)) {
					return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos >= a_src.size() || a_src[a_pos] != ':') {
					return false;
				}
				++a_pos;
				if (key == "id") {
					if (!ParseJsonString(a_src, a_pos, a_row.id)) return false;
				} else if (key == "mode") {
					if (!ParseJsonString(a_src, a_pos, a_row.mode)) return false;
				} else if (key == "story_id") {
					if (!ParseJsonString(a_src, a_pos, a_row.storyId)) return false;
				} else if (key == "story_label") {
					if (!ParseJsonString(a_src, a_pos, a_row.storyLabel)) return false;
				} else if (key == "faction_slot") {
					if (!ParseJsonInt(a_src, a_pos, a_row.factionSlot)) return false;
				} else if (key == "faction_label") {
					if (!ParseJsonString(a_src, a_pos, a_row.factionLabel)) return false;
				} else if (key == "name") {
					if (!ParseJsonString(a_src, a_pos, a_row.name)) return false;
				} else if (key == "warfare_key") {
					if (!ParseJsonString(a_src, a_pos, a_row.warfareKey)) return false;
				} else if (key == "min_difficulty") {
					if (!ParseJsonInt(a_src, a_pos, a_row.minDifficulty)) return false;
				} else if (key == "max_difficulty") {
					if (!ParseJsonInt(a_src, a_pos, a_row.maxDifficulty)) return false;
				} else if (key == "available") {
					if (!ParseJsonBool(a_src, a_pos, a_row.available)) return false;
				} else if (key == "unavailable_reason") {
					if (!ParseJsonString(a_src, a_pos, a_row.unavailableReason)) return false;
				} else {
					if (!SkipJsonValue(a_src, a_pos)) return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos < a_src.size() && a_src[a_pos] == ',') {
					++a_pos;
				}
			}
			return !a_row.id.empty() && (a_row.mode == "story" || a_row.mode == "warfare") && !a_row.name.empty();
		}

		inline bool ParseWarfareStartObject(std::string_view a_src, std::size_t& a_pos, std::string& a_keyOut)
		{
			SkipWs(a_src, a_pos);
			if (a_pos >= a_src.size() || a_src[a_pos] != '{') {
				return false;
			}
			++a_pos;
			a_keyOut.clear();
			for (;;) {
				SkipWs(a_src, a_pos);
				if (a_pos >= a_src.size()) {
					return false;
				}
				if (a_src[a_pos] == '}') {
					++a_pos;
					break;
				}
				std::string key;
				if (!ParseJsonString(a_src, a_pos, key)) {
					return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos >= a_src.size() || a_src[a_pos] != ':') {
					return false;
				}
				++a_pos;
				if (key == "key") {
					if (!ParseJsonString(a_src, a_pos, a_keyOut)) return false;
				} else {
					if (!SkipJsonValue(a_src, a_pos)) return false;
				}
				SkipWs(a_src, a_pos);
				if (a_pos < a_src.size() && a_src[a_pos] == ',') {
					++a_pos;
				}
			}
			return !a_keyOut.empty();
		}
	}   // namespace detail

	inline std::vector<StartPlaceRow> BuiltinFallbackStartPlaces()
	{
		return {
			StartPlaceRow{
				.id = "fo4_vault111",
				.mode = "story",
				.storyId = "fo4_commonwealth",
				.storyLabel = "Fallout 4: Commonwealth",
				.factionSlot = -1,
				.factionLabel = "",
				.name = "Vault 111 (Commonwealth)",
				.warfareKey = "",
				.minDifficulty = 0,
				.maxDifficulty = 3,
				.available = true,
				.unavailableReason = "",
			},
			StartPlaceRow{
				.id = "minutemen_sanctuary",
				.mode = "warfare",
				.storyId = "none",
				.storyLabel = "",
				.factionSlot = 0,
				.factionLabel = "Minutemen",
				.name = "Sanctuary Hills",
				.warfareKey = "minutemen_sanctuary",
				.minDifficulty = 0,
				.maxDifficulty = 3,
				.available = true,
				.unavailableReason = "",
			},
		};
	}

	inline bool ParseStartPlacesJsonText(std::string_view a_json, std::vector<StartPlaceRow>& a_out)
	{
		a_out.clear();
		std::size_t pos = 0;
		detail::SkipWs(a_json, pos);
		if (pos >= a_json.size() || a_json[pos] != '{') {
			return false;
		}
		++pos;
		for (;;) {
			detail::SkipWs(a_json, pos);
			if (pos >= a_json.size()) {
				return false;
			}
			if (a_json[pos] == '}') {
				break;
			}
			std::string topKey;
			if (!detail::ParseJsonString(a_json, pos, topKey)) {
				return false;
			}
			detail::SkipWs(a_json, pos);
			if (pos >= a_json.size() || a_json[pos] != ':') {
				return false;
			}
			++pos;
			if (topKey == "places") {
				detail::SkipWs(a_json, pos);
				if (pos >= a_json.size() || a_json[pos] != '[') {
					return false;
				}
				++pos;
				for (;;) {
					detail::SkipWs(a_json, pos);
					if (pos >= a_json.size()) {
						return false;
					}
					if (a_json[pos] == ']') {
						++pos;
						break;
					}
					StartPlaceRow row{};
					if (!detail::ParsePlaceObject(a_json, pos, row)) {
						return false;
					}
					if (!row.available && row.unavailableReason.empty()) {
						return false;
					}
					a_out.push_back(std::move(row));
					detail::SkipWs(a_json, pos);
					if (pos < a_json.size() && a_json[pos] == ',') {
						++pos;
					}
				}
			} else {
				if (!detail::SkipJsonValue(a_json, pos)) {
					return false;
				}
			}
			detail::SkipWs(a_json, pos);
			if (pos < a_json.size() && a_json[pos] == ',') {
				++pos;
			}
		}
		const bool hasStory = std::ranges::any_of(a_out, [](const auto& r) { return r.available && r.mode == "story"; });
		const bool hasWarfare = std::ranges::any_of(a_out, [](const auto& r) { return r.available && r.mode == "warfare"; });
		return hasStory && hasWarfare;
	}

	inline bool ParseWarfareStartKeysJsonText(std::string_view a_json, std::vector<std::string>& a_out)
	{
		a_out.clear();
		std::size_t pos = 0;
		detail::SkipWs(a_json, pos);
		if (pos >= a_json.size() || a_json[pos] != '{') {
			return false;
		}
		++pos;
		bool sawStarts = false;
		for (;;) {
			detail::SkipWs(a_json, pos);
			if (pos >= a_json.size()) {
				return false;
			}
			if (a_json[pos] == '}') {
				break;
			}
			std::string topKey;
			if (!detail::ParseJsonString(a_json, pos, topKey)) {
				return false;
			}
			detail::SkipWs(a_json, pos);
			if (pos >= a_json.size() || a_json[pos] != ':') {
				return false;
			}
			++pos;
			if (topKey == "starts") {
				sawStarts = true;
				detail::SkipWs(a_json, pos);
				if (pos >= a_json.size() || a_json[pos] != '[') {
					return false;
				}
				++pos;
				for (;;) {
					detail::SkipWs(a_json, pos);
					if (pos >= a_json.size()) {
						return false;
					}
					if (a_json[pos] == ']') {
						++pos;
						break;
					}
					std::string wfKey;
					if (!detail::ParseWarfareStartObject(a_json, pos, wfKey)) {
						return false;
					}
					if (std::ranges::find(a_out, wfKey) != a_out.end()) {
						return false;
					}
					a_out.push_back(std::move(wfKey));
					detail::SkipWs(a_json, pos);
					if (pos < a_json.size() && a_json[pos] == ',') {
						++pos;
					}
				}
			} else {
				if (!detail::SkipJsonValue(a_json, pos)) {
					return false;
				}
			}
			detail::SkipWs(a_json, pos);
			if (pos < a_json.size() && a_json[pos] == ',') {
				++pos;
			}
		}
		return sawStarts && !a_out.empty();
	}

	inline std::vector<std::string> LoadWarfareStartKeysFile(const std::filesystem::path& a_path)
	{
		std::ifstream in(a_path, std::ios::binary);
		if (in) {
			std::ostringstream ss;
			ss << in.rdbuf();
			std::vector<std::string> parsed;
			if (ParseWarfareStartKeysJsonText(ss.str(), parsed)) {
				return parsed;
			}
		}
		return {};
	}

	inline std::vector<std::string> LoadSiblingWarfareStartKeys(const std::filesystem::path& a_startPlacesPath)
	{
		const auto dir = a_startPlacesPath.parent_path();
		constexpr std::array<const char*, 2> kNames{ "FO4SFWarfareStarts.json", "warfare_starts.json" };
		for (const char* name : kNames) {
			auto keys = LoadWarfareStartKeysFile(dir / name);
			if (!keys.empty()) {
				return keys;
			}
		}
		return {};
	}

	inline void ApplyWarfareStartIndices(std::vector<StartPlaceRow>& a_rows, const std::vector<std::string>& a_warfareKeys)
	{
		if (a_warfareKeys.empty()) {
			return;
		}
		for (auto& row : a_rows) {
			if (row.mode != "warfare") {
				continue;
			}
			const std::string& key = row.warfareKey.empty() ? row.id : row.warfareKey;
			for (std::size_t i = 0; i < a_warfareKeys.size(); ++i) {
				if (a_warfareKeys[i] == key) {
					row.warfareStartIndex = static_cast<int>(i);
					break;
				}
			}
		}
	}

	inline std::vector<StartPlaceRow> LoadStartPlacesFileOrFallback(const std::filesystem::path& a_path, bool& a_fromFile)
	{
		a_fromFile = false;
		std::ifstream in(a_path, std::ios::binary);
		if (in) {
			std::ostringstream ss;
			ss << in.rdbuf();
			std::vector<StartPlaceRow> parsed;
			if (ParseStartPlacesJsonText(ss.str(), parsed)) {
				a_fromFile = true;
				ApplyWarfareStartIndices(parsed, LoadSiblingWarfareStartKeys(a_path));
				return parsed;
			}
		}
		return BuiltinFallbackStartPlaces();
	}

	class SetupScreenModel
	{
	public:
		struct StoryGroup
		{
			std::string storyId;
			std::string storyLabel;
			bool        available = false;
		};

		struct FactionGroup
		{
			std::string factionLabel;
			int         factionSlot = 0;
			bool        available = false;
		};

		void Reset(std::vector<StartPlaceRow> a_rows, bool a_showUnavailable, std::vector<std::string> a_warfareKeys = {})
		{
			_allRows = std::move(a_rows);
			_warfareKeys = std::move(a_warfareKeys);
			_availRows.clear();
			for (const auto& r : _allRows) {
				if (r.available) {
					_availRows.push_back(r);
				}
			}
			if (_availRows.empty()) {
				_allRows = BuiltinFallbackStartPlaces();
				_availRows = _allRows;
				_warfareKeys.clear();
			}
			_showUnavailable = a_showUnavailable;
			_visibleRows = _showUnavailable ? _allRows : _availRows;

			_selectedRow = 0;
			_modeVal = 1;
			_storyIdx = 0;
			_factionIdx = 0;
			_placeIdx = 0;
			_survival = 0;
			_difficulty = 1;
		}

		int  SelectedRow() const { return _selectedRow; }
		int  ModeVal() const { return _modeVal; }
		int  Survival() const { return _survival; }
		int  Difficulty() const { return _difficulty; }
		bool ShowUnavailable() const { return _showUnavailable; }
		std::size_t TotalRows() const { return _allRows.size(); }
		std::size_t AvailableRows() const { return _availRows.size(); }

		void SelectRow(int a_row)
		{
			_selectedRow = std::clamp(a_row, 0, static_cast<int>(kSetupRows) - 1);
		}

		void MoveCursor(int a_delta)
		{
			_selectedRow = std::clamp(_selectedRow + a_delta, 0, static_cast<int>(kSetupRows) - 1);
		}

		void AdjustRow(int a_row, int a_delta)
		{
			if (a_delta == 0) {
				return;
			}
			const int step = (a_delta > 0) ? 1 : -1;
			if (a_row == 0) {
				_modeVal = (_modeVal == 1) ? 2 : 1;
				_placeIdx = 0;
			} else if (a_row == 1) {
				if (_modeVal == 1) {
					const auto groups = StoryGroups();
					if (!groups.empty()) {
						const int n = static_cast<int>(groups.size());
						_storyIdx = ((_storyIdx + step) % n + n) % n;
					}
				} else {
					const auto fgroups = FactionGroups();
					if (!fgroups.empty()) {
						const int n = static_cast<int>(fgroups.size());
						_factionIdx = ((_factionIdx + step) % n + n) % n;
					}
				}
				_placeIdx = 0;
			} else if (a_row == 2) {
				const auto places = PlacesForCurrentGroup();
				if (!places.empty()) {
					const int n = static_cast<int>(places.size());
					_placeIdx = ((_placeIdx + step) % n + n) % n;
				}
			} else if (a_row == 3) {
				_survival = _survival ? 0 : 1;
			} else if (a_row == 4) {
				_difficulty = ((_difficulty + step) % 4 + 4) % 4;
				const auto places = PlacesForCurrentGroup();
				if (_placeIdx >= static_cast<int>(places.size())) {
					_placeIdx = 0;
				}
			}
		}

		StartPlaceRow CurrentPlaceRow() const
		{
			const auto places = PlacesForCurrentGroup();
			if (places.empty()) {
				return _availRows.front();
			}
			const int idx = std::clamp(_placeIdx, 0, static_cast<int>(places.size()) - 1);
			return places[static_cast<std::size_t>(idx)];
		}

		void RenderLines(std::array<std::string, kSetupRows>& a_rows, std::string& a_status) const
		{
			const auto cur = CurrentPlaceRow();
			const auto mark = [this](int idx) -> std::string_view {
				return (_selectedRow == idx) ? "> " : "  ";
			};
			const std::string_view modeTxt = (_modeVal == 1) ? "STORY" : "WARFARE";

			std::string row1;
			if (_modeVal == 1) {
				const auto groups = StoryGroups();
				const auto& g = groups[static_cast<std::size_t>(std::clamp(_storyIdx, 0, static_cast<int>(groups.size()) - 1))];
				row1 = std::string(mark(1)) + "STORY LINE: " + (g.available ? "" : "[LOCKED] ") + g.storyLabel;
			} else {
				const auto fgroups = FactionGroups();
				const auto& fg = fgroups[static_cast<std::size_t>(std::clamp(_factionIdx, 0, static_cast<int>(fgroups.size()) - 1))];
				row1 = std::string(mark(1)) + "FACTION: " + (fg.available ? "" : "[LOCKED] ") + fg.factionLabel;
			}

			a_rows[0] = SanitizeSetupText(std::string(mark(0)) + "MODE: " + std::string(modeTxt));
			a_rows[1] = SanitizeSetupText(row1);
			a_rows[2] = SanitizeSetupText(std::string(mark(2)) + "START PLACE: " + (cur.available ? "" : "[LOCKED] ") + cur.name);
			a_rows[3] = SanitizeSetupText(std::string(mark(3)) + "SURVIVAL: " + (_survival ? "ON" : "OFF"));
			a_rows[4] = SanitizeSetupText(std::string(mark(4)) + "DIFFICULTY: " +
			                              std::string(kDifficultyLabels[static_cast<std::size_t>(_difficulty)]));

			if (cur.available) {
				a_status = "READY: PRESS CONFIRM (ENTER) TO BEGIN";
			} else {
				a_status = SanitizeSetupText("LOCKED: " + cur.unavailableReason, 96);
			}
		}

		std::optional<SetupCommitPayload> Confirm() const
		{
			const auto cur = CurrentPlaceRow();
			if (!cur.available) {
				return std::nullopt;
			}

			int availPlaceIdx = 0;
			for (std::size_t i = 0; i < _availRows.size(); ++i) {
				if (_availRows[i].id == cur.id) {
					availPlaceIdx = static_cast<int>(i);
					break;
				}
			}

			if (_modeVal == 1) {
				int storyChoiceIdx = 0;
				std::vector<std::string> seenStories;
				for (const auto& r : _availRows) {
					if (r.mode == "story" && std::ranges::find(seenStories, r.storyId) == seenStories.end()) {
						if (r.storyId == cur.storyId) {
							storyChoiceIdx = static_cast<int>(seenStories.size());
						}
						seenStories.push_back(r.storyId);
					}
				}
				return SetupCommitPayload{
					.modeVal = 1,
					.modeTag = "story",
					.storyChoiceIdx = storyChoiceIdx,
					.storyId = cur.storyId,
					.survival = _survival,
					.difficulty = _difficulty,
					.warfareFactionSlot = -1,
					.warfareStartIdx = -1,
					.startPlaceRow = availPlaceIdx,
					.placeId = cur.id,
				};
			}

			const int wfIdx = ResolveWarfareStartIdx(cur);
			return SetupCommitPayload{
				.modeVal = 2,
				.modeTag = "warfare",
				.storyChoiceIdx = -1,
				.storyId = "none",
				.survival = _survival,
				.difficulty = _difficulty,
				.warfareFactionSlot = cur.factionSlot,
				.warfareStartIdx = wfIdx,
				.startPlaceRow = availPlaceIdx,
				.placeId = cur.id,
			};
		}

	private:
		int ResolveWarfareStartIdx(const StartPlaceRow& a_cur) const
		{
			const std::string& key = a_cur.warfareKey.empty() ? a_cur.id : a_cur.warfareKey;
			if (!_warfareKeys.empty()) {
				for (std::size_t i = 0; i < _warfareKeys.size(); ++i) {
					if (_warfareKeys[i] == key) {
						return static_cast<int>(i);
					}
				}
			}
			if (a_cur.warfareStartIndex >= 0) {
				return a_cur.warfareStartIndex;
			}
			int wfCount = 0;
			for (const auto& r : _allRows) {
				if (r.mode == "warfare") {
					const std::string& rKey = r.warfareKey.empty() ? r.id : r.warfareKey;
					if (rKey == key || r.id == a_cur.id) {
						return wfCount;
					}
					++wfCount;
				}
			}
			return 0;
		}

		std::vector<StoryGroup> StoryGroups() const
		{
			std::vector<StoryGroup> out;
			for (const auto& r : _visibleRows) {
				if (r.mode != "story") {
					continue;
				}
				auto it = std::ranges::find_if(out, [&](const StoryGroup& g) { return g.storyId == r.storyId; });
				if (it == out.end()) {
					out.push_back({ r.storyId, r.storyLabel, r.available });
				} else if (r.available) {
					it->available = true;
				}
			}
			return out;
		}

		std::vector<FactionGroup> FactionGroups() const
		{
			std::vector<FactionGroup> out;
			for (const auto& r : _visibleRows) {
				if (r.mode != "warfare") {
					continue;
				}
				auto it = std::ranges::find_if(out, [&](const FactionGroup& g) { return g.factionLabel == r.factionLabel; });
				if (it == out.end()) {
					out.push_back({ r.factionLabel, r.factionSlot, r.available });
				} else if (r.available) {
					it->available = true;
				}
			}
			return out;
		}

		std::vector<StartPlaceRow> PlacesForCurrentGroup() const
		{
			std::vector<StartPlaceRow> out;
			if (_modeVal == 1) {
				const auto groups = StoryGroups();
				if (groups.empty()) {
					return out;
				}
				const auto& sid = groups[static_cast<std::size_t>(std::clamp(_storyIdx, 0, static_cast<int>(groups.size()) - 1))].storyId;
				for (const auto& r : _visibleRows) {
					if (r.mode == "story" && r.storyId == sid) {
						out.push_back(r);
					}
				}
				return out;
			}
			const auto fgroups = FactionGroups();
			if (fgroups.empty()) {
				return out;
			}
			const auto& flabel = fgroups[static_cast<std::size_t>(std::clamp(_factionIdx, 0, static_cast<int>(fgroups.size()) - 1))].factionLabel;
			for (const auto& r : _visibleRows) {
				if (r.mode == "warfare" && r.factionLabel == flabel &&
				    r.minDifficulty <= _difficulty && _difficulty <= r.maxDifficulty) {
					out.push_back(r);
				}
			}
			if (!out.empty()) {
				return out;
			}
			for (const auto& r : _visibleRows) {
				if (r.mode == "warfare" && r.factionLabel == flabel) {
					out.push_back(r);
				}
			}
			return out;
		}

		std::vector<StartPlaceRow> _allRows;
		std::vector<StartPlaceRow> _availRows;
		std::vector<StartPlaceRow> _visibleRows;
		std::vector<std::string>   _warfareKeys;
		bool                       _showUnavailable = false;
		int                        _selectedRow = 0;
		int                        _modeVal = 1;
		int                        _storyIdx = 0;
		int                        _factionIdx = 0;
		int                        _placeIdx = 0;
		int                        _survival = 0;
		int                        _difficulty = 1;
	};
}   // namespace fo4sf::setup
