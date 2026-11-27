#pragma once

// Pure C++20 HUD Quest/Mission label rewrite helper and INI setting parser.
// Kept free of Starfield/SFSE headers so offline host tests can compile and verify it directly.
// Reads [FO4SFPipboyMenu] settings:
//   ReplaceMissionLabel=1   (0/1 toggle; default 1 for FO4)
//   QuestHudLabel=QUEST     (replacement label for Starfield's "MISSION" HUD toast header; default "QUEST")

#include <algorithm>
#include <array>
#include <cctype>
#include <cstdint>
#include <filesystem>
#include <format>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>
#include <utility>
#include <vector>

namespace fo4sf::hud
{
	inline constexpr std::string_view kDefaultQuestHudLabel = "QUEST";
	inline constexpr std::size_t      kMaxQuestHudLabelLen = 32;
	inline constexpr std::size_t      kTranslateTargetKeyCount = 20;

	struct QuestLabelConfig
	{
		bool        replaceMissionLabel = true;
		std::string questHudLabel{ kDefaultQuestHudLabel };

		[[nodiscard]] bool Active() const noexcept
		{
			return replaceMissionLabel && !questHudLabel.empty();
		}

		[[nodiscard]] std::string_view Mode() const noexcept
		{
			return Active() ? "quest" : "mission";
		}
	};

	struct TranslateFileStatus
	{
		bool        filePresent{ false };
		bool        fileOk{ false };
		std::size_t keysMatched{ 0 };
		std::size_t keysExpected{ kTranslateTargetKeyCount };
	};

	namespace detail
	{
		inline std::string_view TrimWs(std::string_view a_sv) noexcept
		{
			while (!a_sv.empty() &&
			       (a_sv.front() == ' ' || a_sv.front() == '\t' || a_sv.front() == '\r' || a_sv.front() == '\n')) {
				a_sv.remove_prefix(1);
			}
			while (!a_sv.empty() &&
			       (a_sv.back() == ' ' || a_sv.back() == '\t' || a_sv.back() == '\r' || a_sv.back() == '\n')) {
				a_sv.remove_suffix(1);
			}
			return a_sv;
		}

		inline bool EqualsIgnoreCase(std::string_view a_lhs, std::string_view a_rhs) noexcept
		{
			if (a_lhs.size() != a_rhs.size()) {
				return false;
			}
			for (std::size_t i = 0; i < a_lhs.size(); ++i) {
				if (std::tolower(static_cast<unsigned char>(a_lhs[i])) !=
				    std::tolower(static_cast<unsigned char>(a_rhs[i]))) {
					return false;
				}
			}
			return true;
		}

		inline bool ParseToggle(std::string_view a_val, bool a_default) noexcept
		{
			const auto v = TrimWs(a_val);
			if (v.empty()) {
				return a_default;
			}
			if (v == "1" || EqualsIgnoreCase(v, "true") || EqualsIgnoreCase(v, "yes") || EqualsIgnoreCase(v, "on")) {
				return true;
			}
			if (v == "0" || EqualsIgnoreCase(v, "false") || EqualsIgnoreCase(v, "no") || EqualsIgnoreCase(v, "off")) {
				return false;
			}
			return a_default;
		}

		inline std::string SanitizeHudLabel(std::string_view a_raw)
		{
			auto s = TrimWs(a_raw);
			if (s.size() >= 2 && ((s.front() == '"' && s.back() == '"') || (s.front() == '\'' && s.back() == '\''))) {
				s = TrimWs(s.substr(1, s.size() - 2));
			}
			std::string out;
			out.reserve(std::min(s.size(), kMaxQuestHudLabelLen));
			for (const char ch : s) {
				if (out.size() >= kMaxQuestHudLabelLen) {
					break;
				}
				const auto uc = static_cast<unsigned char>(ch);
				if (std::isalnum(uc) || ch == ' ' || ch == '_' || ch == '-') {
					out.push_back(ch);
				}
			}
			const auto trimmed = TrimWs(out);
			if (trimmed.empty()) {
				return std::string(kDefaultQuestHudLabel);
			}
			return std::string(trimmed);
		}

