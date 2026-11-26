#pragma once

// Pure C++20 HUD Quest/Mission label rewrite helper and INI setting parser.
// Kept free of Starfield/SFSE headers so offline host tests can compile and verify it directly.
// Reads [FO4SFPipboyMenu] settings:
//   ReplaceMissionLabel=1   (0/1 toggle; default 1 for FO4)
//   QuestHudLabel=QUEST     (replacement label for Starfield's "MISSION" HUD toast header; default "QUEST")

#include <algorithm>
#include <array>
#include <cctype>
#include <filesystem>
#include <format>
#include <fstream>
#include <sstream>
#include <string>
#include <string_view>

namespace fo4sf::hud
{
	inline constexpr std::string_view kDefaultQuestHudLabel = "QUEST";
	inline constexpr std::size_t      kMaxQuestHudLabelLen = 32;

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

	/// Format the SFSE startup log line recording the active per-game HUD quest label configuration.
	[[nodiscard]] inline std::string FormatStartupLog(const QuestLabelConfig& a_cfg)
	{
		const std::string_view lbl = a_cfg.questHudLabel.empty() ? kDefaultQuestHudLabel : std::string_view(a_cfg.questHudLabel);
		return std::format("step=hud_quest_label mode={} label={} active={}",
			a_cfg.Mode(), lbl, a_cfg.Active() ? 1 : 0);
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
		if (trimmed == "$MISSION" || detail::EqualsIgnoreCase(trimmed, "MISSION")) {
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
