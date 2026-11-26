#pragma once

#include <algorithm>
#include <array>
#include <format>
#include <string>

namespace fo4sf::lift
{
	inline constexpr std::size_t kLiftRows = 7;
	inline constexpr std::size_t kSpecialCount = 7;
	inline constexpr int         kSpecialMin = 1;
	inline constexpr int         kSpecialMax = 10;
	inline constexpr int         kSpecialTotal = 40;

	inline constexpr std::array<const char*, kSpecialCount> kSpecialNames{ {
		"STRENGTH",
		"PERCEPTION",
		"ENDURANCE",
		"CHARISMA",
		"INTELLIGENCE",
		"AGILITY",
		"LUCK",
	} };

	enum class Page : std::uint8_t
	{
		kOptions = 0,
		kSpecial = 1,
	};

	enum class CommitAction : std::uint8_t
	{
		kNone = 0,
		kRide = 1,             // FO4SF_StartCardOpen -> 6.0
		kStay = 2,             // FO4SF_StartCardOpen -> 7.0
		kChangeAppearance = 3, // FO4SF_StartCardOpen -> 8.0
	};

	struct LiftCommitPayload
	{
		CommitAction                    action = CommitAction::kNone;
		std::array<int, kSpecialCount> special{};
		bool                           specialConfirmed = false;
	};

	class LiftMenuModel
	{
	public:
		void Reset(const std::array<int, kSpecialCount>& a_initial, bool a_alreadyConfirmed)
		{
			special_ = a_initial;
			for (int& v : special_) {
				v = std::clamp(v, kSpecialMin, kSpecialMax);
			}
			// Clamp excess back down toward 5 if any test override broke the 40-pt invariant.
			while (Total() > kSpecialTotal) {
				bool changed = false;
				for (int& v : special_) {
					if (v > kSpecialMin && Total() > kSpecialTotal) {
						--v;
						changed = true;
					}
				}
				if (!changed) {
					break;
				}
			}
			confirmed_ = a_alreadyConfirmed && (Remaining() == 0);
			page_ = Page::kOptions;
			cursor_ = 0;
			if (Remaining() > 0 && !confirmed_) {
				status_ = std::format("CHOOSE RIDE LIFT TO SURFACE NOW, OR EDIT S.P.E.C.I.A.L. ({} PT(S) UNSPENT)", Remaining());
			} else {
				status_ = "CHOOSE RIDE LIFT TO SURFACE TO RIDE UP, OR EDIT S.P.E.C.I.A.L.";
			}
		}

		[[nodiscard]] Page CurrentPage() const noexcept { return page_; }
		[[nodiscard]] int  Cursor() const noexcept { return cursor_; }
		[[nodiscard]] bool Confirmed() const noexcept { return confirmed_; }

		[[nodiscard]] int Total() const noexcept
		{
			int s = 0;
			for (int v : special_) {
				s += v;
			}
			return s;
		}

		[[nodiscard]] int Remaining() const noexcept
		{
			return std::max(0, kSpecialTotal - Total());
		}

		[[nodiscard]] std::size_t RowCountForPage() const noexcept
		{
			return page_ == Page::kOptions ? 4u : kSpecialCount;
		}

		void SelectRow(int a_row) noexcept
		{
			const int n = static_cast<int>(RowCountForPage());
			if (n <= 0) {
				cursor_ = 0;
				return;
			}
			cursor_ = std::clamp(a_row, 0, n - 1);
		}

		void MoveCursor(int a_delta) noexcept
		{
			const int n = static_cast<int>(RowCountForPage());
			if (n <= 0) {
				return;
			}
			cursor_ = (cursor_ + a_delta % n + n) % n;
		}

		void AdjustCurrentOrRow(int a_row, int a_delta)
		{
			if (page_ == Page::kOptions) {
				SelectRow(a_row);
				if (cursor_ == 1 && a_delta != 0) {
					EnterSpecialPage();
				}
				return;
			}
			SelectRow(a_row);
			if (a_delta > 0) {
				if (Remaining() <= 0) {
					status_ = "NO UNSPENT POINTS LEFT - PRESS CONFIRM OR LOWER A STAT";
					return;
				}
				if (special_[cursor_] >= kSpecialMax) {
					status_ = std::format("{} IS ALREADY AT MAX ({})", kSpecialNames[cursor_], kSpecialMax);
					return;
				}
				++special_[cursor_];
				status_ = std::format("{} -> {}  (POOL REMAINING: {})",
					kSpecialNames[cursor_], special_[cursor_], Remaining());
			} else if (a_delta < 0) {
				if (special_[cursor_] <= kSpecialMin) {
					status_ = std::format("{} IS ALREADY AT MIN ({})", kSpecialNames[cursor_], kSpecialMin);
					return;
				}
				--special_[cursor_];
				confirmed_ = false;
				status_ = std::format("{} -> {}  (POOL REMAINING: {})",
					kSpecialNames[cursor_], special_[cursor_], Remaining());
			}
		}