		inline std::string ToUpperAscii(std::string_view a_sv)
		{
			std::string out(a_sv);
			for (char& ch : out) {
				ch = static_cast<char>(std::toupper(static_cast<unsigned char>(ch)));
			}
			return out;
		}

		inline std::string ToTitleWords(std::string_view a_sv)
		{
			std::string out;
			out.reserve(a_sv.size());
			bool newWord = true;
			for (const char ch : a_sv) {
				const auto uc = static_cast<unsigned char>(ch);
				if (ch == ' ' || ch == '\t' || ch == '_' || ch == '-') {
					out.push_back(ch);
					newWord = true;
				} else if (newWord) {
					out.push_back(static_cast<char>(std::toupper(uc)));
					newWord = false;
				} else {
					out.push_back(static_cast<char>(std::tolower(uc)));
				}
			}
			return out;
		}

		inline std::string ToPluralUpperAscii(std::string_view a_sv)
		{
			std::string u = ToUpperAscii(a_sv);
			if (u.empty()) {
				return "QUESTS";
			}
			if (u.ends_with('S') || u.ends_with('X') || u.ends_with('Z') || u.ends_with("CH") || u.ends_with("SH")) {
				u += "ES";
			} else if (u.ends_with('Y') && u.size() > 1 &&
			           std::string_view("AEIOU").find(u[u.size() - 2]) == std::string_view::npos) {
				u.pop_back();
				u += "IES";
			} else {
				u.push_back('S');
			}
			return u;
		}

		inline std::string DecodeTranslateText(std::string_view a_raw)
		{
			std::string out;
			if (a_raw.size() >= 2 && static_cast<unsigned char>(a_raw[0]) == 0xFF &&
			    static_cast<unsigned char>(a_raw[1]) == 0xFE) {
				out.reserve((a_raw.size() - 2) / 2);
				for (std::size_t i = 2; i + 1 < a_raw.size(); i += 2) {
					const std::uint16_t ch = static_cast<unsigned char>(a_raw[i]) |
					                         (static_cast<unsigned char>(a_raw[i + 1]) << 8);
					out.push_back(ch < 0x80 ? static_cast<char>(ch) : '?');
				}
				return out;
			}
			if (a_raw.size() >= 2 && static_cast<unsigned char>(a_raw[0]) == 0xFE &&
			    static_cast<unsigned char>(a_raw[1]) == 0xFF) {
				out.reserve((a_raw.size() - 2) / 2);
				for (std::size_t i = 2; i + 1 < a_raw.size(); i += 2) {
					const std::uint16_t ch = (static_cast<unsigned char>(a_raw[i]) << 8) |
					                         static_cast<unsigned char>(a_raw[i + 1]);
					out.push_back(ch < 0x80 ? static_cast<char>(ch) : '?');
				}
				return out;
			}
			if (a_raw.size() >= 3 && static_cast<unsigned char>(a_raw[0]) == 0xEF &&
			    static_cast<unsigned char>(a_raw[1]) == 0xBB && static_cast<unsigned char>(a_raw[2]) == 0xBF) {
				a_raw.remove_prefix(3);
			}
			return std::string(a_raw);
		}
		inline bool ReadU16Le(const unsigned char* a_p, std::uint16_t& a_out) noexcept
		{
			a_out = static_cast<std::uint16_t>(a_p[0]) | (static_cast<std::uint16_t>(a_p[1]) << 8);
			return true;
		}

		inline std::uint32_t ReadU32Le(const unsigned char* a_p) noexcept
		{
			return static_cast<std::uint32_t>(a_p[0]) | (static_cast<std::uint32_t>(a_p[1]) << 8) |
			       (static_cast<std::uint32_t>(a_p[2]) << 16) | (static_cast<std::uint32_t>(a_p[3]) << 24);
		}

		inline std::uint64_t ReadU64Le(const unsigned char* a_p) noexcept
		{
			std::uint64_t v = 0;
			for (int i = 0; i < 8; ++i) {
				v |= static_cast<std::uint64_t>(a_p[i]) << (8 * i);
			}
			return v;
		}

		inline std::string NormalizeArchiveEntryName(std::string_view a_name)
		{
			std::string out;
			out.reserve(a_name.size());
			for (char ch : a_name) {
				if (ch == '\\') {
					ch = '/';
				}
				if (out.empty() && ch == '/') {
					continue;
				}
				out.push_back(static_cast<char>(std::tolower(static_cast<unsigned char>(ch))));
			}
			return out;
		}

		inline bool ReadUncompressedBa2Entry(
			const std::filesystem::path& a_ba2Path,
			std::string_view             a_targetNormalized,
			std::string&                 a_outBytes)
		{
			std::error_code ec;
			const auto      fileSize = std::filesystem::file_size(a_ba2Path, ec);
			if (ec || fileSize < 24) {
				return false;
			}
			std::ifstream in(a_ba2Path, std::ios::binary);
			if (!in) {
				return false;
			}
			std::array<unsigned char, 24> hdr{};
			if (!in.read(reinterpret_cast<char*>(hdr.data()), hdr.size())) {
				return false;
			}
			if (hdr[0] != 'B' || hdr[1] != 'T' || hdr[2] != 'D' || hdr[3] != 'X') {
				return false;
			}
			if (hdr[8] != 'G' || hdr[9] != 'N' || hdr[10] != 'R' || hdr[11] != 'L') {
				return false;
			}
			const auto version = ReadU32Le(hdr.data() + 4);
			std::size_t extra = 0;
			if (version == 2) {
				extra = 8;
			} else if (version == 3) {
				extra = 12;
			} else if (version != 1 && version != 7 && version != 8) {
				return false;
			}
			const auto count = ReadU32Le(hdr.data() + 12);
			const auto nameOff = ReadU64Le(hdr.data() + 16);
			if (count == 0 || count > 1000000u || nameOff < 24ull + extra || nameOff >= fileSize) {
				return false;
			}
			in.seekg(static_cast<std::streamoff>(nameOff));
			if (!in) {
				return false;
			}
			std::uint32_t matchIdx = count;
			for (std::uint32_t i = 0; i < count; ++i) {
				std::array<unsigned char, 2> lenBuf{};
				if (!in.read(reinterpret_cast<char*>(lenBuf.data()), lenBuf.size())) {
					return false;
				}
				std::uint16_t nameLen = 0;
				ReadU16Le(lenBuf.data(), nameLen);
				if (nameLen == 0 || nameLen > 4096) {
					return false;
				}
				std::string entryName(nameLen, '\0');
				if (!in.read(entryName.data(), nameLen)) {
					return false;
				}
				if (NormalizeArchiveEntryName(entryName) == a_targetNormalized) {
					matchIdx = i;
					break;
				}
			}
			if (matchIdx >= count) {
				return false;
			}
			const std::uint64_t recOff = 24ull + extra + static_cast<std::uint64_t>(matchIdx) * 36ull;
			if (recOff + 36ull > fileSize) {
				return false;
			}
			in.seekg(static_cast<std::streamoff>(recOff));
			std::array<unsigned char, 36> rec{};
			if (!in.read(reinterpret_cast<char*>(rec.data()), rec.size())) {
				return false;
			}
			const auto dataOffset = ReadU64Le(rec.data() + 16);
			const auto packed = ReadU32Le(rec.data() + 24);
			const auto unpacked = ReadU32Le(rec.data() + 28);
			if (packed != 0 || unpacked == 0 || dataOffset + unpacked > fileSize) {
				return false;
			}
			in.seekg(static_cast<std::streamoff>(dataOffset));
			a_outBytes.assign(unpacked, '\0');
			return static_cast<bool>(in.read(a_outBytes.data(), unpacked));
		}

		inline bool StartsWithIgnoreCase(std::string_view a_sv, std::string_view a_prefix) noexcept
		{
			if (a_sv.size() < a_prefix.size()) {
				return false;
			}
			return EqualsIgnoreCase(a_sv.substr(0, a_prefix.size()), a_prefix);
		}