		void EnterSpecialPage()
		{
			page_ = Page::kSpecial;
			cursor_ = 0;
			status_ = std::format("POOL OF 40 - UNSPENT POINTS: {}  (CONFIRM WHEN 0 LEFT)", Remaining());
		}

		bool BackOrStay(LiftCommitPayload& a_out)
		{
			if (page_ == Page::kSpecial) {
				page_ = Page::kOptions;
				cursor_ = 0;
				status_ = Remaining() == 0
					? "RETURNED TO LIFT OPTIONS"
					: std::format("UNSPENT POINTS: {} - RIDE LIFT TO SURFACE OR EDIT S.P.E.C.I.A.L.", Remaining());
				return false;
			}
			a_out.action = CommitAction::kStay;
			a_out.special = special_;
			a_out.specialConfirmed = confirmed_ && (Remaining() == 0);
			return true;
		}

		bool ActivateOrConfirm(bool a_allowSpecialFinish, LiftCommitPayload& a_out)
		{
			if (page_ == Page::kSpecial) {
				if (Remaining() > 0 && a_allowSpecialFinish) {
					status_ = std::format("ALLOCATE ALL {} REMAINING POINT(S) FIRST", Remaining());
					return false;
				}
				if (Remaining() > 0) {
					AdjustCurrentOrRow(cursor_, 1);
					return false;
				}
				confirmed_ = true;
				page_ = Page::kOptions;
				cursor_ = 0;
				status_ = "S.P.E.C.I.A.L. CONFIRMED - SELECT RIDE LIFT TO SURFACE";
				return false;
			}

			switch (cursor_) {
			case 0:
				confirmed_ = true;
				a_out.action = CommitAction::kRide;
				a_out.special = special_;
				a_out.specialConfirmed = true;
				return true;
			case 1:
				EnterSpecialPage();
				return false;
			case 2:
				a_out.action = CommitAction::kChangeAppearance;
				a_out.special = special_;
				a_out.specialConfirmed = confirmed_ && (Remaining() == 0);
				return true;
			case 3:
			default:
				a_out.action = CommitAction::kStay;
				a_out.special = special_;
				a_out.specialConfirmed = confirmed_ && (Remaining() == 0);
				return true;
			}
		}

		void RenderLines(std::array<std::string, kLiftRows>& a_rows, std::string& a_status, std::string& a_hint) const
		{
			a_rows.fill(" ");
			if (page_ == Page::kOptions) {
				const std::array<std::string, 4> opts{
					"RIDE LIFT TO SURFACE",
					std::format("EDIT S.P.E.C.I.A.L. (POOL: {})", Remaining()),
					"CHANGE APPEARANCE",
					"STAY IN VAULT 111",
				};
				for (std::size_t i = 0; i < opts.size(); ++i) {
					a_rows[i] = std::format("{}{}", (static_cast<int>(i) == cursor_) ? "> " : "  ", opts[i]);
				}
				a_hint = "UP/DOWN SELECT   ENTER OR CLICK TO CHOOSE   ESC STAY";
			} else {
				for (std::size_t i = 0; i < kSpecialCount; ++i) {
					a_rows[i] = std::format("{}{}: {}  [-/+]",
						(static_cast<int>(i) == cursor_) ? "> " : "  ",
						kSpecialNames[i],
						special_[i]);
				}
				a_hint = "UP/DOWN STAT   LEFT/RIGHT ADJUST   ENTER/CONFIRM APPLY   ESC BACK";
			}
			a_status = status_;
		}

	private:
		Page                          page_ = Page::kOptions;
		int                           cursor_ = 0;
		bool                          confirmed_ = false;
		std::array<int, kSpecialCount> special_{ 5, 5, 5, 5, 5, 5, 5 };
		std::string                   status_;
	};
}