		inline bool EndsWithIgnoreCase(std::string_view a_sv, std::string_view a_suffix) noexcept
		{
			if (a_sv.size() < a_suffix.size()) {
				return false;
			}
			return EqualsIgnoreCase(a_sv.substr(a_sv.size() - a_suffix.size()), a_suffix);
		}
	}   // namespace detail

	/// Parse [FO4SFPipboyMenu] ReplaceMissionLabel and QuestHudLabel from raw INI text.
	[[nodiscard]] inline QuestLabelConfig ParseQuestLabelIniText(std::string_view a_iniText)
	{
		QuestLabelConfig cfg;
		bool             inSection = false;
		std::size_t      pos = 0;

		while (pos <= a_iniText.size()) {
			const auto nextNl = a_iniText.find('\n', pos);
			const auto rawLine = (nextNl == std::string_view::npos)
			                         ? a_iniText.substr(pos)
			                         : a_iniText.substr(pos, nextNl - pos);
			pos = (nextNl == std::string_view::npos) ? a_iniText.size() + 1 : nextNl + 1;

			const auto line = detail::TrimWs(rawLine);
			if (line.empty() || line.front() == ';' || line.front() == '#') {
				continue;
			}
			if (line.front() == '[' && line.back() == ']') {
				const auto sec = detail::TrimWs(line.substr(1, line.size() - 2));
				inSection = detail::EqualsIgnoreCase(sec, "FO4SFPipboyMenu");
				continue;
			}
			if (!inSection) {
				continue;
			}
			const auto eq = line.find('=');
			if (eq == std::string_view::npos) {
				continue;
			}
			const auto key = detail::TrimWs(line.substr(0, eq));
			auto       val = detail::TrimWs(line.substr(eq + 1));
			if (const auto semi = val.find(';'); semi != std::string_view::npos) {
				val = detail::TrimWs(val.substr(0, semi));
			}

			if (detail::EqualsIgnoreCase(key, "ReplaceMissionLabel")) {
				cfg.replaceMissionLabel = detail::ParseToggle(val, cfg.replaceMissionLabel);
			} else if (detail::EqualsIgnoreCase(key, "QuestHudLabel")) {
				cfg.questHudLabel = detail::SanitizeHudLabel(val);
			}
		}
		return cfg;
	}

	/// Load QuestLabelConfig from an INI file path; falls back to defaults if the file does not exist.
	[[nodiscard]] inline QuestLabelConfig LoadQuestLabelConfig(const std::filesystem::path& a_iniPath)
	{
		std::ifstream in(a_iniPath, std::ios::binary);
		if (!in) {
			return QuestLabelConfig{};
		}
		std::ostringstream ss;
		ss << in.rdbuf();
		return ParseQuestLabelIniText(ss.str());
	}

	inline constexpr std::array<std::string_view, kTranslateTargetKeyCount> kTranslateTargetKeys{ {
		"$MISSION",
		"$MISSIONS",
		"$MISSION COMPLETE",
		"$MISSION FAILED",
		"$MISSION REWARDS",
		"$MISSION STATUS",
		"$MISSION UPDATED",
		"$MissionAdded",
		"$MissionComplete",
		"$MissionFailed",
		"$MissionMenu",
		"$MissionNew",
		"$MissionUpdate",
		"$Mission Data",
		"$Mission Info",
		"$Mission name",
		"$QUEST",
		"$Quest",
		"$QUESTS",
		"$SET MISSION ACTIVE",
	} };

	[[nodiscard]] inline std::string ExpectedTranslateValue(std::string_view a_key, const QuestLabelConfig& a_cfg)
	{
		if (!a_cfg.Active()) {
			if (a_key == "$MISSIONS" || a_key == "$QUESTS") {
				return "MISSIONS";
			}
			if (a_key == "$MISSION COMPLETE") {
				return "MISSION COMPLETE";
			}
			if (a_key == "$MISSION FAILED" || a_key == "$MissionFailed") {
				return "MISSION FAILED";
			}
			if (a_key == "$MISSION REWARDS") {
				return "MISSION REWARDS";
			}
			if (a_key == "$MISSION STATUS") {
				return "MISSION STATUS";
			}
			if (a_key == "$MISSION UPDATED" || a_key == "$MissionUpdate") {
				return "MISSION UPDATED";
			}
			if (a_key == "$MissionAdded") {
				return "ADDED TO MISSION MENU";
			}
			if (a_key == "$MissionComplete") {
				return "MISSION COMPLETE";
			}
			if (a_key == "$MissionMenu") {
				return "MISSION MENU";
			}
			if (a_key == "$MissionNew") {
				return "NEW MISSION";
			}
			if (a_key == "$Mission Data") {
				return "Mission Data";
			}
			if (a_key == "$Mission Info") {
				return "Mission Info";
			}
			if (a_key == "$Mission name") {
				return "Mission Name";
			}
			if (a_key == "$Quest") {
				return "Mission";
			}
			if (a_key == "$SET MISSION ACTIVE") {
				return "SET MISSION ACTIVE";
			}
			return "MISSION";
		}

		const std::string& raw = a_cfg.questHudLabel;
		const std::string  upper = (std::ranges::all_of(raw, [](char c) { return !std::islower(static_cast<unsigned char>(c)); }))
		                              ? raw
		                              : detail::ToUpperAscii(raw);
		const std::string  title = detail::ToTitleWords(raw);
		const std::string  pluralUpper = detail::ToPluralUpperAscii(upper);

		if (a_key == "$MISSION" || a_key == "$QUEST") {
			return upper;
		}
		if (a_key == "$MISSIONS" || a_key == "$QUESTS") {
			return pluralUpper;
		}
		if (a_key == "$MISSION COMPLETE") {
			return std::format("{} COMPLETE", upper);
		}
		if (a_key == "$MISSION FAILED" || a_key == "$MissionFailed") {
			return std::format("{} FAILED", upper);
		}
		if (a_key == "$MISSION REWARDS") {
			return std::format("{} REWARDS", upper);
		}
		if (a_key == "$MISSION STATUS") {
			return std::format("{} STATUS", upper);
		}
		if (a_key == "$MISSION UPDATED" || a_key == "$MissionUpdate") {
			return std::format("{} UPDATED", upper);
		}
		if (a_key == "$MissionAdded") {
			return std::format("ADDED TO {} LOG", upper);
		}
		if (a_key == "$MissionComplete") {
			return std::format("{} COMPLETED", upper);
		}
		if (a_key == "$MissionMenu") {
			return std::format("{} LOG", upper);
		}
		if (a_key == "$MissionNew") {
			return std::format("NEW {}", upper);
		}
		if (a_key == "$Mission Data") {
			return std::format("{} Data", title);
		}
		if (a_key == "$Mission Info") {
			return std::format("{} Info", title);
		}
		if (a_key == "$Mission name") {
			return std::format("{} Name", title);
		}
		if (a_key == "$Quest") {
			return title;
		}
		if (a_key == "$SET MISSION ACTIVE") {
			return std::format("SET {} ACTIVE", upper);
		}
		return upper;
	}

	/// Verify raw `Translate_en.txt` bytes contain expected translations for all 20 HUD/menu keys.
	[[nodiscard]] inline TranslateFileStatus VerifyTranslateEnBytes(
		std::string_view        a_raw,
		const QuestLabelConfig& a_cfg)
	{
		TranslateFileStatus status{};
		if (a_raw.empty()) {
			return status;
		}
		status.filePresent = true;
		const std::string                        decoded = detail::DecodeTranslateText(a_raw);
		std::array<bool, kTranslateTargetKeyCount> matched{};

		std::size_t pos = 0;
		while (pos <= decoded.size()) {
			const auto nextNl = decoded.find('\n', pos);
			auto       line = (nextNl == std::string::npos)
			                      ? std::string_view(decoded).substr(pos)
			                      : std::string_view(decoded).substr(pos, nextNl - pos);
			pos = (nextNl == std::string::npos) ? decoded.size() + 1 : nextNl + 1;
			if (!line.empty() && line.back() == '\r') {
				line.remove_suffix(1);
			}
			const auto tab = line.find('\t');
			if (tab == std::string_view::npos) {
				continue;
			}
			const auto key = line.substr(0, tab);
			const auto val = line.substr(tab + 1);
			for (std::size_t i = 0; i < kTranslateTargetKeyCount; ++i) {
				if (key == kTranslateTargetKeys[i]) {
					const std::string expected = ExpectedTranslateValue(key, a_cfg);
					const bool        ok = a_cfg.Active() ? (val == expected) : detail::EqualsIgnoreCase(val, expected);
					if (ok) {
						matched[i] = true;
					}
					break;
				}
			}
		}

		for (const bool m : matched) {
			if (m) {
				++status.keysMatched;
			}
		}
		status.fileOk = (status.keysMatched == kTranslateTargetKeyCount);
		return status;
	}

	/// Verify `interface/translate_en.txt` in a mod `Main.ba2` archive (preferring `FO4ActorRaider - Main.ba2`)
	/// or loose `<dataDir>/Interface/Translate_en.txt` on disk contains expected translations for all 20 HUD/menu keys.
	[[nodiscard]] inline TranslateFileStatus VerifyTranslateEnFile(
		const std::filesystem::path& a_dataDir,
		const QuestLabelConfig&      a_cfg)
	{
		std::error_code ec;
		const auto      primaryBa2 = a_dataDir / "FO4ActorRaider - Main.ba2";
		if (std::filesystem::is_regular_file(primaryBa2, ec)) {
			std::string raw;
			if (detail::ReadUncompressedBa2Entry(primaryBa2, "interface/translate_en.txt", raw)) {
				return VerifyTranslateEnBytes(raw, a_cfg);
			}
		}
		if (std::filesystem::is_directory(a_dataDir, ec)) {
			std::vector<std::filesystem::path> otherArchives;
			for (const auto& entry : std::filesystem::directory_iterator(a_dataDir, ec)) {
				if (!entry.is_regular_file(ec)) {
					continue;
				}
				const auto name = entry.path().filename().string();
				if (!detail::EndsWithIgnoreCase(name, " - Main.ba2")) {
					continue;
				}
				if (detail::StartsWithIgnoreCase(name, "Starfield") ||
				    detail::StartsWithIgnoreCase(name, "BlueprintShips") ||
				    detail::StartsWithIgnoreCase(name, "SFBGS")) {
					continue;
				}
				otherArchives.push_back(entry.path());
			}
			std::sort(otherArchives.begin(), otherArchives.end());
			for (const auto& ba2Path : otherArchives) {
				std::string raw;
				if (detail::ReadUncompressedBa2Entry(ba2Path, "interface/translate_en.txt", raw)) {
					return VerifyTranslateEnBytes(raw, a_cfg);
				}
			}
		}

		TranslateFileStatus   status{};
		std::filesystem::path filePath = a_dataDir / "Interface" / "Translate_en.txt";
		if (!std::filesystem::is_regular_file(filePath, ec)) {
			const auto lowerPath = a_dataDir / "interface" / "translate_en.txt";
			if (std::filesystem::is_regular_file(lowerPath, ec)) {
				filePath = lowerPath;
			} else {
				return status;
			}
		}
		std::ifstream in(filePath, std::ios::binary);
		if (!in) {
			return status;
		}
		std::ostringstream ss;
		ss << in.rdbuf();
		return VerifyTranslateEnBytes(ss.str(), a_cfg);
	}

	/// Format the SFSE startup log line recording the active per-game HUD quest label configuration and Translate_en.txt check.
	[[nodiscard]] inline std::string FormatStartupLog(
		const QuestLabelConfig&    a_cfg,
		const TranslateFileStatus& a_fileStatus = {})
	{
		const std::string_view lbl = a_cfg.questHudLabel.empty() ? kDefaultQuestHudLabel : std::string_view(a_cfg.questHudLabel);
		return std::format("step=hud_quest_label mode={} label={} active={} file={} file_ok={}",
			a_cfg.Mode(), lbl, a_cfg.Active() ? 1 : 0,
			a_fileStatus.filePresent ? "present" : "absent",
			a_fileStatus.fileOk ? 1 : 0);
	}

	/// Rewrite Starfield's "MISSION" HUD label / toast tokens to the configured QuestHudLabel (default "QUEST")
	/// when ReplaceMissionLabel=1, while leaving mission/quest titles (such as "Out of Time") untouched.
	[[nodiscard]] inline std::string RewriteMissionHudLabel(std::string_view a_text, const QuestLabelConfig& a_cfg)
	{
		if (!a_cfg.Active()) {
			return std::string(a_text);
		}
		const std::string& label = a_cfg.questHudLabel;
		const auto         trimmed = detail::TrimWs(a_text);

		if (trimmed == "$MissionNew" || detail::EqualsIgnoreCase(trimmed, "NEW MISSION")) {
			return std::format("NEW {}", label);
		}
		if (trimmed == "$MissionUpdate" || trimmed == "$MISSION UPDATED" ||
		    detail::EqualsIgnoreCase(trimmed, "MISSION UPDATED")) {
			return std::format("{} UPDATED", label);
		}
		if (trimmed == "$MISSION STATUS" || detail::EqualsIgnoreCase(trimmed, "MISSION STATUS")) {
			return std::format("{} STATUS", label);
		}
		if (trimmed == "$MissionFailed" || trimmed == "$MISSION FAILED" ||
		    detail::EqualsIgnoreCase(trimmed, "MISSION FAILED")) {
			return std::format("{} FAILED", label);
		}
		if (trimmed == "$MISSION COMPLETE" || detail::EqualsIgnoreCase(trimmed, "MISSION COMPLETE")) {
			return std::format("{} COMPLETE", label);
		}
		if (trimmed == "$MissionComplete" || detail::EqualsIgnoreCase(trimmed, "MISSION COMPLETED")) {
			return std::format("{} COMPLETED", label);
		}
		if (trimmed == "$MISSION REWARDS" || detail::EqualsIgnoreCase(trimmed, "MISSION REWARDS")) {
			return std::format("{} REWARDS", label);
		}
		if (trimmed == "$MissionAdded" || detail::EqualsIgnoreCase(trimmed, "ADDED TO MISSION MENU")) {
			return std::format("ADDED TO {} LOG", label);
		}
		if (trimmed == "$MissionMenu" || detail::EqualsIgnoreCase(trimmed, "MISSION MENU")) {
			return std::format("{} LOG", label);
		}
		if (trimmed == "$MISSIONS" || trimmed == "$QUESTS" || detail::EqualsIgnoreCase(trimmed, "MISSIONS")) {
			return detail::ToPluralUpperAscii(label);
		}
		if (trimmed == "$Mission Data" || trimmed == "$Mission Info" || trimmed == "$Mission name" || trimmed == "$Quest") {
			return ExpectedTranslateValue(trimmed, a_cfg);
		}
		if (trimmed == "$SET MISSION ACTIVE" || detail::EqualsIgnoreCase(trimmed, "SET MISSION ACTIVE")) {
			return std::format("SET {} ACTIVE", label);
		}
		if (trimmed == "$MISSION" || trimmed == "$QUEST" || detail::EqualsIgnoreCase(trimmed, "MISSION")) {
			return label;
		}
		return std::string(a_text);
	}

	[[nodiscard]] inline std::string RewriteMissionHudLabel(
		std::string_view a_text,
		bool             a_replaceMissionLabel,
		std::string_view a_questHudLabel = kDefaultQuestHudLabel)
	{
		QuestLabelConfig cfg;
		cfg.replaceMissionLabel = a_replaceMissionLabel;
		cfg.questHudLabel = detail::SanitizeHudLabel(a_questHudLabel);
		return RewriteMissionHudLabel(a_text, cfg);
	}
}
